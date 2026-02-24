import asyncio
import json
import logging
import math
from datetime import datetime, timezone

import h3

from app.config import settings
from app.database import get_db, get_redis
from app.models.enums import ais_type_to_vessel_type
from app.services.coastline_service import classify_receiver

logger = logging.getLogger("poseidon.redis_buffer")

H3_RESOLUTION = 7


async def run_buffer_flush():
    logger.info("Redis buffer flusher starting...")
    while True:
        try:
            await asyncio.sleep(settings.buffer_flush_interval)
            await _flush_batch()
        except asyncio.CancelledError:
            logger.info("Buffer flush task cancelled")
            return
        except Exception as e:
            logger.error(f"Buffer flush error: {e}")
            await asyncio.sleep(1)


async def _flush_batch():
    r = get_redis()
    db = get_db()

    # Atomically grab up to batch_size items
    batch_size = settings.buffer_batch_size
    pipe = r.pipeline(transaction=True)
    pipe.lrange("ais:buffer", 0, batch_size - 1)
    pipe.ltrim("ais:buffer", batch_size, -1)
    results = await pipe.execute()

    items = results[0]
    if not items:
        return

    positions = []
    statics = []

    for raw in items:
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue

        if data.get("type") == "position":
            positions.append(data)
        elif data.get("type") == "static":
            statics.append(data)

    all_messages = positions + statics

    async with db.acquire() as conn:
        async with conn.transaction():
            if statics:
                await _detect_identity_changes(conn, statics)
                await _upsert_vessels_static(conn, statics)
            if positions:
                await _upsert_vessels_from_positions(conn, positions)
                await _insert_positions(conn, positions)
            if all_messages:
                await _insert_raw_messages(conn, all_messages)

    total = len(positions) + len(statics)
    if positions:
        logger.info(f"Flushed {len(positions)} positions, {len(statics)} statics ({total} total)")


async def _upsert_vessels_static(conn, statics: list[dict]):
    await conn.executemany(
        """
        INSERT INTO vessels (mmsi, imo, name, callsign, ship_type, ais_type_code,
                             dim_bow, dim_stern, dim_port, dim_starboard, destination, updated_at)
        VALUES ($1, $2, $3, $4, $5::vessel_type, $6, $7, $8, $9, $10, $11, NOW())
        ON CONFLICT (mmsi) DO UPDATE SET
            imo = COALESCE(EXCLUDED.imo, vessels.imo),
            name = COALESCE(EXCLUDED.name, vessels.name),
            callsign = COALESCE(EXCLUDED.callsign, vessels.callsign),
            ship_type = EXCLUDED.ship_type,
            ais_type_code = COALESCE(EXCLUDED.ais_type_code, vessels.ais_type_code),
            dim_bow = COALESCE(EXCLUDED.dim_bow, vessels.dim_bow),
            dim_stern = COALESCE(EXCLUDED.dim_stern, vessels.dim_stern),
            dim_port = COALESCE(EXCLUDED.dim_port, vessels.dim_port),
            dim_starboard = COALESCE(EXCLUDED.dim_starboard, vessels.dim_starboard),
            destination = COALESCE(EXCLUDED.destination, vessels.destination),
            updated_at = NOW()
        """,
        [
            (
                s["mmsi"],
                s.get("imo"),
                s.get("name"),
                s.get("callsign"),
                s.get("ship_type", "unknown"),
                s.get("ais_type_code"),
                s.get("dim_bow"),
                s.get("dim_stern"),
                s.get("dim_port"),
                s.get("dim_starboard"),
                s.get("destination"),
            )
            for s in statics
        ],
    )


async def _upsert_vessels_from_positions(conn, positions: list[dict]):
    # Ensure vessel rows exist for position data (dedup by mmsi)
    seen = {}
    for p in positions:
        mmsi = p["mmsi"]
        if mmsi not in seen:
            seen[mmsi] = p

    await conn.executemany(
        """
        INSERT INTO vessels (mmsi, name, updated_at)
        VALUES ($1, $2, NOW())
        ON CONFLICT (mmsi) DO UPDATE SET
            name = COALESCE(EXCLUDED.name, vessels.name),
            updated_at = NOW()
        """,
        [(mmsi, p.get("name")) for mmsi, p in seen.items()],
    )


