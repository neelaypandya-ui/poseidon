import asyncio
import json
import logging
from datetime import datetime, timezone

import h3

from app.config import settings
from app.database import get_db, get_redis
from app.models.enums import ais_type_to_vessel_type

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

    async with db.acquire() as conn:
        async with conn.transaction():
            if statics:
                await _upsert_vessels_static(conn, statics)
            if positions:
                await _upsert_vessels_from_positions(conn, positions)
                await _insert_positions(conn, positions)

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
        ))

    await conn.executemany(
        """
        INSERT INTO vessel_positions
            (mmsi, geom, h3_index, sog, cog, heading, nav_status, rot, timestamp)
        VALUES
            ($1, ST_SetSRID(ST_MakePoint($2, $3), 4326), $4, $5, $6, $7, $8::nav_status, $9, $10)
        """,
        rows,
    )
