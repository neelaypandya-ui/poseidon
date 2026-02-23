import asyncio
import logging

import numpy as np
import rasterio
from rasterio.transform import xy, Affine
from scipy import ndimage
from numba import njit

from app.config import settings
from app.database import get_db

logger = logging.getLogger("poseidon.sar_cfar")


@njit
def _ca_cfar_2d(
    image: np.ndarray,
    guard: int,
    background: int,
    alpha: float,
) -> np.ndarray:
    """Cell-Averaging CFAR detector (numba-accelerated).

    For each pixel, estimates background noise from an annular window
    (excluding guard cells) and compares the pixel to a threshold.
    """
    rows, cols = image.shape
    detections = np.zeros((rows, cols), dtype=np.bool_)
    outer = guard + background

    for r in range(outer, rows - outer):
        for c in range(outer, cols - outer):
            # Sum the background ring (outer window minus guard window)
            bg_sum = 0.0
            bg_count = 0
            for dr in range(-outer, outer + 1):
                for dc in range(-outer, outer + 1):
                    if abs(dr) <= guard and abs(dc) <= guard:
                        continue
                    bg_sum += image[r + dr, c + dc]
                    bg_count += 1

            if bg_count == 0:
                continue

            noise_mean = bg_sum / bg_count
            threshold = noise_mean * alpha

            if image[r, c] > threshold:
                detections[r, c] = True

    return detections


def _compute_alpha(n_bg_cells: int, pfa: float) -> float:
    """Compute CFAR threshold multiplier from number of bg cells and desired PFA."""
    return n_bg_cells * (pfa ** (-1.0 / n_bg_cells) - 1.0)


async def process_scene(scene_db_id: int) -> int:
    """Run CFAR detection on a downloaded SAR scene. Returns number of detections."""
    db = get_db()

    async with db.acquire() as conn:
        scene = await conn.fetchrow(
            "SELECT id, file_path, acquisition_date, status FROM sar_scenes WHERE id = $1",
            scene_db_id,
        )

    if not scene:
        raise ValueError(f"Scene {scene_db_id} not found")

    if not scene["file_path"]:
        raise ValueError(f"Scene {scene_db_id} has no file_path — download first")

    # Update status to processing
    async with db.acquire() as conn:
        await conn.execute(
            "UPDATE sar_scenes SET status = 'processing' WHERE id = $1", scene_db_id
        )

    # Get the scene footprint for geocoding (in case TIFF has no georeference)
    async with db.acquire() as conn:
        footprint_row = await conn.fetchrow(
            """SELECT ST_XMin(footprint) as xmin, ST_YMin(footprint) as ymin,
                      ST_XMax(footprint) as xmax, ST_YMax(footprint) as ymax
               FROM sar_scenes WHERE id = $1""",
            scene_db_id,
        )
    footprint_bbox = None
    if footprint_row:
        footprint_bbox = (
            float(footprint_row["xmin"]),
            float(footprint_row["ymin"]),
            float(footprint_row["xmax"]),
            float(footprint_row["ymax"]),
        )

    try:
        # Run CPU-intensive work in a thread pool
        detections = await asyncio.to_thread(
            _run_cfar_pipeline, scene["file_path"], footprint_bbox
        )

        # Insert detections into DB
        count = 0
        async with db.acquire() as conn:
            # Delete any existing detections for this scene (re-processing)
            await conn.execute(
                "DELETE FROM sar_detections WHERE scene_id = $1", scene_db_id
            )

            for det in detections:
                await conn.execute(
                    """
                    INSERT INTO sar_detections
                        (scene_id, geom, rcs_db, pixel_size_m, confidence)
                    VALUES ($1, ST_SetSRID(ST_MakePoint($2, $3), 4326), $4, $5, $6)
                    """,
                    scene_db_id,
                    det["lon"],
                    det["lat"],
                    det["rcs_db"],
                    det["pixel_size_m"],
                    det["confidence"],
                )
                count += 1

            await conn.execute(
                "UPDATE sar_scenes SET status = 'completed', detection_count = $1 WHERE id = $2",
                count,
                scene_db_id,
            )

        logger.info("CFAR detection complete: %d targets in scene %d", count, scene_db_id)
        return count

    except Exception as e:
        logger.error("CFAR processing failed for scene %d: %s", scene_db_id, e)
        async with db.acquire() as conn:
            await conn.execute(
                "UPDATE sar_scenes SET status = 'failed' WHERE id = $1", scene_db_id
            )
        raise


