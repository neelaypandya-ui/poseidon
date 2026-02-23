from fastapi import APIRouter, Query, HTTPException

from app.services.vessel_service import get_vessel_track

router = APIRouter()


@router.get("/vessels/{mmsi}/track")
async def vessel_track(
    mmsi: int,
    hours: int = Query(6, ge=1, le=72),
):
    track = await get_vessel_track(mmsi, hours)
    if not track:
        raise HTTPException(status_code=404, detail="No track data found")
    return {"mmsi": mmsi, "hours": hours, "points": len(track), "track": track}
