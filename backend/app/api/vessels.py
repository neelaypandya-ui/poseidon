from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import FileResponse

from app.services.vessel_service import get_all_vessels, get_vessel_detail
from app.services.history_service import get_mmsi_history
from app.services.sanctions_service import screen_vessel
from app.services.equasis_service import lookup_vessel
from app.services.report_service import generate_vessel_report

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


@router.get("/{mmsi}/history")
async def vessel_history(mmsi: int):
    history = await get_mmsi_history(mmsi)
    if not history:
        raise HTTPException(status_code=404, detail="Vessel not found")
    return history


@router.get("/{mmsi}/sanctions")
async def vessel_sanctions(mmsi: int, force: bool = Query(False)):
    """Screen vessel against OpenSanctions database."""
    vessel = await get_vessel_detail(mmsi)
    if not vessel:
        raise HTTPException(status_code=404, detail="Vessel not found")
    return await screen_vessel(
        mmsi=mmsi,
        imo=vessel.get("imo"),
        name=vessel.get("name"),
        force_refresh=force,
    )


@router.get("/{mmsi}/equasis")
async def vessel_equasis(mmsi: int, force: bool = Query(False)):
    """Look up vessel in Equasis registry."""
    vessel = await get_vessel_detail(mmsi)
    if not vessel:
        raise HTTPException(status_code=404, detail="Vessel not found")
    if not vessel.get("imo"):
        raise HTTPException(status_code=400, detail="Vessel has no IMO number for Equasis lookup")
    result = await lookup_vessel(vessel["imo"], force_refresh=force)
    if not result:
        raise HTTPException(status_code=404, detail="Not found in Equasis")
    return result


@router.get("/{mmsi}/report")
async def vessel_report(mmsi: int):
    """Generate and return a PDF intelligence report for this vessel."""
    try:
        filepath = await generate_vessel_report(mmsi)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return FileResponse(
        filepath,
        media_type="application/pdf",
        filename=filepath.rsplit("/", 1)[-1],
    )
