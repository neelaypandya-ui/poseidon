from fastapi import APIRouter, Query, HTTPException

from app.services.vessel_service import get_all_vessels, get_vessel_detail

router = APIRouter()


@router.get("")
async def list_vessels(
    min_lon: float | None = Query(None),
    min_lat: float | None = Query(None),
    max_lon: float | None = Query(None),
    max_lat: float | None = Query(None),
    name: str | None = Query(None),
):
    bbox = None
    if all(v is not None for v in [min_lon, min_lat, max_lon, max_lat]):
        bbox = (min_lon, min_lat, max_lon, max_lat)

    vessels = await get_all_vessels(bbox=bbox, name_search=name)
    return {"count": len(vessels), "vessels": vessels}


@router.get("/{mmsi}")
async def vessel_detail(mmsi: int):
    vessel = await get_vessel_detail(mmsi)
    if not vessel:
        raise HTTPException(status_code=404, detail="Vessel not found")
    return vessel
