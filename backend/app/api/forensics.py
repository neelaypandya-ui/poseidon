from fastapi import APIRouter, Query, HTTPException

from app.services.forensics_service import get_forensic_messages, get_forensic_summary
from app.services.assessment_service import compute_assessment

router = APIRouter()


@router.get("/messages/{mmsi}")
async def forensic_messages(
    mmsi: int,
    hours: int = Query(24, ge=1, le=720),
    flagged_only: bool = Query(False),
    limit: int = Query(200, ge=1, le=1000),
):
    messages = await get_forensic_messages(mmsi, hours, flagged_only, limit)
    return {"count": len(messages), "messages": messages}


@router.get("/summary/{mmsi}")
async def forensic_summary(
    mmsi: int,
    hours: int = Query(24, ge=1, le=720),
):
    return await get_forensic_summary(mmsi, hours)


@router.get("/assessment/{mmsi}")
async def forensic_assessment(mmsi: int):
    result = await compute_assessment(mmsi)
    if not result:
        raise HTTPException(status_code=404, detail="Vessel not found")
    return result