def _run_cfar_pipeline(
    tiff_path: str,
    footprint_bbox: tuple[float, float, float, float] | None = None,
) -> list[dict]:
    """CPU-bound CFAR pipeline: read GeoTIFF → intensity → mask → CFAR → cluster → geocode."""
    guard = settings.sar_cfar_guard_pixels
    background = settings.sar_cfar_bg_pixels
    pfa = settings.sar_cfar_pfa

    # Downsample factor — Sentinel-1 IW GRD is 10m; 4x gives ~40m, still fine for ships
    DOWNSAMPLE = 4

    with rasterio.open(tiff_path) as src:
        full_h, full_w = src.height, src.width
        out_h, out_w = full_h // DOWNSAMPLE, full_w // DOWNSAMPLE
        band = src.read(
            1,
            out_shape=(out_h, out_w),
            resampling=rasterio.enums.Resampling.average,
        ).astype(np.float64)

        # Determine geotransform
        if src.crs and not src.transform.is_identity:
            # File has proper geotransform
            transform = src.transform * Affine.scale(DOWNSAMPLE, DOWNSAMPLE)
        elif src.gcps and src.gcps[0]:
            # Use GCPs to build an approximate affine
            from rasterio.transform import from_gcps
            gcp_transform = from_gcps(src.gcps[0])
            transform = gcp_transform * Affine.scale(DOWNSAMPLE, DOWNSAMPLE)
        else:
            # No georeferencing — compute from DB footprint later
            # For now, set a flag
            transform = None

        if transform:
            res_x = abs(transform.a)
            res_y = abs(transform.e)
        else:
            res_x = DOWNSAMPLE * 10.0 / 111_320
            res_y = res_x
        pixel_size_m = (res_x + res_y) / 2.0 * 111_320

    # If no embedded georeference, build transform from scene footprint
    if transform is None and footprint_bbox:
        xmin, ymin, xmax, ymax = footprint_bbox
        res_x_deg = (xmax - xmin) / out_w
        res_y_deg = (ymax - ymin) / out_h
        transform = Affine(res_x_deg, 0, xmin, 0, -res_y_deg, ymax)
        res_x = res_x_deg
        res_y = res_y_deg
        pixel_size_m = (res_x + res_y) / 2.0 * 111_320
        logger.info("Using footprint-derived transform: origin=(%.4f, %.4f), res=(%.6f, %.6f)", xmin, ymax, res_x_deg, res_y_deg)

    if transform is None:
        logger.error("No georeference available — cannot geocode detections")
        return []

    logger.info(
        "CFAR input: shape=%s (downsampled %dx from %dx%d), min=%.1f, max=%.1f, mean=%.1f, nonzero=%d",
        band.shape, DOWNSAMPLE, full_h, full_w,
        np.min(band), np.max(band), np.mean(band),
        int(np.count_nonzero(band)),
    )

    # Work with intensity (DN²) — CFAR operates on power-like quantities
    intensity = band ** 2

    # Mask nodata (zeros at scene borders) and land (high percentile)
    # Land has very high, stable backscatter; ocean is darker and variable
    valid = band > 0
    if np.sum(valid) == 0:
        logger.warning("CFAR: entire image is nodata")
        return []

    # Use percentile-based land masking: land pixels are typically in the top ~10%
    # of intensity. We mask anything above the 90th percentile of valid pixels.
    p90 = np.percentile(intensity[valid], 90)
    ocean_mask = valid & (intensity < p90)

    logger.info(
        "CFAR masking: valid=%d, ocean=%d (%.1f%%), p90=%.1f",
        int(np.sum(valid)), int(np.sum(ocean_mask)),
        100.0 * np.sum(ocean_mask) / max(np.sum(valid), 1), p90,
    )

    # For CFAR input: use intensity, set masked areas to 0
    cfar_input = np.where(ocean_mask, intensity, 0.0)

    # Compute CFAR parameters
    outer = guard + background
    n_bg_cells = (2 * outer + 1) ** 2 - (2 * guard + 1) ** 2
    alpha = _compute_alpha(n_bg_cells, pfa)

    logger.info("CFAR params: guard=%d, bg=%d, n_bg=%d, alpha=%.2f, pfa=%.1e", guard, background, n_bg_cells, alpha, pfa)

    # Run CFAR
    detection_mask = _ca_cfar_2d(cfar_input, guard, background, alpha)

    # Remove detections in masked areas
    detection_mask = detection_mask & ocean_mask

    n_det_pixels = int(np.sum(detection_mask))
    logger.info("CFAR raw detection pixels: %d", n_det_pixels)

    if n_det_pixels == 0:
        return []

    # Cluster adjacent detections
    labeled, n_clusters = ndimage.label(detection_mask)

    # Compute dB values for reporting (relative to image mean)
    mean_intensity = np.mean(intensity[ocean_mask]) if np.any(ocean_mask) else 1.0

    results = []
    for cluster_id in range(1, n_clusters + 1):
        cluster_pixels = np.argwhere(labeled == cluster_id)
        if len(cluster_pixels) == 0:
            continue

        # Skip tiny clusters (likely noise)
        if len(cluster_pixels) < 2:
            continue

        # Centroid in pixel coords
        centroid_row = cluster_pixels[:, 0].mean()
        centroid_col = cluster_pixels[:, 1].mean()

        # Geocode centroid → lon/lat
        lon, lat = xy(transform, centroid_row, centroid_col)

        # RCS: peak intensity in cluster, expressed in dB relative to mean
        cluster_values = intensity[labeled == cluster_id]
        peak_intensity = float(np.max(cluster_values))
        rcs_db = float(10.0 * np.log10(peak_intensity / max(mean_intensity, 1e-10)))

        # Estimated physical size
        size_m = float(len(cluster_pixels) * pixel_size_m)

        # Confidence: based on signal-to-clutter ratio
        local_bg = float(np.mean(cfar_input[
            max(0, int(centroid_row) - outer):int(centroid_row) + outer + 1,
            max(0, int(centroid_col) - outer):int(centroid_col) + outer + 1,
        ]))
        scr = peak_intensity / max(local_bg, 1e-10)
        confidence = min(1.0, max(0.1, float(np.log10(max(scr, 1.0))) / 2.0))

        results.append({
            "lon": float(lon),
            "lat": float(lat),
            "rcs_db": rcs_db,
            "pixel_size_m": size_m,
            "confidence": float(confidence),
        })

    logger.info("CFAR pipeline: %d targets from %d clusters, %d detection pixels", len(results), n_clusters, n_det_pixels)
    return results


