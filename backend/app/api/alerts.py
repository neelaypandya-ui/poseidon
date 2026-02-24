from fastapi import APIRouter, Query, HTTPException

from app.services.vessel_service import get_dark_vessel_alerts
from app.services.spoof_service import get_spoof_clusters, get_spoof_cluster_detail
from app.services.correlation_service import find_spoof_dark_correlations, get_correlation_summary

router = APIRouter()


@router.get("/dark-vessels")
async def dark_vessel_alerts(
    status: str = Query("active", regex="^(active|resolved)$"),
):
    alerts = await get_dark_vessel_alerts(status)
    return {"count": len(alerts), "alerts": alerts}


@router.get("/spoof-clusters")
async def spoof_clusters(
    status: str = Query("active", regex="^(active|resolved)$"),
    limit: int = Query(50, ge=1, le=500),
):
    clusters = await get_spoof_clusters(status, limit)
    return {"count": len(clusters), "clusters": clusters}


@router.get("/spoof-clusters/{cluster_id}")
async def spoof_cluster_detail(cluster_id: int):
    detail = await get_spoof_cluster_detail(cluster_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Cluster not found")
    return detail


@router.get("/correlations")
async def spoof_dark_correlations(
    time_window_hours: float = Query(2.0, ge=0.5, le=24.0),
    spatial_radius_nm: float = Query(100.0, ge=10, le=500),
    limit: int = Query(50, ge=1, le=200),
):
    """Find spoof signals that coincide with nearby vessels going dark."""
    pairs = await find_spoof_dark_correlations(time_window_hours, spatial_radius_nm, limit)
    return {"count": len(pairs), "correlations": pairs}


@router.get("/correlations/summary")
async def correlation_summary():
    return await get_correlation_summary()
