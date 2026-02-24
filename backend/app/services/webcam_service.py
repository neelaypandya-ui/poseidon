"""Port webcam aggregation service.

Manages public port webcam streams and provides a catalog of
known maritime webcams around the world.
"""

import logging

from app.database import get_db

logger = logging.getLogger("poseidon.webcam_service")

# Seed data: verified public port/maritime webcams (real working URLs)
# Last verified: 2026-02-23
# Sources: skylinewebcams.com, webcamtaxi.com, earthcam.com, ptztv.com,
#           panama-canal.com (official Panama Canal Authority)
SEED_WEBCAMS = [
    # ── European Ports ──────────────────────────────────────────────
    {"name": "Port of Rotterdam", "lon": 4.002, "lat": 51.948, "country": "NL",
     "stream_url": "https://www.skylinewebcams.com/en/webcam/netherlands/south-holland/rotterdam/port.html",
     "port_locode": "NLRTM"},
    {"name": "Port of Hamburg", "lon": 9.938, "lat": 53.545, "country": "DE",
     "stream_url": "https://www.webcamtaxi.com/en/germany/hamburg/port-of-hamburg-cam.html",
     "port_locode": "DEHAM"},
    {"name": "Port of Genoa", "lon": 8.926, "lat": 44.409, "country": "IT",
     "stream_url": "https://www.skylinewebcams.com/en/webcam/italia/liguria/genova/porto-di-genova.html",
     "port_locode": "ITGOA"},
    {"name": "Port of Helsinki", "lon": 24.958, "lat": 60.167, "country": "FI",
     "stream_url": "https://www.skylinewebcams.com/en/webcam/finland/uusimaa/helsinki/port.html",
     "port_locode": None},
    {"name": "Port of Lisbon", "lon": -9.093, "lat": 38.693, "country": "PT",
     "stream_url": "https://www.skylinewebcams.com/en/webcam/portugal/lisboa/lisbon/port-of-lisbon.html",
     "port_locode": "PTLIS"},
    {"name": "Port of Piraeus", "lon": 23.636, "lat": 37.942, "country": "GR",
     "stream_url": "https://www.skylinewebcams.com/en/webcam/ellada/atiki/piraeus/port-of-piraeus.html",
     "port_locode": "GRPIR"},
    {"name": "Grand Harbour - Valletta", "lon": 14.517, "lat": 35.894, "country": "MT",
     "stream_url": "https://www.skylinewebcams.com/en/webcam/malta/malta/valletta/grand-harbour-entrance.html",
     "port_locode": None},
    {"name": "Barcelona - Port Olimpic", "lon": 2.198, "lat": 41.385, "country": "ES",
     "stream_url": "https://www.skylinewebcams.com/webcam/espana/cataluna/barcelona/port-vell.html",
     "port_locode": "ESBCN"},
    {"name": "Venice - St. Mark's Basin", "lon": 12.343, "lat": 45.433, "country": "IT",
     "stream_url": "https://www.skylinewebcams.com/en/webcam/italia/veneto/venezia/riva-schiavoni.html",
     "port_locode": "ITVCE"},
    {"name": "Naples - Posillipo", "lon": 14.199, "lat": 40.810, "country": "IT",
     "stream_url": "https://www.skylinewebcams.com/webcam/italia/campania/napoli/napoli-posillipo.html",
     "port_locode": None},
    {"name": "Port of Southampton", "lon": -1.404, "lat": 50.899, "country": "GB",
     "stream_url": "https://www.webcamtaxi.com/en/england/hampshire/southampton-cruiseship-cam.html",
     "port_locode": "GBSOU"},
    {"name": "Port of Amsterdam", "lon": 4.902, "lat": 52.382, "country": "NL",
     "stream_url": "https://www.webcamtaxi.com/en/netherlands/north-holland/port-of-amsterdam.html",
     "port_locode": None},
    # ── Maritime Chokepoints & Canals ───────────────────────────────
    {"name": "Strait of Gibraltar - Ceuta", "lon": -5.307, "lat": 35.889, "country": "ES",
     "stream_url": "https://www.earthcam.com/world/spain/ceuta/?cam=gibraltarCeuta",
     "port_locode": None},
    {"name": "Bosphorus Strait - Istanbul", "lon": 29.067, "lat": 41.085, "country": "TR",
     "stream_url": "https://www.webcamtaxi.com/en/turkey/istanbul/anadolu-hisar-cam.html",
     "port_locode": "TRIST"},
    {"name": "Kiel Canal - Brunsbuttel Lock", "lon": 9.138, "lat": 53.897, "country": "DE",
     "stream_url": "https://www.webcamtaxi.com/en/germany/schleswig-holstein/brunsbuttel-kiel-canal.html",
     "port_locode": None},
    {"name": "Panama Canal - Miraflores Locks", "lon": -79.547, "lat": 8.997, "country": "PA",
     "stream_url": "https://multimedia.panama-canal.com/Webcams/miraflores.html",
     "port_locode": None},
    # ── Americas ────────────────────────────────────────────────────
    {"name": "Port of Miami", "lon": -80.168, "lat": 25.774, "country": "US",
     "stream_url": "https://www.skylinewebcams.com/en/webcam/united-states/florida/miami/port.html",
     "port_locode": "USMIA"},
    {"name": "Port Everglades", "lon": -80.117, "lat": 26.093, "country": "US",
     "stream_url": "https://www.skylinewebcams.com/en/webcam/united-states/florida/fort-lauderdale/port-everglades.html",
     "port_locode": None},
    {"name": "New York Harbor", "lon": -74.044, "lat": 40.689, "country": "US",
     "stream_url": "https://www.skylinewebcams.com/en/webcam/united-states/new-york/new-york/new-york-city-harbor.html",
     "port_locode": "USNYC"},
    {"name": "Port of Baltimore", "lon": -76.578, "lat": 39.263, "country": "US",
     "stream_url": "https://www.skylinewebcams.com/en/webcam/united-states/maryland/baltimora/port.html",
     "port_locode": None},
    {"name": "Port of Los Angeles", "lon": -118.272, "lat": 33.739, "country": "US",
     "stream_url": "https://www.webcamtaxi.com/en/usa/california/port-of-los-angeles.html",
     "port_locode": "USLAX"},
    {"name": "Port Canaveral", "lon": -80.607, "lat": 28.408, "country": "US",
     "stream_url": "https://www.portcanaveralwebcam.com/",
     "port_locode": None},
    {"name": "Port of Vancouver", "lon": -123.108, "lat": 49.290, "country": "CA",
     "stream_url": "https://www.skylinewebcams.com/en/webcam/canada/british-columbia/vancouver/port.html",
     "port_locode": None},
    {"name": "Port of Halifax", "lon": -63.571, "lat": 44.643, "country": "CA",
     "stream_url": "https://www.skylinewebcams.com/en/webcam/canada/nova-scotia/halifax/halifax.html",
     "port_locode": None},
    # ── Asia ────────────────────────────────────────────────────────
    {"name": "Port of Singapore", "lon": 103.842, "lat": 1.264, "country": "SG",
     "stream_url": "https://www.webcamtaxi.com/en/singapore/singapore-city/port-cam.html",
     "port_locode": "SGSIN"},
    {"name": "Port of Yokohama", "lon": 139.651, "lat": 35.453, "country": "JP",
     "stream_url": "https://www.webcamtaxi.com/en/japan/kanagawa-prefecture/yokohama-port.html",
     "port_locode": "JPYOK"},
]


