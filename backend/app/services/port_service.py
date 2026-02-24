"""Port service for UN LOCODE port data."""

import json
import logging

from app.database import get_db

logger = logging.getLogger("poseidon.port_service")


async def get_ports(
    bbox: tuple[float, float, float, float] | None = None,
    country_code: str | None = None,
    name_search: str | None = None,
    limit: int = 500,
) -> list[dict]:
    """Query ports from the database with optional filters."""
    db = get_db()
    conditions: list[str] = []
    params: list = []
    idx = 1

    if bbox:
        conditions.append(
            f"ST_Intersects(geom, ST_MakeEnvelope(${idx}, ${idx+1}, ${idx+2}, ${idx+3}, 4326))"
        )
        params.extend(bbox)
        idx += 4

    if country_code:
        conditions.append(f"country_code = ${idx}")
        params.append(country_code.upper())
        idx += 1

    if name_search:
        conditions.append(f"name ILIKE ${idx}")
        params.append(f"%{name_search}%")
        idx += 1

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    rows = await db.fetch(
        f"""
        SELECT id, locode, name, country_code, country_name,
               ST_X(geom) AS lon, ST_Y(geom) AS lat,
               port_size, port_type
        FROM ports
        {where}
        ORDER BY port_size DESC, name ASC
        LIMIT {limit}
        """,
        *params,
    )

    return [
        {
            "id": r["id"],
            "locode": r["locode"],
            "name": r["name"],
            "country_code": r["country_code"],
            "country_name": r["country_name"],
            "lon": float(r["lon"]) if r["lon"] else None,
            "lat": float(r["lat"]) if r["lat"] else None,
            "port_size": r["port_size"],
            "port_type": r["port_type"],
        }
        for r in rows
    ]


async def get_ports_geojson(
    bbox: tuple[float, float, float, float] | None = None,
) -> dict:
    """Return ports as GeoJSON FeatureCollection."""
    ports = await get_ports(bbox=bbox, limit=2000)
    features = []
    for p in ports:
        if p["lon"] is None or p["lat"] is None:
            continue
        features.append({
            "type": "Feature",
            "properties": {
                "locode": p["locode"],
                "name": p["name"],
                "country_code": p["country_code"],
                "port_size": p["port_size"],
            },
            "geometry": {
                "type": "Point",
                "coordinates": [p["lon"], p["lat"]],
            },
        })
    return {"type": "FeatureCollection", "features": features}


async def get_port_detail(locode: str) -> dict | None:
    """Get a single port by UN/LOCODE."""
    db = get_db()
    r = await db.fetchrow(
        """
        SELECT id, locode, name, country_code, country_name,
               ST_X(geom) AS lon, ST_Y(geom) AS lat,
               port_size, port_type
        FROM ports WHERE locode = $1
        """,
        locode.upper(),
    )
    if not r:
        return None
    return {
        "id": r["id"],
        "locode": r["locode"],
        "name": r["name"],
        "country_code": r["country_code"],
        "country_name": r["country_name"],
        "lon": float(r["lon"]) if r["lon"] else None,
        "lat": float(r["lat"]) if r["lat"] else None,
        "port_size": r["port_size"],
        "port_type": r["port_type"],
    }
