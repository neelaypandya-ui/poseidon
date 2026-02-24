"""Port webcam REST endpoints."""

import logging

from fastapi import APIRouter, Query

from app.services.webcam_service import get_webcams

logger = logging.getLogger("poseidon.api.webcams")

router = APIRouter()


@router.get("")
async def list_webcams(
    min_lon: float | None = Query(None),
    min_lat: float | None = Query(None),
    max_lon: float | None = Query(None),
    max_lat: float | None = Query(None),
    country: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    """List port webcams with optional bbox and country filters."""
    bbox = None
    if all(v is not None for v in [min_lon, min_lat, max_lon, max_lat]):
        bbox = (min_lon, min_lat, max_lon, max_lat)
    webcams = await get_webcams(bbox=bbox, country_code=country, limit=limit)
    return {"count": len(webcams), "webcams": webcams}
