"""EEZ boundary REST endpoints."""

import logging

from fastapi import APIRouter, Query

from app.services.eez_service import get_eez_events, get_eez_zones_geojson

logger = logging.getLogger("poseidon.api.eez")

router = APIRouter()


@router.get("/zones")
async def list_eez_zones():
    """Return all EEZ zones as simplified GeoJSON."""
    geojson = await get_eez_zones_geojson()
    return geojson


@router.get("/events")
async def list_eez_events(
    mmsi: int | None = Query(None),
    hours: int = Query(24, ge=1, le=720),
    limit: int = Query(200, ge=1, le=1000),
):
    """Return recent EEZ entry/exit events."""
    events = await get_eez_events(mmsi=mmsi, hours=hours, limit=limit)
    return {"count": len(events), "events": events}
