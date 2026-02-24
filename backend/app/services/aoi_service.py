"""Area of Interest management — create zones and query events."""

import logging

from app.database import get_db

logger = logging.getLogger("poseidon.aoi")


async def create_aoi(
    name: str,
    polygon_coords: list[list[float]],
    description: str | None = None,
    alert_vessel_types: list[str] | None = None,
    alert_min_risk_score: int = 0,
) -> dict:
    """Create a new Area of Interest from polygon coordinates.

    polygon_coords: list of [lon, lat] pairs forming a closed polygon.
    """
    if len(polygon_coords) < 3:
        raise ValueError("Polygon must have at least 3 points")

    # Close the ring if not already closed
    if polygon_coords[0] != polygon_coords[-1]:
        polygon_coords.append(polygon_coords[0])

    ring = ", ".join(f"{c[0]} {c[1]}" for c in polygon_coords)
    wkt = f"SRID=4326;POLYGON(({ring}))"

    db = get_db()
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO areas_of_interest (name, description, geom, alert_vessel_types, alert_min_risk_score)
            VALUES ($1, $2, ST_GeomFromEWKT($3), $4, $5)
            RETURNING id, name, description, active, created_at,
                      ST_AsGeoJSON(geom)::json AS geojson
            """,
            name, description, wkt,
            alert_vessel_types or [],
            alert_min_risk_score,
        )

    logger.info("Created AOI '%s' (id=%d)", name, row["id"])
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "active": row["active"],
        "geojson": row["geojson"],
        "created_at": row["created_at"].isoformat(),
    }


async def list_aois(active_only: bool = True) -> list[dict]:
    """List all areas of interest."""
    db = get_db()
    clause = "WHERE active = TRUE" if active_only else ""
    async with db.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT id, name, description, active, created_at,
                   alert_vessel_types, alert_min_risk_score,
                   ST_AsGeoJSON(geom)::json AS geojson,
                   (SELECT COUNT(*) FROM aoi_vessel_presence WHERE aoi_id = areas_of_interest.id) AS vessels_inside
            FROM areas_of_interest {clause}
            ORDER BY created_at DESC
            """
        )

    return [
        {
            "id": r["id"],
            "name": r["name"],
            "description": r["description"],
            "active": r["active"],
            "geojson": r["geojson"],
            "alert_vessel_types": r["alert_vessel_types"],
            "alert_min_risk_score": r["alert_min_risk_score"],
            "vessels_inside": r["vessels_inside"],
            "created_at": r["created_at"].isoformat(),
        }
        for r in rows
    ]


async def delete_aoi(aoi_id: int) -> bool:
    """Delete an area of interest."""
    db = get_db()
    async with db.acquire() as conn:
        result = await conn.execute("DELETE FROM areas_of_interest WHERE id = $1", aoi_id)
    return result.split()[-1] != "0"


async def get_aoi_events(aoi_id: int, limit: int = 100) -> list[dict]:
    """Get recent events for an AOI."""
    db = get_db()
    async with db.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, mmsi, event_type, vessel_name, ship_type,
                   lon, lat, sog, occurred_at
            FROM aoi_events
            WHERE aoi_id = $1
            ORDER BY occurred_at DESC
            LIMIT $2
            """,
            aoi_id, limit,
        )

    return [
        {
            "id": r["id"],
            "mmsi": r["mmsi"],
            "event_type": r["event_type"],
            "vessel_name": r["vessel_name"],
            "ship_type": r["ship_type"],
            "lon": r["lon"],
            "lat": r["lat"],
            "sog": r["sog"],
            "occurred_at": r["occurred_at"].isoformat(),
        }
        for r in rows
    ]


async def get_vessels_in_aoi(aoi_id: int) -> list[dict]:
    """Get vessels currently inside an AOI."""
    db = get_db()
    async with db.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT p.mmsi, p.entered_at,
                   v.name AS vessel_name, v.ship_type, v.imo,
                   ST_X(lvp.geom) AS lon, ST_Y(lvp.geom) AS lat,
                   lvp.sog, lvp.nav_status
            FROM aoi_vessel_presence p
            JOIN vessels v ON v.mmsi = p.mmsi
            LEFT JOIN latest_vessel_positions lvp ON lvp.mmsi = p.mmsi
            WHERE p.aoi_id = $1
            ORDER BY p.entered_at DESC
            """,
            aoi_id,
        )

    return [
        {
            "mmsi": r["mmsi"],
            "vessel_name": r["vessel_name"],
            "ship_type": r["ship_type"],
            "imo": r["imo"],
            "lon": float(r["lon"]) if r["lon"] else None,
            "lat": float(r["lat"]) if r["lat"] else None,
            "sog": float(r["sog"]) if r["sog"] else None,
            "nav_status": r["nav_status"],
            "entered_at": r["entered_at"].isoformat(),
        }
        for r in rows
    ]
