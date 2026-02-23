import os
import logging

from fastapi import APIRouter, Query, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse

from app.services.sentinel2_service import (
    search_optical_scenes,
    download_optical_scene,
    get_optical_scenes,
)
from app.processors.timelapse import generate_timelapse
from app.database import get_db

logger = logging.getLogger("poseidon.api.optical")

router = APIRouter()


# ---------------------------------------------------------------------------
# Sentinel-2 scene search & management
# ---------------------------------------------------------------------------

@router.post("/search")
async def optical_search(
    min_lon: float = Query(...),
    min_lat: float = Query(...),
    max_lon: float = Query(...),
    max_lat: float = Query(...),
    start_date: str = Query(..., description="YYYY-MM-DD"),
    end_date: str = Query(..., description="YYYY-MM-DD"),
    max_cloud: float = Query(30.0, ge=0, le=100, description="Max cloud cover %"),
    limit: int = Query(20, ge=1, le=50),
):
    """Search Copernicus for Sentinel-2 L2A scenes within bbox, date range, and cloud cover."""
    bbox = (min_lon, min_lat, max_lon, max_lat)
    try:
        scenes = await search_optical_scenes(bbox, start_date, end_date, max_cloud, limit)
    except Exception as e:
        logger.error("Optical search failed: %s", e)
        raise HTTPException(status_code=502, detail=str(e))
    return {"count": len(scenes), "scenes": scenes}


@router.get("/scenes")
async def list_scenes(
    min_lon: float | None = Query(None),
    min_lat: float | None = Query(None),
    max_lon: float | None = Query(None),
    max_lat: float | None = Query(None),
    status: str | None = Query(None),
):
    """List optical scenes stored in the database."""
    bbox = None
    if all(v is not None for v in [min_lon, min_lat, max_lon, max_lat]):
        bbox = (min_lon, min_lat, max_lon, max_lat)
    scenes = await get_optical_scenes(bbox=bbox, status=status)
    return {"count": len(scenes), "scenes": scenes}


@router.post("/scenes/{scene_db_id}/download")
async def download_scene(scene_db_id: int, background_tasks: BackgroundTasks):
    """Trigger background download of TCI for a specific optical scene."""

    async def _download(sid: int):
        try:
            await download_optical_scene(sid)
            logger.info("Optical scene %d download completed", sid)
        except Exception as e:
            logger.error("Optical scene %d download failed: %s", sid, e)

    background_tasks.add_task(_download, scene_db_id)
    return {"status": "downloading", "scene_id": scene_db_id}


# ---------------------------------------------------------------------------
# Timelapse generation
# ---------------------------------------------------------------------------

@router.post("/timelapse")
async def create_timelapse(
    min_lon: float = Query(...),
    min_lat: float = Query(...),
    max_lon: float = Query(...),
    max_lat: float = Query(...),
    start_date: str = Query(..., description="YYYY-MM-DD"),
    end_date: str = Query(..., description="YYYY-MM-DD"),
    composite_type: str = Query("true-color", description="Composite type"),
    background_tasks: BackgroundTasks = None,
):
    """Create a timelapse job: finds optical scenes in bbox+dates and generates MP4."""
    bbox_wkt = (
        f"SRID=4326;POLYGON(("
        f"{min_lon} {min_lat}, {max_lon} {min_lat}, "
        f"{max_lon} {max_lat}, {min_lon} {max_lat}, "
        f"{min_lon} {min_lat}))"
    )

    db = get_db()
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO timelapse_jobs (bbox_geom, start_date, end_date, composite_type, status)
            VALUES (ST_GeomFromEWKT($1), $2, $3, $4, 'pending')
            RETURNING id
            """,
            bbox_wkt,
            f"{start_date}T00:00:00+00:00",
            f"{end_date}T23:59:59+00:00",
            composite_type,
        )
    job_id = row["id"]

    background_tasks.add_task(generate_timelapse, job_id)
    return {"status": "pending", "job_id": job_id}


@router.get("/timelapse/{job_id}")
async def get_timelapse_status(job_id: int):
    """Get the status of a timelapse job."""
    db = get_db()
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, status, scene_count, composite_type, output_path, created_at,
                   start_date, end_date
            FROM timelapse_jobs WHERE id = $1
            """,
            job_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail=f"Timelapse job {job_id} not found")

    return {
        "id": row["id"],
        "status": row["status"],
        "scene_count": row["scene_count"],
        "composite_type": row["composite_type"],
        "start_date": row["start_date"].isoformat() if row["start_date"] else None,
        "end_date": row["end_date"].isoformat() if row["end_date"] else None,
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "has_output": row["output_path"] is not None,
    }


@router.get("/timelapse/{job_id}/download")
async def download_timelapse(job_id: int):
    """Download the completed timelapse MP4 file."""
    db = get_db()
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT status, output_path FROM timelapse_jobs WHERE id = $1",
            job_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail=f"Timelapse job {job_id} not found")

    if row["status"] != "completed":
        raise HTTPException(
            status_code=409,
            detail=f"Timelapse job {job_id} is not completed (status: {row['status']})",
        )

    output_path = row["output_path"]
    if not output_path or not os.path.exists(output_path):
        raise HTTPException(status_code=404, detail="Timelapse MP4 file not found on disk")

    return FileResponse(
        path=output_path,
        media_type="video/mp4",
        filename=f"timelapse_{job_id}.mp4",
    )
