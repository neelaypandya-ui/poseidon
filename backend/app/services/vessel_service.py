from datetime import datetime, timezone, timedelta

from app.database import get_db


async def get_all_vessels(
    bbox: tuple[float, float, float, float] | None = None,
    name_search: str | None = None,
) -> list[dict]:
    db = get_db()

    query = """
        SELECT mmsi, name, ship_type::text, destination,
               ST_X(geom) as lon, ST_Y(geom) as lat,
               sog, cog, heading, nav_status::text, timestamp
        FROM latest_vessel_positions
        WHERE 1=1
    """
    params = []
    idx = 1

    if bbox:
        query += f"""
            AND ST_Intersects(geom, ST_MakeEnvelope(${idx}, ${idx+1}, ${idx+2}, ${idx+3}, 4326))
        """
        params.extend(bbox)
        idx += 4

    if name_search:
        query += f" AND name ILIKE ${idx}"
        params.append(f"%{name_search}%")
        idx += 1

    query += " ORDER BY timestamp DESC"

    rows = await db.fetch(query, *params)
    return [dict(r) for r in rows]


async def get_vessel_detail(mmsi: int) -> dict | None:
    db = get_db()

    row = await db.fetchrow(
        """
        SELECT v.mmsi, v.imo, v.name, v.callsign, v.ship_type::text,
               v.ais_type_code, v.dim_bow, v.dim_stern, v.dim_port, v.dim_starboard,
               v.destination, v.eta,
               ST_X(lv.geom) as lon, ST_Y(lv.geom) as lat,
               lv.sog, lv.cog, lv.heading, lv.nav_status::text,
               lv.timestamp as last_seen,
               (SELECT COUNT(*) FROM vessel_positions vp
                WHERE vp.mmsi = v.mmsi
                AND vp.timestamp > NOW() - INTERVAL '6 hours') as track_points_6h
        FROM vessels v
        LEFT JOIN latest_vessel_positions lv ON v.mmsi = lv.mmsi
        WHERE v.mmsi = $1
        """,
        mmsi,
    )

    if not row:
        return None
    return dict(row)


async def get_vessel_track(mmsi: int, hours: int = 6) -> list[dict]:
    db = get_db()

    rows = await db.fetch(
        """
        SELECT ST_X(geom) as lon, ST_Y(geom) as lat, sog, cog, timestamp
        FROM vessel_positions
        WHERE mmsi = $1 AND timestamp > NOW() - make_interval(hours => $2)
        ORDER BY timestamp ASC
        """,
        mmsi,
        hours,
    )

    return [dict(r) for r in rows]


async def get_dark_vessel_alerts(status: str = "active") -> list[dict]:
    db = get_db()

    rows = await db.fetch(
        """
        SELECT d.id, d.mmsi, d.status::text, v.name as vessel_name,
               v.ship_type::text as ship_type,
               ST_X(d.last_known_geom) as last_known_lon,
               ST_Y(d.last_known_geom) as last_known_lat,
               ST_X(d.predicted_geom) as predicted_lon,
               ST_Y(d.predicted_geom) as predicted_lat,
               d.last_sog, d.last_cog, d.gap_hours, d.search_radius_nm,
               d.last_seen_at, d.detected_at
        FROM dark_vessel_alerts d
        JOIN vessels v ON d.mmsi = v.mmsi
        WHERE d.status = $1::alert_status
        ORDER BY d.detected_at DESC
        """,
        status,
    )

    return [dict(r) for r in rows]
