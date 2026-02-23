import os
import logging
import zipfile
from datetime import datetime

import aiohttp
import aiofiles

from app.config import settings
from app.database import get_db
from app.services.copernicus_auth import get_access_token, get_download_token

logger = logging.getLogger("poseidon.sar_service")

STAC_URL = "https://catalogue.dataspace.copernicus.eu/stac/search"
ODATA_BASE = "https://zipper.dataspace.copernicus.eu/odata/v1"


def _extract_vh_url(feat: dict) -> str | None:
    """Extract the HTTPS download URL for the VH band from a STAC feature."""
    assets = feat.get("assets", {})

    # Prefer VH, fall back to VV
    for key in ("vh", "vv"):
        asset = assets.get(key, {})
        alt = asset.get("alternate", {}).get("https", {})
        href = alt.get("href")
        if href:
            return href

    return None


async def search_scenes(
    bbox: tuple[float, float, float, float],
    start_date: str,
    end_date: str,
    limit: int = 10,
) -> list[dict]:
    """Search Copernicus STAC for Sentinel-1 GRD scenes in bbox + date range."""
    body = {
        "collections": ["sentinel-1-grd"],
        "bbox": list(bbox),
        "datetime": f"{start_date}T00:00:00Z/{end_date}T23:59:59Z",
        "limit": limit,
    }

    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}

    async with aiohttp.ClientSession() as session:
        async with session.post(STAC_URL, json=body, headers=headers) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"STAC search failed ({resp.status}): {text}")
            result = await resp.json()

    features = result.get("features", [])
    scenes = []

    db = get_db()
    async with db.acquire() as conn:
        for feat in features:
            props = feat.get("properties", {})
            geom = feat.get("geometry", {})
            scene_id = feat.get("id", "")

            coords = geom.get("coordinates", [[]])
            ring = coords[0] if coords else []
            wkt_ring = ", ".join(f"{c[0]} {c[1]}" for c in ring)
            wkt = f"SRID=4326;POLYGON(({wkt_ring}))"

            acq_date = props.get("datetime", "")
            title = props.get("title", feat.get("id", ""))
            platform = props.get("platform", "")
            polarisation = props.get("polarization", props.get("sar:polarizations", ""))
            if isinstance(polarisation, list):
                polarisation = "+".join(polarisation)
            orbit_dir = props.get("sat:orbit_state", "").upper()

            # Extract direct HTTPS URL for VH band COG
            vh_url = _extract_vh_url(feat)

            scene_meta = {
                "scene_id": scene_id,
                "title": title,
                "platform": platform,
                "acquisition_date": acq_date,
                "polarisation": polarisation,
                "orbit_direction": orbit_dir,
                "bbox": list(bbox),
            }

            try:
                row = await conn.fetchrow(
                    """
                    INSERT INTO sar_scenes
                        (scene_id, title, platform, acquisition_date, footprint,
                         polarisation, orbit_direction, file_path, status)
                    VALUES ($1, $2, $3, $4, ST_GeomFromEWKT($5), $6, $7, $8, 'pending')
                    ON CONFLICT (scene_id) DO UPDATE SET
                        title = EXCLUDED.title,
                        file_path = COALESCE(EXCLUDED.file_path, sar_scenes.file_path)
                    RETURNING id, status, detection_count
                    """,
                    scene_id,
                    title,
                    platform,
                    datetime.fromisoformat(acq_date.replace("Z", "+00:00")) if acq_date else datetime.now(),
                    wkt,
                    polarisation,
                    orbit_dir,
                    vh_url,
                )
                scene_meta["id"] = row["id"]
                scene_meta["status"] = row["status"]
                scene_meta["detection_count"] = row["detection_count"]
            except Exception as e:
                logger.error("Failed to insert scene %s: %s", scene_id, e)
                continue

            scenes.append(scene_meta)

    logger.info("STAC search returned %d scenes, inserted/updated %d", len(features), len(scenes))
    return scenes


