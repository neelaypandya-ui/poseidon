"""Port REST endpoints."""

import logging

from fastapi import APIRouter, Query, HTTPException

from app.services.port_service import get_ports, get_ports_geojson, get_port_detail

logger = logging.getLogger("poseidon.api.ports")

router = APIRouter()


@router.get("")
async def list_ports(
    min_lon: float | None = Query(None),
    min_lat: float | None = Query(None),
    max_lon: float | None = Query(None),
    max_lat: float | None = Query(None),
    country: str | None = Query(None),
    name: str | None = Query(None),
    limit: int = Query(500, ge=1, le=2000),
):
    """List ports with optional bbox, country, and name filters."""
    bbox = None
    if all(v is not None for v in [min_lon, min_lat, max_lon, max_lat]):
        bbox = (min_lon, min_lat, max_lon, max_lat)
    ports = await get_ports(bbox=bbox, country_code=country, name_search=name, limit=limit)
    return {"count": len(ports), "ports": ports}


@router.get("/geojson")
async def ports_geojson(
    min_lon: float | None = Query(None),
    min_lat: float | None = Query(None),
    max_lon: float | None = Query(None),
    max_lat: float | None = Query(None),
):
    """Return ports as GeoJSON FeatureCollection."""
    bbox = None
    if all(v is not None for v in [min_lon, min_lat, max_lon, max_lat]):
        bbox = (min_lon, min_lat, max_lon, max_lat)
    return await get_ports_geojson(bbox=bbox)


@router.get("/{locode}")
async def port_detail(locode: str):
    """Get a single port by UN/LOCODE."""
    port = await get_port_detail(locode)
    if not port:
        raise HTTPException(status_code=404, detail=f"Port {locode} not found")
    return port
