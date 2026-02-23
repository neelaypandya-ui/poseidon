"""VIIRS nighttime light API routes.

POST /api/v1/viirs/fetch         — manually trigger VIIRS data fetch for bbox
GET  /api/v1/viirs/observations  — list observations (bbox + date filter)
GET  /api/v1/viirs/anomalies     — list anomalies (bbox filter)
"""

import logging
from datetime import date

from fastapi import APIRouter, Query, HTTPException, BackgroundTasks

from app.services.viirs_service import (
    fetch_viirs_data,
    detect_anomalies,
    get_viirs_observations,
    get_viirs_anomalies,
)

logger = logging.getLogger("poseidon.api.viirs")

router = APIRouter()


@router.post("/fetch")
async def viirs_fetch(
    background_tasks: BackgroundTasks,
    min_lon: float | None = Query(None),
    min_lat: float | None = Query(None),
    max_lon: float | None = Query(None),
    max_lat: float | None = Query(None),
    days: int = Query(1, ge=1, le=10),
):
    """Manually trigger VIIRS data fetch. Optionally filter by bbox.

    Fetch runs in the background; returns immediately with status.
    """
    bbox = None
    if all(v is not None for v in [min_lon, min_lat, max_lon, max_lat]):
        bbox = (min_lon, min_lat, max_lon, max_lat)

    async def _fetch_and_detect():
        try:
            inserted = await fetch_viirs_data(bbox=bbox, days=days)
            logger.info("Manual VIIRS fetch: %d observations ingested", inserted)
            if inserted > 0:
                anomaly_count = await detect_anomalies(bbox=bbox)
                logger.info("Manual VIIRS anomaly detection: %d anomalies", anomaly_count)
        except Exception as e:
            logger.error("Manual VIIRS fetch failed: %s", e)

    background_tasks.add_task(_fetch_and_detect)
    return {"status": "fetching", "bbox": bbox, "days": days}


@router.get("/observations")
async def list_observations(
    min_lon: float | None = Query(None),
    min_lat: float | None = Query(None),
    max_lon: float | None = Query(None),
    max_lat: float | None = Query(None),
    date: date | None = Query(None, description="YYYY-MM-DD"),
):
    """List VIIRS observations with optional bbox and date filters."""
    bbox = None
    if all(v is not None for v in [min_lon, min_lat, max_lon, max_lat]):
        bbox = (min_lon, min_lat, max_lon, max_lat)

    try:
        observations = await get_viirs_observations(bbox=bbox, obs_date=date)
    except Exception as e:
        logger.error("Failed to query VIIRS observations: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

    return {"count": len(observations), "observations": observations}


@router.get("/anomalies")
async def list_anomalies(
    min_lon: float | None = Query(None),
    min_lat: float | None = Query(None),
    max_lon: float | None = Query(None),
    max_lat: float | None = Query(None),
):
    """List VIIRS brightness anomalies with optional bbox filter."""
    bbox = None
    if all(v is not None for v in [min_lon, min_lat, max_lon, max_lat]):
        bbox = (min_lon, min_lat, max_lon, max_lat)

    try:
        anomalies = await get_viirs_anomalies(bbox=bbox)
    except Exception as e:
        logger.error("Failed to query VIIRS anomalies: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

    return {"count": len(anomalies), "anomalies": anomalies}
