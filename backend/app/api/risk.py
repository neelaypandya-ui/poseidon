"""
Risk scoring and report generation API router.

Provides endpoints for computing vessel risk scores, retrieving
scores, listing high-risk vessels, and generating PDF reports.
"""

import os
import logging

from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import FileResponse

from app.services.risk_scoring import (
    compute_risk_score,
    get_risk_score,
    get_high_risk_vessels,
)
from app.services.report_service import generate_vessel_report

logger = logging.getLogger("poseidon.api.risk")

router = APIRouter()


@router.post("/compute/{mmsi}")
async def compute_vessel_risk(mmsi: int):
    """Compute a comprehensive risk score for a vessel.

    Evaluates identity completeness, flag state risk, anomaly behavior,
    and dark vessel history to produce an overall risk score (0-100).
    """
    try:
        result = await compute_risk_score(mmsi)
    except Exception as e:
        logger.error("Risk scoring failed for MMSI %d: %s", mmsi, e)
        raise HTTPException(status_code=500, detail=f"Risk scoring failed: {str(e)}")

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result


@router.get("/score/{mmsi}")
async def get_vessel_risk_score(mmsi: int):
    """Get the latest stored risk score for a vessel."""
    try:
        result = await get_risk_score(mmsi)
    except Exception as e:
        logger.error("Failed to fetch risk score for MMSI %d: %s", mmsi, e)
        raise HTTPException(status_code=500, detail=f"Failed to fetch risk score: {str(e)}")

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No risk score found for MMSI {mmsi}. Run POST /compute/{mmsi} first.",
        )

    return result


@router.get("/high-risk")
async def list_high_risk_vessels(
    threshold: float = Query(50, ge=0, le=100, description="Minimum risk score threshold"),
):
    """Get all vessels with risk scores above the specified threshold."""
    try:
        vessels = await get_high_risk_vessels(threshold)
    except Exception as e:
        logger.error("Failed to fetch high-risk vessels: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to fetch high-risk vessels: {str(e)}")

    return {"threshold": threshold, "count": len(vessels), "vessels": vessels}


@router.get("/report/{mmsi}")
async def download_vessel_report(mmsi: int):
    """Generate and download a PDF intelligence report for a vessel.

    Produces a comprehensive report including vessel identity, risk assessment,
    track summary, dark activity, and SAR detections.
    """
    try:
        filepath = await generate_vessel_report(mmsi)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Report generation failed for MMSI %d: %s", mmsi, e)
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")

    if not os.path.exists(filepath):
        raise HTTPException(status_code=500, detail="Report file was not created")

    filename = os.path.basename(filepath)
    return FileResponse(
        path=filepath,
        media_type="application/pdf",
        filename=filename,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
