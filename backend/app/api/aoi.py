from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.aoi_service import (
    create_aoi, list_aois, delete_aoi, get_aoi_events, get_vessels_in_aoi,
)

router = APIRouter()


class AOICreate(BaseModel):
    name: str
    description: str | None = None
    polygon: list[list[float]]  # [[lon, lat], ...]
    alert_vessel_types: list[str] | None = None
    alert_min_risk_score: int = 0


@router.get("")
async def list_areas(active_only: bool = Query(True)):
    aois = await list_aois(active_only)
    return {"count": len(aois), "areas": aois}


@router.post("")
async def create_area(body: AOICreate):
    if len(body.polygon) < 3:
        raise HTTPException(status_code=400, detail="Polygon must have at least 3 points")
    return await create_aoi(
        name=body.name,
        polygon_coords=body.polygon,
        description=body.description,
        alert_vessel_types=body.alert_vessel_types,
        alert_min_risk_score=body.alert_min_risk_score,
    )


@router.delete("/{aoi_id}")
async def delete_area(aoi_id: int):
    deleted = await delete_aoi(aoi_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="AOI not found")
    return {"status": "deleted", "id": aoi_id}


@router.get("/{aoi_id}/events")
async def area_events(aoi_id: int, limit: int = Query(100, ge=1, le=1000)):
    events = await get_aoi_events(aoi_id, limit)
    return {"count": len(events), "events": events}


@router.get("/{aoi_id}/vessels")
async def area_vessels(aoi_id: int):
    vessels = await get_vessels_in_aoi(aoi_id)
    return {"count": len(vessels), "vessels": vessels}
