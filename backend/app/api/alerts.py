from fastapi import APIRouter, Query

from app.services.vessel_service import get_dark_vessel_alerts

router = APIRouter()


@router.get("/dark-vessels")
async def dark_vessel_alerts(
    status: str = Query("active", regex="^(active|resolved)$"),
):
    alerts = await get_dark_vessel_alerts(status)
    return {"count": len(alerts), "alerts": alerts}
