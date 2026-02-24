"""EEZ (Exclusive Economic Zone) boundary service.

Loads EEZ GeoJSON and provides spatial queries for vessel-EEZ interaction.
Uses shapely PreparedGeometry for fast point-in-polygon checks.
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timezone

from shapely.geometry import shape, Point
from shapely.prepared import prep

from app.database import get_db

logger = logging.getLogger("poseidon.eez_service")

# In-memory EEZ geometries for fast checks
_eez_zones: list[dict] = []
_prepared_geoms: list = []


async def init_eez_zones() -> int:
    """Load EEZ zones from DB into memory with PreparedGeometry for fast checks."""
    global _eez_zones, _prepared_geoms
    db = get_db()

    rows = await db.fetch(
        """
        SELECT id, name, sovereign, iso_ter1, mrgid,
               ST_AsGeoJSON(geom) as geojson
        FROM eez_zones
        WHERE geom IS NOT NULL
        """
    )

    _eez_zones = []
    _prepared_geoms = []

    for r in rows:
        geojson = json.loads(r["geojson"])
        geom = shape(geojson)
        _eez_zones.append({
            "id": r["id"],
            "name": r["name"],
            "sovereign": r["sovereign"],
            "iso_ter1": r["iso_ter1"],
            "mrgid": r["mrgid"],
            "geom": geom,
        })
        _prepared_geoms.append(prep(geom))

    logger.info("Loaded %d EEZ zones into memory", len(_eez_zones))
    return len(_eez_zones)


def find_eez_for_point(lon: float, lat: float) -> dict | None:
    """Find which EEZ a lon/lat point falls within. Returns zone dict or None."""
    pt = Point(lon, lat)
    for i, pg in enumerate(_prepared_geoms):
        if pg.contains(pt):
            z = _eez_zones[i]
            return {
                "id": z["id"],
                "name": z["name"],
                "sovereign": z["sovereign"],
                "iso_ter1": z["iso_ter1"],
            }
    return None


async def record_eez_event(
    mmsi: int, eez_id: int, eez_name: str,
    event_type: str, lon: float, lat: float,
    timestamp: datetime,
) -> int:
    """Record an EEZ entry or exit event."""
    db = get_db()
    row = await db.fetchrow(
        """
        INSERT INTO eez_entry_events (mmsi, eez_id, eez_name, event_type, geom, timestamp)
        VALUES ($1, $2, $3, $4, ST_SetSRID(ST_MakePoint($5, $6), 4326), $7)
        RETURNING id
        """,
        mmsi, eez_id, eez_name, event_type, lon, lat, timestamp,
    )
    return row["id"]


async def get_eez_events(
    mmsi: int | None = None,
    hours: int = 24,
    limit: int = 200,
) -> list[dict]:
    """Query recent EEZ entry/exit events."""
    db = get_db()
    conditions = ["timestamp > NOW() - make_interval(hours => $1)"]
    params: list = [hours]
    idx = 2

    if mmsi is not None:
        conditions.append(f"mmsi = ${idx}")
        params.append(mmsi)
        idx += 1

    where = " AND ".join(conditions)

    rows = await db.fetch(
        f"""
        SELECT id, mmsi, eez_id, eez_name, event_type,
               ST_X(geom) AS lon, ST_Y(geom) AS lat,
               timestamp, created_at
        FROM eez_entry_events
        WHERE {where}
        ORDER BY timestamp DESC
        LIMIT {limit}
        """,
        *params,
    )

    return [
        {
            "id": r["id"],
            "mmsi": r["mmsi"],
            "eez_id": r["eez_id"],
            "eez_name": r["eez_name"],
            "event_type": r["event_type"],
            "lon": float(r["lon"]) if r["lon"] else None,
            "lat": float(r["lat"]) if r["lat"] else None,
            "timestamp": r["timestamp"].isoformat(),
        }
        for r in rows
    ]


async def get_eez_zones_geojson() -> dict:
    """Return all EEZ zones as a GeoJSON FeatureCollection (simplified for API)."""
    db = get_db()
    rows = await db.fetch(
        """
        SELECT id, name, sovereign, iso_ter1, mrgid,
               ST_AsGeoJSON(ST_Simplify(geom, 0.01)) as geojson
        FROM eez_zones
        WHERE geom IS NOT NULL
        """
    )

    features = []
    for r in rows:
        features.append({
            "type": "Feature",
            "properties": {
                "id": r["id"],
                "name": r["name"],
                "sovereign": r["sovereign"],
                "iso_ter1": r["iso_ter1"],
                "mrgid": r["mrgid"],
            },
            "geometry": json.loads(r["geojson"]),
        })

    return {"type": "FeatureCollection", "features": features}
