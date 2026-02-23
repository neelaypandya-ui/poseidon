import os
import logging
from datetime import datetime

import aiohttp
import aiofiles

from app.config import settings
from app.database import get_db
from app.services.copernicus_auth import get_access_token, get_download_token

logger = logging.getLogger("poseidon.sentinel2_service")

STAC_URL = "https://catalogue.dataspace.copernicus.eu/stac/search"
ODATA_BASE = "https://zipper.dataspace.copernicus.eu/odata/v1"


def _extract_tci_url(feat: dict) -> str | None:
    """Extract the HTTPS download URL for the TCI (True Color Image) from a STAC feature."""
    assets = feat.get("assets", {})

    # Prefer 'visual' asset key, fall back to 'tci'
    for key in ("visual", "tci"):
        asset = assets.get(key, {})
        # Try alternate HTTPS URL first (direct download link)
        alt = asset.get("alternate", {}).get("https", {})
        href = alt.get("href")
        if href:
            return href
        # Fall back to the primary href
        href = asset.get("href")
        if href:
            return href

    return None


async def search_optical_scenes(
    bbox: tuple[float, float, float, float],
    start_date: str,
    end_date: str,
    max_cloud: float = 30.0,
    limit: int = 20,
) -> list[dict]:
    """Search Copernicus STAC for Sentinel-2 L2A scenes in bbox + date range."""
    body = {
        "collections": ["sentinel-2-l2a"],
        "bbox": list(bbox),
        "datetime": f"{start_date}T00:00:00Z/{end_date}T23:59:59Z",
        "limit": limit,
        "query": {
            "eo:cloud_cover": {"lte": max_cloud},
        },
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
            cloud_cover = props.get("eo:cloud_cover")

            # Extract direct HTTPS URL for TCI
            tci_url = _extract_tci_url(feat)

            scene_meta = {
                "scene_id": scene_id,
                "title": title,
                "platform": platform,
                "acquisition_date": acq_date,
                "cloud_cover": cloud_cover,
                "bbox": list(bbox),
            }

            try:
                row = await conn.fetchrow(
                    """
                    INSERT INTO optical_scenes
                        (scene_id, title, platform, acquisition_date, footprint,
                         cloud_cover, file_path, status)
                    VALUES ($1, $2, $3, $4, ST_GeomFromEWKT($5), $6, $7, 'pending')
                    ON CONFLICT (scene_id) DO UPDATE SET
                        title = EXCLUDED.title,
                        cloud_cover = COALESCE(EXCLUDED.cloud_cover, optical_scenes.cloud_cover),
                        file_path = COALESCE(EXCLUDED.file_path, optical_scenes.file_path)
                    RETURNING id, status
                    """,
                    scene_id,
                    title,
                    platform,
                    datetime.fromisoformat(acq_date.replace("Z", "+00:00")) if acq_date else datetime.now(),
                    wkt,
                    cloud_cover,
                    tci_url,
                )
                scene_meta["id"] = row["id"]
                scene_meta["status"] = row["status"]
            except Exception as e:
                logger.error("Failed to insert optical scene %s: %s", scene_id, e)
                continue

            scenes.append(scene_meta)

    logger.info("STAC search returned %d optical scenes, inserted/updated %d", len(features), len(scenes))
    return scenes


async def download_optical_scene(scene_db_id: int) -> str:
    """Download TCI TIFF for an optical scene. Returns local path to the file."""
    db = get_db()

    async with db.acquire() as conn:
        scene = await conn.fetchrow(
            "SELECT id, scene_id, title, file_path, status FROM optical_scenes WHERE id = $1",
            scene_db_id,
        )
    if not scene:
        raise ValueError(f"Optical scene {scene_db_id} not found")

    file_path = scene["file_path"] or ""

    # If already downloaded to local path, reuse
    if scene["status"] in ("completed", "downloaded") and file_path.startswith("/"):
        return file_path

    # file_path stores the HTTPS URL from STAC
    if not file_path.startswith("http"):
        raise ValueError(f"Optical scene {scene_db_id} has no download URL — re-search to populate")

    download_url = file_path
    cache_dir = os.path.join(settings.sar_scene_cache_dir, "optical", str(scene_db_id))
    os.makedirs(cache_dir, exist_ok=True)
    tiff_filename = download_url.rsplit("/", 1)[-1].replace("/$value", "").replace("$value", "tci.tiff")
    if not tiff_filename.endswith((".tiff", ".tif")):
        tiff_filename = "tci.tiff"
    local_path = os.path.join(cache_dir, tiff_filename)

    async with db.acquire() as conn:
        await conn.execute(
            "UPDATE optical_scenes SET status = 'downloading' WHERE id = $1", scene_db_id
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

        logger.info(
            "Downloaded TCI for optical scene %d: %s (%.1f MB)",
            scene_db_id, local_path, total / 1e6,
        )

        async with db.acquire() as conn:
            await conn.execute(
                "UPDATE optical_scenes SET status = 'downloaded', file_path = $1 WHERE id = $2",
                local_path,
                scene_db_id,
            )

        return local_path

    except Exception as e:
        logger.error("Download failed for optical scene %d: %s", scene_db_id, e)
        async with db.acquire() as conn:
            await conn.execute(
                "UPDATE optical_scenes SET status = 'failed' WHERE id = $1", scene_db_id
            )
        raise


async def get_optical_scenes(
    bbox: tuple[float, float, float, float] | None = None,
    status: str | None = None,
) -> list[dict]:
    """List optical scenes from the database."""
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
            SELECT id, scene_id, title, platform, acquisition_date, cloud_cover,
                   status, created_at,
                   ST_AsGeoJSON(footprint)::json as footprint_geojson
            FROM optical_scenes {where}
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
            "cloud_cover": r["cloud_cover"],
            "status": r["status"],
            "footprint": r["footprint_geojson"],
        }
        for r in rows
    ]
