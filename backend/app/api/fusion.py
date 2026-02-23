"""Bayesian signal fusion API routes.

POST /api/v1/fusion/compute/{mmsi}  -- compute fusion for a single vessel
GET  /api/v1/fusion/history/{mmsi}  -- get fusion history for a vessel
GET  /api/v1/fusion/batch           -- compute fusion for all recently active vessels
"""

import logging

from fastapi import APIRouter, Query, HTTPException

from app.database import get_db
from app.services.fusion_service import compute_fusion, get_fusion_history

logger = logging.getLogger("poseidon.api.fusion")

router = APIRouter()


@router.post("/compute/{mmsi}")
async def fusion_compute(mmsi: int):
    """Compute Bayesian signal fusion for a single vessel.

    Combines AIS freshness, SAR detections, VIIRS anomalies, and
    acoustic correlations into a single posterior confidence score.
    """
    try:
        result = await compute_fusion(mmsi)
    except Exception as e:
        logger.error("Fusion compute failed for MMSI %d: %s", mmsi, e)
        raise HTTPException(status_code=500, detail=str(e))

    return result


@router.get("/history/{mmsi}")
async def fusion_history(
    mmsi: int,
    limit: int = Query(20, ge=1, le=200, description="Max results to return"),
):
    """Get fusion score history for a vessel, most recent first."""
    try:
        history = await get_fusion_history(mmsi, limit=limit)
    except Exception as e:
        logger.error("Fusion history failed for MMSI %d: %s", mmsi, e)
        raise HTTPException(status_code=500, detail=str(e))

    return {"count": len(history), "mmsi": mmsi, "history": history}


@router.get("/batch")
async def fusion_batch(
    hours: int = Query(24, ge=1, le=168, description="Active window in hours"),
):
    """Compute fusion for all vessels with positions in the last N hours.

    Returns a list of fusion results for every vessel that has reported
    at least one AIS position within the specified window.
    """
    db = get_db()

    try:
        rows = await db.fetch(
            """
            SELECT DISTINCT mmsi
            FROM latest_vessel_positions
            WHERE timestamp > NOW() - make_interval(hours => $1)
            """,
            hours,
        )
    except Exception as e:
        logger.error("Fusion batch vessel query failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

    results = []
    errors = 0
    for row in rows:
        try:
            result = await compute_fusion(row["mmsi"])
            results.append(result)
        except Exception as e:
            logger.warning("Fusion batch skipped MMSI %d: %s", row["mmsi"], e)
            errors += 1

    logger.info(
        "Fusion batch complete: %d computed, %d errors out of %d vessels",
        len(results), errors, len(rows),
    )

    return {
        "count": len(results),
        "errors": errors,
        "total_vessels": len(rows),
        "results": results,
    }
