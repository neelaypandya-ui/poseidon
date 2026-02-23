"""Acoustic event correlation API routes.

POST /api/v1/acoustic/fetch              -- trigger NOAA PMEL data fetch
GET  /api/v1/acoustic/events             -- list acoustic events
POST /api/v1/acoustic/correlate/{event_id} -- correlate event to AIS vessel
"""

import logging

from fastapi import APIRouter, Query, HTTPException, BackgroundTasks

from app.services.acoustic_service import (
    fetch_acoustic_events,
    correlate_acoustic_to_ais,
    get_acoustic_events,
)

logger = logging.getLogger("poseidon.api.acoustic")

router = APIRouter()


@router.post("/fetch")
async def acoustic_fetch(
    background_tasks: BackgroundTasks,
    min_lon: float | None = Query(None),
    min_lat: float | None = Query(None),
    max_lon: float | None = Query(None),
    max_lat: float | None = Query(None),
    days: int = Query(7, ge=1, le=30, description="Days of data to fetch"),
):
    """Trigger acoustic data fetch from NOAA PMEL.

    Runs in the background; returns immediately with status.
    Currently stubbed - will activate when PMEL data feed is available.
    """
    bbox = None
    if all(v is not None for v in [min_lon, min_lat, max_lon, max_lat]):
        bbox = (min_lon, min_lat, max_lon, max_lat)

    async def _fetch():
        try:
            count = await fetch_acoustic_events(bbox=bbox, days=days)
            logger.info("Acoustic fetch completed: %d events ingested", count)
        except Exception as e:
            logger.error("Acoustic fetch failed: %s", e)

    background_tasks.add_task(_fetch)
    return {"status": "fetching", "bbox": bbox, "days": days}


@router.get("/events")
async def list_events(
    min_lon: float | None = Query(None),
    min_lat: float | None = Query(None),
    max_lon: float | None = Query(None),
    max_lat: float | None = Query(None),
    hours: int = Query(48, ge=1, le=720, description="Lookback window in hours"),
):
    """List acoustic events with optional bbox and time filters."""
    bbox = None
    if all(v is not None for v in [min_lon, min_lat, max_lon, max_lat]):
        bbox = (min_lon, min_lat, max_lon, max_lat)

    try:
        events = await get_acoustic_events(bbox=bbox, hours=hours)
    except Exception as e:
        logger.error("Failed to query acoustic events: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

    return {"count": len(events), "events": events}


@router.post("/correlate/{event_id}")
async def correlate_event(
    event_id: int,
    time_window_hours: float = Query(
        2.0, ge=0.5, le=24, description="Time search window in hours"
    ),
    radius_km: float = Query(
        100.0, ge=10, le=500, description="Spatial search radius in km"
    ),
):
    """Correlate a specific acoustic event with the nearest AIS vessel.

    Searches vessel positions within the specified time and space window
    around the acoustic event.  Updates the event record with the match.
    """
    try:
        match = await correlate_acoustic_to_ais(
            event_id,
            time_window_hours=time_window_hours,
            radius_km=radius_km,
        )
    except Exception as e:
        logger.error("Acoustic correlation failed for event %d: %s", event_id, e)
        raise HTTPException(status_code=500, detail=str(e))

    if match is None:
        return {"matched": False, "event_id": event_id, "message": "No AIS vessel found in search window"}

    return {"matched": True, **match}