async def _insert_positions(conn, positions: list[dict]):
    rows = []
    for p in positions:
        lat, lon = p["lat"], p["lon"]
        try:
            h3_index = h3.latlng_to_cell(lat, lon, H3_RESOLUTION)
        except Exception:
            h3_index = None

        ts = p.get("timestamp")
        if isinstance(ts, str):
            try:
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                ts = datetime.now(timezone.utc)

        rc = classify_receiver(lon, lat)

        rows.append((
            p["mmsi"],
            lon,
            lat,
            h3_index,
            p.get("sog"),
            p.get("cog"),
            p.get("heading"),
            p.get("nav_status"),
            p.get("rot"),
            ts,
            rc,
        ))

    await conn.executemany(
        """
        INSERT INTO vessel_positions
            (mmsi, geom, h3_index, sog, cog, heading, nav_status, rot, timestamp, receiver_class)
        VALUES
            ($1, ST_SetSRID(ST_MakePoint($2, $3), 4326), $4, $5, $6, $7, $8::nav_status, $9, $10, $11::receiver_class)
        """,
        rows,
    )


def _haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in nautical miles."""
    R_NM = 3440.065
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return 2 * R_NM * math.asin(math.sqrt(a))


async def _insert_raw_messages(conn, messages: list[dict]):
    """Store raw AIS messages with forensic flags."""
    rows = []
    for m in messages:
        raw_json = m.get("raw_json")
        if not raw_json:
            continue

        mmsi = m["mmsi"]
        msg_type = m.get("type", "unknown")
        lat = m.get("lat")
        lon = m.get("lon")
        sog = m.get("sog")

        ts = m.get("timestamp")
        if isinstance(ts, str):
            try:
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                ts = datetime.now(timezone.utc)

        # Forensic flags
        flag_impossible_speed = False
        if sog is not None and sog > 50.0 and abs(sog - 102.3) > 0.1:
            flag_impossible_speed = True

        flag_sart_on_non_sar = False
        nav = m.get("nav_status")
        if nav == "ais_sart":
            flag_sart_on_non_sar = True

        flag_no_identity = False
        if msg_type == "position" and not m.get("name"):
            flag_no_identity = True

        rc = classify_receiver(lon, lat) if lat is not None and lon is not None else "unknown"

        rows.append((
            mmsi,
            msg_type,
            json.dumps(raw_json),
            flag_impossible_speed,
            flag_sart_on_non_sar,
            flag_no_identity,
            rc,
            lat,
            lon,
            sog,
            ts,
        ))

    if not rows:
        return

    await conn.executemany(
        """
        INSERT INTO ais_raw_messages
            (mmsi, message_type, raw_json, flag_impossible_speed, flag_sart_on_non_sar,
             flag_no_identity, receiver_class, lat, lon, sog, timestamp)
        VALUES
            ($1, $2, $3::jsonb, $4, $5, $6, $7::receiver_class, $8, $9, $10, $11)
        """,
        rows,
    )


async def _detect_identity_changes(conn, statics: list[dict]):
    """Compare incoming static data against current vessel record and log changes."""
    for s in statics:
        mmsi = s["mmsi"]
        current = await conn.fetchrow(
            "SELECT name, ship_type, callsign, imo, destination FROM vessels WHERE mmsi = $1",
            mmsi,
        )
        if current is None:
            continue

        incoming_name = s.get("name")
        incoming_type = s.get("ship_type", "unknown")
        incoming_callsign = s.get("callsign")
        incoming_imo = s.get("imo")
        incoming_dest = s.get("destination")

        changed = False
        if incoming_name and incoming_name != current["name"]:
            changed = True
        if incoming_type != current["ship_type"]:
            changed = True
        if incoming_callsign and incoming_callsign != current["callsign"]:
            changed = True
        if incoming_imo and incoming_imo != current["imo"]:
            changed = True
        if incoming_dest and incoming_dest != current["destination"]:
            changed = True

        if changed:
            await conn.execute(
                """
                INSERT INTO vessel_identity_history (mmsi, name, ship_type, callsign, imo, destination)
                VALUES ($1, $2, $3::vessel_type, $4, $5, $6)
                """,
                mmsi,
                incoming_name or current["name"],
                incoming_type,
                incoming_callsign or current["callsign"],
                incoming_imo or current["imo"],
                incoming_dest or current["destination"],
            )
