import asyncio
import logging

from fastapi import APIRouter, Query, HTTPException, BackgroundTasks

from app.services.sar_service import (
    search_scenes,
    download_scene,
    get_scenes,
    get_detections,
    get_ghost_vessels,
)
from app.processors.sar_cfar import process_scene, match_detections_to_ais

logger = logging.getLogger("poseidon.api.sar")

router = APIRouter()


@router.post("/search")
async def sar_search(
    min_lon: float = Query(...),
    min_lat: float = Query(...),
    max_lon: float = Query(...),
    max_lat: float = Query(...),
    start_date: str = Query(..., description="YYYY-MM-DD"),
    end_date: str = Query(..., description="YYYY-MM-DD"),
    limit: int = Query(10, ge=1, le=50),
):
    """Search Copernicus for Sentinel-1 GRD scenes within bbox and date range."""
    bbox = (min_lon, min_lat, max_lon, max_lat)
    try:
        scenes = await search_scenes(bbox, start_date, end_date, limit)
    except Exception as e:
        logger.error("SAR search failed: %s", e)
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
    """List SAR scenes stored in the database."""
    bbox = None
    if all(v is not None for v in [min_lon, min_lat, max_lon, max_lat]):
        bbox = (min_lon, min_lat, max_lon, max_lat)
    scenes = await get_scenes(bbox=bbox, status=status)
    return {"count": len(scenes), "scenes": scenes}


@router.post("/scenes/{scene_db_id}/process")
async def process_sar_scene(scene_db_id: int, background_tasks: BackgroundTasks):
    """Trigger download + CFAR processing for a specific scene."""

    async def _download_and_process(sid: int):
        try:
            await download_scene(sid)
            count = await process_scene(sid)
            await match_detections_to_ais(sid)
            logger.info("Scene %d fully processed: %d detections", sid, count)
        except Exception as e:
            logger.error("Scene %d processing pipeline failed: %s", sid, e)

    background_tasks.add_task(_download_and_process, scene_db_id)
    return {"status": "processing", "scene_id": scene_db_id}


@router.get("/detections")
async def list_detections(
    scene_id: int | None = Query(None),
    min_lon: float | None = Query(None),
    min_lat: float | None = Query(None),
    max_lon: float | None = Query(None),
    max_lat: float | None = Query(None),
    unmatched_only: bool = Query(False),
):
    """List SAR detections with optional filters."""
    bbox = None
    if all(v is not None for v in [min_lon, min_lat, max_lon, max_lat]):
        bbox = (min_lon, min_lat, max_lon, max_lat)
    detections = await get_detections(
        scene_id=scene_id, bbox=bbox, unmatched_only=unmatched_only
    )
    return {"count": len(detections), "detections": detections}


@router.get("/ghost-vessels")
async def list_ghost_vessels(
    min_lon: float | None = Query(None),
    min_lat: float | None = Query(None),
    max_lon: float | None = Query(None),
    max_lat: float | None = Query(None),
):
    """List unmatched SAR detections (ghost vessels)."""
    bbox = None
    if all(v is not None for v in [min_lon, min_lat, max_lon, max_lat]):
        bbox = (min_lon, min_lat, max_lon, max_lat)
    ghosts = await get_ghost_vessels(bbox=bbox)
    return {"count": len(ghosts), "ghost_vessels": ghosts}