async def seed_webcams() -> int:
    """Seed the port_webcams table with known public streams.

    Replaces all existing webcams with the current verified seed data
    to ensure stale/broken URLs are removed.
    """
    db = get_db()

    # Remove old entries that are not in the current seed set
    seed_names = [cam["name"] for cam in SEED_WEBCAMS]
    await db.execute(
        "DELETE FROM port_webcams WHERE name != ALL($1::text[])",
        seed_names,
    )

    count = 0
    for cam in SEED_WEBCAMS:
        try:
            await db.execute(
                """
                INSERT INTO port_webcams
                    (name, stream_url, geom, country_code, port_locode, status)
                VALUES ($1, $2, ST_SetSRID(ST_MakePoint($3, $4), 4326), $5, $6, 'active')
                ON CONFLICT (name) DO UPDATE SET
                    stream_url = EXCLUDED.stream_url,
                    geom = EXCLUDED.geom,
                    country_code = EXCLUDED.country_code,
                    port_locode = EXCLUDED.port_locode
                """,
                cam["name"], cam["stream_url"],
                cam["lon"], cam["lat"],
                cam["country"], cam.get("port_locode"),
            )
            count += 1
        except Exception as e:
            logger.debug("Webcam seed skip: %s", e)

    logger.info("Seeded %d webcams", count)
    return count


async def get_webcams(
    bbox: tuple[float, float, float, float] | None = None,
    country_code: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """Query webcams with optional filters."""
    db = get_db()
    conditions: list[str] = ["status = 'active'"]
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

    where = " AND ".join(conditions)

    rows = await db.fetch(
        f"""
        SELECT id, name, stream_url, thumbnail_url,
               ST_X(geom) AS lon, ST_Y(geom) AS lat,
               country_code, port_locode, status, last_checked
        FROM port_webcams
        WHERE {where}
        ORDER BY name ASC
        LIMIT {limit}
        """,
        *params,
    )

    return [
        {
            "id": r["id"],
            "name": r["name"],
            "stream_url": r["stream_url"],
            "thumbnail_url": r["thumbnail_url"],
            "lon": float(r["lon"]) if r["lon"] else None,
            "lat": float(r["lat"]) if r["lat"] else None,
            "country_code": r["country_code"],
            "port_locode": r["port_locode"],
            "status": r["status"],
        }
        for r in rows
    ]
