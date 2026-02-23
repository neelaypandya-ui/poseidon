import asyncio
import json
import logging
from datetime import datetime, timezone

import websockets

from app.config import settings
from app.database import get_redis
from app.models.enums import ais_type_to_vessel_type, NAV_STATUS_MAP

logger = logging.getLogger("poseidon.ais_stream")

AIS_STREAM_URL = "wss://stream.aisstream.io/v0/stream"

SUBSCRIPTION = {
    "APIKey": settings.aisstream_api_key,
    "BoundingBoxes": [[[-90, -180], [90, 180]]],
    "FilterMessageTypes": ["PositionReport", "ShipStaticData"],
}


def parse_position_report(msg: dict) -> dict | None:
    meta = msg.get("MetaData", {})
    pos_report = msg.get("Message", {}).get("PositionReport")
    if not pos_report:
        return None

    mmsi = meta.get("MMSI")
    if not mmsi:
        return None

    lat = pos_report.get("Latitude")
    lon = pos_report.get("Longitude")
    if lat is None or lon is None or (lat == 0 and lon == 0):
        return None
    if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
        return None

    nav_code = pos_report.get("NavigationalStatus")
    nav_status = NAV_STATUS_MAP.get(nav_code, None)

    ship_name = meta.get("ShipName", "").strip() or None
    time_str = meta.get("time_utc", "")

    return {
        "type": "position",
        "mmsi": mmsi,
        "lat": lat,
        "lon": lon,
        "sog": pos_report.get("Sog"),
        "cog": pos_report.get("Cog"),
        "heading": pos_report.get("TrueHeading"),
        "nav_status": nav_status.value if nav_status else None,
        "rot": pos_report.get("RateOfTurn"),
        "name": ship_name,
        "timestamp": time_str or datetime.now(timezone.utc).isoformat(),
    }


def parse_static_data(msg: dict) -> dict | None:
    meta = msg.get("MetaData", {})
    static = msg.get("Message", {}).get("ShipStaticData")
    if not static:
        return None

    mmsi = meta.get("MMSI")
    if not mmsi:
        return None

    dim = static.get("Dimension", {})
    ais_type = static.get("Type")

    return {
        "type": "static",
        "mmsi": mmsi,
        "imo": static.get("ImoNumber"),
        "name": static.get("Name", "").strip() or meta.get("ShipName", "").strip() or None,
        "callsign": static.get("CallSign", "").strip() or None,
        "ais_type_code": ais_type,
        "ship_type": ais_type_to_vessel_type(ais_type).value,
        "dim_bow": dim.get("A"),
        "dim_stern": dim.get("B"),
        "dim_port": dim.get("C"),
        "dim_starboard": dim.get("D"),
        "destination": static.get("Destination", "").strip() or None,
        "eta": static.get("Eta", {}).get("Month"),
    }


async def run_ais_stream():
    logger.info("AIS stream ingestor starting...")
    while True:
        try:
            await _connect_and_consume()
        except asyncio.CancelledError:
            logger.info("AIS stream task cancelled")
            return
        except Exception as e:
            logger.error(f"AIS stream error: {e}, reconnecting in 5s...")
            await asyncio.sleep(5)


async def _connect_and_consume():
    r = get_redis()
    async with websockets.connect(AIS_STREAM_URL, ping_interval=20) as ws:
        await ws.send(json.dumps(SUBSCRIPTION))
        logger.info("Connected to aisstream.io, subscription sent")

        msg_count = 0
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = msg.get("MessageType")

            if msg_type == "PositionReport":
                parsed = parse_position_report(msg)
            elif msg_type == "ShipStaticData":
                parsed = parse_static_data(msg)
            else:
                continue

            if parsed is None:
                continue

            encoded = json.dumps(parsed)

            # Dual Redis path: durable buffer + instant pub/sub
            pipe = r.pipeline(transaction=False)
            pipe.rpush("ais:buffer", encoded)
            pipe.publish("ais:live", encoded)
            await pipe.execute()

            msg_count += 1
            if msg_count % 1000 == 0:
                logger.info(f"AIS stream: {msg_count} messages processed")