async def download_scene(scene_db_id: int) -> str:
    """Download VH band TIFF for a scene. Returns local path to the file."""
    db = get_db()

    async with db.acquire() as conn:
        scene = await conn.fetchrow(
            "SELECT id, scene_id, title, file_path, status FROM sar_scenes WHERE id = $1",
            scene_db_id,
        )
    if not scene:
        raise ValueError(f"Scene {scene_db_id} not found")

    file_path = scene["file_path"] or ""

    # If already downloaded to local path, reuse
    if scene["status"] in ("completed", "downloaded") and file_path.startswith("/"):
        return file_path

    # file_path stores the HTTPS URL from STAC
    if not file_path.startswith("http"):
        raise ValueError(f"Scene {scene_db_id} has no download URL — re-search to populate")

    download_url = file_path
    scene_id = scene["scene_id"]
    cache_dir = os.path.join(settings.sar_scene_cache_dir, str(scene_db_id))
    os.makedirs(cache_dir, exist_ok=True)
    tiff_filename = download_url.rsplit("/", 1)[-1].replace("/$value", "").replace("$value", "scene.tiff")
    if not tiff_filename.endswith((".tiff", ".tif")):
        tiff_filename = "vh.tiff"
    local_path = os.path.join(cache_dir, tiff_filename)

    async with db.acquire() as conn:
        await conn.execute(
            "UPDATE sar_scenes SET status = 'downloading' WHERE id = $1", scene_db_id
        )

    token = await get_download_token()

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                download_url,
                headers={"Authorization": f"Bearer {token}"},
                timeout=aiohttp.ClientTimeout(total=3600),
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(f"Download failed ({resp.status}): {text[:500]}")

                async with aiofiles.open(local_path, "wb") as f:
                    total = 0
                    async for chunk in resp.content.iter_chunked(1024 * 1024):
                        await f.write(chunk)
                        total += len(chunk)

        logger.info("Downloaded VH band for scene %d: %s (%.1f MB)", scene_db_id, local_path, total / 1e6)

        async with db.acquire() as conn:
            await conn.execute(
                "UPDATE sar_scenes SET status = 'downloaded', file_path = $1 WHERE id = $2",
                local_path,
                scene_db_id,
            )

        return local_path

    except Exception as e:
        logger.error("Download failed for scene %d: %s", scene_db_id, e)
        async with db.acquire() as conn:
            await conn.execute(
                "UPDATE sar_scenes SET status = 'failed' WHERE id = $1", scene_db_id
            )
        raise


async def get_scenes(
    bbox: tuple[float, float, float, float] | None = None,
    status: str | None = None,
) -> list[dict]:
    """List SAR scenes from the database."""
    db = get_db()
    conditions = []
    params: list = []
    idx = 1

    if bbox:
        conditions.append(
            f"ST_Intersects(footprint, ST_MakeEnvelope(${idx}, ${idx+1}, ${idx+2}, ${idx+3}, 4326))"
        )
        params.extend(bbox)
        idx += 4

    if status:
        conditions.append(f"status = ${idx}")
        params.append(status)
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    async with db.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT id, scene_id, title, platform, acquisition_date, polarisation,
                   orbit_direction, status, detection_count, created_at,
                   ST_AsGeoJSON(footprint)::json as footprint_geojson
            FROM sar_scenes {where}
            ORDER BY acquisition_date DESC
            LIMIT 100
            """,
            *params,
        )

    return [
        {
            "id": r["id"],
            "scene_id": r["scene_id"],
            "title": r["title"],
            "platform": r["platform"],
            "acquisition_date": r["acquisition_date"].isoformat() if r["acquisition_date"] else None,
            "polarisation": r["polarisation"],
            "orbit_direction": r["orbit_direction"],
            "status": r["status"],
            "detection_count": r["detection_count"],
            "footprint": r["footprint_geojson"],
        }
        for r in rows
    ]


async def get_detections(
    scene_id: int | None = None,
    bbox: tuple[float, float, float, float] | None = None,
    unmatched_only: bool = False,
) -> list[dict]:
    """List SAR detections with optional filters."""
    db = get_db()
    conditions = []
    params: list = []
    idx = 1

    if scene_id is not None:
        conditions.append(f"d.scene_id = ${idx}")
        params.append(scene_id)
        idx += 1

    if bbox:
        conditions.append(
            f"ST_Intersects(d.geom, ST_MakeEnvelope(${idx}, ${idx+1}, ${idx+2}, ${idx+3}, 4326))"
        )
        params.extend(bbox)
        idx += 4

    if unmatched_only:
        conditions.append("d.matched = FALSE")

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    async with db.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT d.id, d.scene_id, ST_X(d.geom) as lon, ST_Y(d.geom) as lat,
                   d.rcs_db, d.pixel_size_m, d.confidence, d.matched, d.created_at
            FROM sar_detections d
            {where}
            ORDER BY d.created_at DESC
            LIMIT 5000
            """,
            *params,
        )

    return [
        {
            "id": r["id"],
            "scene_id": r["scene_id"],
            "lon": float(r["lon"]),
            "lat": float(r["lat"]),
            "rcs_db": r["rcs_db"],
            "pixel_size_m": r["pixel_size_m"],
            "confidence": r["confidence"],
            "matched": r["matched"],
        }
        for r in rows
    ]


async def get_ghost_vessels(
    bbox: tuple[float, float, float, float] | None = None,
) -> list[dict]:
    """Return unmatched SAR detections (ghost vessels)."""
    return await get_detections(bbox=bbox, unmatched_only=True)