async def match_detections_to_ais(scene_db_id: int) -> int:
    """Match SAR detections to AIS vessel positions. Returns number of matches."""
    db = get_db()
    radius_m = settings.sar_match_radius_m
    time_window_s = settings.sar_match_time_window_s

    async with db.acquire() as conn:
        scene = await conn.fetchrow(
            "SELECT id, acquisition_date FROM sar_scenes WHERE id = $1",
            scene_db_id,
        )
        if not scene:
            return 0

        acq_time = scene["acquisition_date"]

        unmatched = await conn.fetch(
            """
            SELECT id, ST_X(geom) as lon, ST_Y(geom) as lat
            FROM sar_detections
            WHERE scene_id = $1 AND matched = FALSE
            """,
            scene_db_id,
        )

        if not unmatched:
            return 0

        match_count = 0
        for det in unmatched:
            # Find closest AIS position within time window and spatial radius
            match = await conn.fetchrow(
                """
                SELECT vp.mmsi,
                       ST_Distance(
                           vp.geom::geography,
                           ST_SetSRID(ST_MakePoint($1, $2), 4326)::geography
                       ) as distance_m,
                       EXTRACT(EPOCH FROM (vp.timestamp - $3)) as time_delta_s
                FROM vessel_positions vp
                WHERE vp.timestamp BETWEEN $3 - make_interval(secs => $4)
                                       AND $3 + make_interval(secs => $4)
                  AND ST_DWithin(
                          vp.geom::geography,
                          ST_SetSRID(ST_MakePoint($1, $2), 4326)::geography,
                          $5
                      )
                ORDER BY ST_Distance(
                    vp.geom::geography,
                    ST_SetSRID(ST_MakePoint($1, $2), 4326)::geography
                )
                LIMIT 1
                """,
                det["lon"],
                det["lat"],
                acq_time,
                time_window_s,
                radius_m,
            )

            if match:
                await conn.execute(
                    """
                    INSERT INTO sar_vessel_matches (detection_id, mmsi, distance_m, time_delta_s)
                    VALUES ($1, $2, $3, $4)
                    """,
                    det["id"],
                    match["mmsi"],
                    match["distance_m"],
                    abs(match["time_delta_s"]),
                )
                await conn.execute(
                    "UPDATE sar_detections SET matched = TRUE WHERE id = $1",
                    det["id"],
                )
                match_count += 1

    logger.info(
        "AIS matching for scene %d: %d/%d detections matched",
        scene_db_id,
        match_count,
        len(unmatched),
    )
    return match_count


async def run_sar_matcher():
    """Background task: periodically match unmatched SAR detections to AIS."""
    logger.info("SAR matcher background task starting...")
    while True:
        try:
            await asyncio.sleep(60)
            db = get_db()
            async with db.acquire() as conn:
                scenes = await conn.fetch(
                    """
                    SELECT DISTINCT s.id
                    FROM sar_scenes s
                    JOIN sar_detections d ON d.scene_id = s.id
                    WHERE s.status = 'completed' AND d.matched = FALSE
                    """,
                )

            for scene_row in scenes:
                try:
                    await match_detections_to_ais(scene_row["id"])
                except Exception as e:
                    logger.error("Match error for scene %d: %s", scene_row["id"], e)

        except asyncio.CancelledError:
            logger.info("SAR matcher cancelled")
            return
        except Exception as e:
            logger.error("SAR matcher error: %s", e)
            await asyncio.sleep(10)
