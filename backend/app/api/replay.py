"""
Replay engine API router.

Provides endpoints for creating replay jobs, checking job status,
and retrieving frame data for historical vessel movement playback.
"""

import logging

from fastapi import APIRouter, Query, HTTPException

from app.services.replay_service import (
    create_replay_job,
    get_replay_data,
    get_replay_status,
)

logger = logging.getLogger("poseidon.api.replay")

router = APIRouter()


@router.post("/create")
async def create_replay(
    mmsi: int | None = Query(None, description="Optional MMSI to filter single vessel"),
    min_lon: float | None = Query(None, description="Bounding box minimum longitude"),
    min_lat: float | None = Query(None, description="Bounding box minimum latitude"),
    max_lon: float | None = Query(None, description="Bounding box maximum longitude"),
    max_lat: float | None = Query(None, description="Bounding box maximum latitude"),
    start_time: str = Query(..., description="Replay start time (ISO 8601)"),
    end_time: str = Query(..., description="Replay end time (ISO 8601)"),
    speed: float = Query(10, ge=1, le=100, description="Playback speed multiplier"),
):
    """Create a new replay job for historical vessel playback.

    Specify a time range and optionally filter by MMSI or bounding box.
    The returned job_id can be used to fetch frame data for animation.
    """
    # Build bbox if all coordinates provided
    bbox = None
    if all(v is not None for v in [min_lon, min_lat, max_lon, max_lat]):
        bbox = (min_lon, min_lat, max_lon, max_lat)

    try:
        job_id = await create_replay_job(
            mmsi=mmsi,
            bbox=bbox,
            start_time=start_time,
            end_time=end_time,
            speed=speed,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to create replay job: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to create replay job: {str(e)}")

    return {"job_id": job_id, "status": "created"}


@router.get("/{job_id}")
async def replay_status(job_id: int):
    """Get the current status of a replay job."""
    try:
        result = await get_replay_status(job_id)
    except Exception as e:
        logger.error("Failed to fetch replay status for job %d: %s", job_id, e)
        raise HTTPException(status_code=500, detail=f"Failed to fetch status: {str(e)}")

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result


@router.get("/{job_id}/data")
async def replay_data(job_id: int):
    """Get all frame data for a replay job.

    Returns vessel positions grouped into 1-minute time buckets,
    ready for frontend animation playback.
    """
    try:
        result = await get_replay_data(job_id)
    except Exception as e:
        logger.error("Failed to fetch replay data for job %d: %s", job_id, e)
        raise HTTPException(status_code=500, detail=f"Failed to fetch replay data: {str(e)}")

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result
