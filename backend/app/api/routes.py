"""
Route prediction API router.

Provides endpoints for predicting vessel routes and retrieving
stored predictions.
"""

import logging

from fastapi import APIRouter, Query, HTTPException

from app.services.route_prediction import predict_route, get_predictions

logger = logging.getLogger("poseidon.api.routes")

router = APIRouter()


@router.post("/predict/{mmsi}")
async def predict_vessel_route(
    mmsi: int,
    hours: float = Query(24, ge=1, le=168, description="Hours to project forward (1-168)"),
):
    """Predict a vessel's future route using dead reckoning.

    Projects the vessel's position forward based on current SOG/COG
    with confidence cones that widen over time.
    """
    try:
        result = await predict_route(mmsi, hours)
    except Exception as e:
        logger.error("Route prediction failed for MMSI %d: %s", mmsi, e)
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result


@router.get("/predictions/{mmsi}")
async def get_vessel_predictions(
    mmsi: int,
    limit: int = Query(5, ge=1, le=50, description="Max predictions to return"),
):
    """Get stored route predictions for a vessel."""
    try:
        predictions = await get_predictions(mmsi, limit)
    except Exception as e:
        logger.error("Failed to fetch predictions for MMSI %d: %s", mmsi, e)
        raise HTTPException(status_code=500, detail=f"Failed to fetch predictions: {str(e)}")

    return {"mmsi": mmsi, "count": len(predictions), "predictions": predictions}
