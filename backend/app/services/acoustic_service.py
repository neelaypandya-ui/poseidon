"""NOAA PMEL acoustic event correlation service.

Manages acoustic events from hydrophone arrays and correlates them
with AIS vessel positions to identify vessel-generated noise signatures.

The actual NOAA PMEL data feed integration is stubbed pending a
public real-time API. The table structure and correlation logic are
fully implemented for when data becomes available.
"""

import logging
from datetime import datetime, timezone, timedelta

from app.database import get_db

logger = logging.getLogger("poseidon.acoustic_service")

# Radius in metres for ST_DWithin geographic queries
DEFAULT_CORRELATION_RADIUS_M = 100_000  # 100 km


async def fetch_acoustic_events(
    bbox: tuple[float, float, float, float] | None = None,
    days: int = 7,
) -> int:
    """Fetch acoustic events from NOAA PMEL hydrophone event data.

    Parameters
    ----------
    bbox : optional spatial bounding box (min_lon, min_lat, max_lon, max_lat)
    days : number of days of data to fetch

    Returns
    -------
    Number of events ingested.

    Notes
    -----
    NOAA PMEL does not currently expose a public real-time API for
    hydrophone event data.  This stub is ready for integration when
    access becomes available (e.g., via a scheduled file drop or
    partnership data feed).
    """
    logger.info(
        "NOAA PMEL integration pending - no public real-time API available. "
        "bbox=%s, days=%d",
        bbox, days,
    )
    return 0


async def correlate_acoustic_to_ais(
    event_id: int,
    time_window_hours: float = 2,
    radius_km: float = 100,
) -> dict | None:
    """Find the closest AIS vessel within a time/space window of an
    acoustic event.

    Uses ST_DWithin with geography cast for accurate distance on the
    WGS84 ellipsoid.

    Parameters
    ----------
    event_id : id of the acoustic event to correlate
    time_window_hours : hours before/after event_time to search for AIS positions
    radius_km : spatial search radius in kilometres

    Returns
    -------
    dict with match details, or None if no vessel is found.
    """
    db = get_db()
    radius_m = radius_km * 1000.0

    async with db.acquire() as conn:
        # Fetch the acoustic event
        event = await conn.fetchrow(
            """
            SELECT id, geom, event_time, source, event_type, magnitude
            FROM acoustic_events
            WHERE id = $1
            """,
            event_id,
        )

        if not event:
            logger.warning("Acoustic event %d not found", event_id)
            return None

        if event["geom"] is None or event["event_time"] is None:
            logger.warning("Acoustic event %d missing geom or time", event_id)
            return None

        # Find the closest AIS position within the time/space window
        match = await conn.fetchrow(
            """
            SELECT vp.mmsi,
                   v.name AS vessel_name,
                   v.ship_type::text AS ship_type,
                   ST_X(vp.geom) AS vessel_lon,
                   ST_Y(vp.geom) AS vessel_lat,
                   vp.sog,
                   vp.cog,
                   vp.timestamp AS ais_time,
                   ST_Distance(
                       ae.geom::geography,
                       vp.geom::geography
                   ) AS distance_m,
                   EXTRACT(EPOCH FROM (vp.timestamp - ae.event_time)) AS time_delta_s
            FROM acoustic_events ae
            CROSS JOIN LATERAL (
                SELECT mmsi, geom, sog, cog, timestamp
                FROM vessel_positions
                WHERE timestamp BETWEEN ae.event_time - make_interval(hours => $2)
                                     AND ae.event_time + make_interval(hours => $2)
                  AND ST_DWithin(
                        geom::geography,
                        ae.geom::geography,
                        $3
                  )
                ORDER BY ST_Distance(geom::geography, ae.geom::geography)
                LIMIT 1
            ) vp
            LEFT JOIN vessels v ON v.mmsi = vp.mmsi
            WHERE ae.id = $1
            """,
            event_id,
            time_window_hours,
            radius_m,
        )

        if not match:
            logger.info("No AIS match for acoustic event %d", event_id)
            return None

        # Compute a correlation confidence based on distance and time proximity
        dist_m = float(match["distance_m"])
        time_delta = abs(float(match["time_delta_s"]))
        # Confidence decays linearly with distance and time
        dist_conf = max(0.0, 1.0 - (dist_m / radius_m))
        time_conf = max(0.0, 1.0 - (time_delta / (time_window_hours * 3600)))
        correlation_confidence = round((dist_conf + time_conf) / 2.0, 4)

        # Update the acoustic event with the correlation
        await conn.execute(
            """
            UPDATE acoustic_events
            SET correlated_mmsi = $1,
                correlation_confidence = $2
            WHERE id = $3
            """,
            match["mmsi"],
            correlation_confidence,
            event_id,
        )

    result = {
        "event_id": event_id,
        "mmsi": match["mmsi"],
        "vessel_name": match["vessel_name"],
        "ship_type": match["ship_type"],
        "vessel_lon": float(match["vessel_lon"]),
        "vessel_lat": float(match["vessel_lat"]),
        "sog": float(match["sog"]) if match["sog"] is not None else None,
        "distance_m": round(dist_m, 1),
        "time_delta_s": round(float(match["time_delta_s"]), 1),
        "ais_time": match["ais_time"].isoformat(),
        "correlation_confidence": correlation_confidence,
    }

    logger.info(
        "Acoustic event %d correlated to MMSI %d (dist=%.0fm, conf=%.2f)",
        event_id, match["mmsi"], dist_m, correlation_confidence,
    )
    return result


async def get_acoustic_events(
    bbox: tuple[float, float, float, float] | None = None,
    hours: int = 48,
) -> list[dict]:
    """Query acoustic events from the database.

    Parameters
    ----------
    bbox : optional spatial bounding box (min_lon, min_lat, max_lon, max_lat)
    hours : return events from the last N hours (default 48)

    Returns
    -------
    List of event dicts.
    """
    db = get_db()
    conditions: list[str] = ["event_time > NOW() - make_interval(hours => $1)"]
    params: list = [hours]
    idx = 2

    if bbox:
        conditions.append(
            f"ST_Intersects(geom, ST_MakeEnvelope(${idx}, ${idx+1}, ${idx+2}, ${idx+3}, 4326))"
        )
        params.extend(bbox)
        idx += 4

    where = "WHERE " + " AND ".join(conditions)

    rows = await db.fetch(
        f"""
        SELECT id, source, event_type,
               ST_X(geom) AS lon, ST_Y(geom) AS lat,
               bearing, magnitude, event_time,
               correlated_mmsi, correlation_confidence,
               created_at
        FROM acoustic_events
        {where}
        ORDER BY event_time DESC
        LIMIT 5000
        """,
        *params,
    )

    return [
        {
            "id": r["id"],
            "source": r["source"],
            "event_type": r["event_type"],
            "lon": float(r["lon"]) if r["lon"] is not None else None,
            "lat": float(r["lat"]) if r["lat"] is not None else None,
            "bearing": float(r["bearing"]) if r["bearing"] is not None else None,
            "magnitude": float(r["magnitude"]) if r["magnitude"] is not None else None,
            "event_time": r["event_time"].isoformat(),
            "correlated_mmsi": r["correlated_mmsi"],
            "correlation_confidence": (
                float(r["correlation_confidence"])
                if r["correlation_confidence"] is not None
                else None
            ),
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]
