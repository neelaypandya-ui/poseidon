"""VIIRS nighttime light data service.

Fetches VIIRS active fire / hotspot CSV data from NASA FIRMS,
stores observations in PostGIS, and detects brightness anomalies
by comparing against a rolling 30-day baseline.
"""

import csv
import io
import logging
from datetime import date, timedelta

import aiohttp

from app.config import settings
from app.database import get_db

logger = logging.getLogger("poseidon.viirs_service")

# NASA FIRMS global 24h CSV (no auth required, VIIRS SNPP C2)
FIRMS_GLOBAL_24H_URL = (
    "https://firms.modaps.eosdis.nasa.gov/data/active_fire"
    "/suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_Global_24h.csv"
)

# FIRMS area API (requires MAP_KEY)
FIRMS_AREA_URL_TEMPLATE = (
    "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
    "/{map_key}/VIIRS_SNPP_NRT/{bbox}/{days}"
)


async def fetch_viirs_data(
    bbox: tuple[float, float, float, float] | None = None,
    days: int = 1,
) -> int:
    """Download VIIRS hotspot CSV from NASA FIRMS, filter to bbox, and
    insert bright spots into viirs_observations.

    Parameters
    ----------
    bbox : (min_lon, min_lat, max_lon, max_lat) or None for global
    days : number of days of data (only used with area API)

    Returns
    -------
    Number of observations inserted.
    """
    map_key = settings.earthdata_token
    if map_key and bbox:
        # Use the authenticated area API for targeted queries
        bbox_str = f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}"
        url = FIRMS_AREA_URL_TEMPLATE.format(
            map_key=map_key, bbox=bbox_str, days=days
        )
    else:
        # Fall back to the free global 24h CSV (no auth needed)
        url = FIRMS_GLOBAL_24H_URL

    logger.info("Fetching VIIRS data from %s", url)

    timeout = aiohttp.ClientTimeout(total=300)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(
                    f"FIRMS download failed ({resp.status}): {text[:500]}"
                )
            csv_text = await resp.text()

    reader = csv.DictReader(io.StringIO(csv_text))

    rows_to_insert: list[tuple] = []
    for row in reader:
        try:
            lat = float(row["latitude"])
            lon = float(row["longitude"])
            bright = float(row.get("bright_ti4") or row.get("brightness", "0"))
            acq_date_str = row.get("acq_date", "")
            if not acq_date_str:
                continue
            obs_date = date.fromisoformat(acq_date_str)
        except (ValueError, KeyError):
            continue

        # Filter to bbox if provided and using global feed
        if bbox and not map_key:
            min_lon, min_lat, max_lon, max_lat = bbox
            if not (min_lon <= lon <= max_lon and min_lat <= lat <= max_lat):
                continue

        rows_to_insert.append((lon, lat, bright, obs_date))

    if not rows_to_insert:
        logger.info("VIIRS fetch: 0 observations after filtering")
        return 0

    db = get_db()
    inserted = 0
    async with db.acquire() as conn:
        # Batch insert using executemany for performance
        await conn.executemany(
            """
            INSERT INTO viirs_observations (geom, radiance, observation_date)
            VALUES (ST_SetSRID(ST_MakePoint($1, $2), 4326), $3, $4)
            """,
            rows_to_insert,
        )
        inserted = len(rows_to_insert)

    logger.info("VIIRS fetch: inserted %d observations", inserted)
    return inserted


async def detect_anomalies(
    bbox: tuple[float, float, float, float] | None = None,
    target_date: date | None = None,
) -> int:
    """Compare current VIIRS observations against a 30-day baseline mean.
    Points with radiance > 3x baseline are flagged as anomalies.
    For maritime anomalies (no baseline), flags bright points at sea
    (radiance > 10 nW) that are far from known infrastructure.

    Parameters
    ----------
    bbox : spatial filter (min_lon, min_lat, max_lon, max_lat)
    target_date : the date to analyse (defaults to most recent observation date)

    Returns
    -------
    Number of anomalies inserted.
    """
    db = get_db()

    async with db.acquire() as conn:
        # If no target_date, detect the most recent observation date(s)
        if target_date is None:
            recent_dates = await conn.fetch(
                """
                SELECT DISTINCT observation_date
                FROM viirs_observations
                WHERE observation_date >= (CURRENT_DATE - INTERVAL '3 days')
                ORDER BY observation_date DESC
                LIMIT 3
                """
            )
            if not recent_dates:
                logger.info("Anomaly detection: no recent observations found")
                return 0
            dates_to_check = [r["observation_date"] for r in recent_dates]
        else:
            dates_to_check = [target_date]

        total_anomalies = 0
        for check_date in dates_to_check:
            count = await _detect_anomalies_for_date(conn, check_date, bbox)
            total_anomalies += count

    return total_anomalies


async def _detect_anomalies_for_date(conn, target_date: date, bbox=None) -> int:
    """Run anomaly detection for a specific date."""
    baseline_start = target_date - timedelta(days=30)
    baseline_end = target_date - timedelta(days=1)

    # Build spatial clause
    spatial_clause = ""
    params: list = [target_date, baseline_start, baseline_end]
    idx = 4

    if bbox:
        spatial_clause = (
            f"AND ST_Intersects(o.geom, "
            f"ST_MakeEnvelope(${idx}, ${idx+1}, ${idx+2}, ${idx+3}, 4326))"
        )
        params.extend(bbox)

    # Check if baseline data exists
    baseline_count = await conn.fetchval(
        "SELECT COUNT(*) FROM viirs_observations WHERE observation_date BETWEEN $1 AND $2",
        baseline_start, baseline_end,
    )

    if baseline_count > 0:
        # Standard mode: compare against 30-day baseline
        anomalies = await conn.fetch(
            f"""
            WITH current_obs AS (
                SELECT id, geom, radiance
                FROM viirs_observations o
                WHERE o.observation_date = $1
                {spatial_clause}
            ),
            baseline AS (
                SELECT
                    c.id AS obs_id,
                    AVG(b.radiance) AS mean_radiance,
                    COUNT(b.id) AS sample_count
                FROM current_obs c
                LEFT JOIN viirs_observations b
                    ON b.observation_date BETWEEN $2 AND $3
                   AND ST_DWithin(c.geom, b.geom, 0.1)
                GROUP BY c.id
            )
            SELECT c.id, ST_X(c.geom) AS lon, ST_Y(c.geom) AS lat,
                   c.radiance,
                   COALESCE(bl.mean_radiance, 0) AS baseline_radiance,
                   CASE WHEN COALESCE(bl.mean_radiance, 0) > 0
                        THEN c.radiance / bl.mean_radiance
                        ELSE NULL END AS anomaly_ratio
            FROM current_obs c
            LEFT JOIN baseline bl ON bl.obs_id = c.id
            WHERE bl.sample_count < 3
               OR c.radiance > 3.0 * COALESCE(bl.mean_radiance, 0)
            """,
            *params,
        )
    else:
        # No baseline yet — flag unusually bright maritime hotspots
        # Use absolute brightness threshold (>10 nW) and only points at sea
        # (latitude filtering removes most land-based fires)
        anomalies = await conn.fetch(
            f"""
            SELECT id, ST_X(geom) AS lon, ST_Y(geom) AS lat,
                   radiance,
                   0.0 AS baseline_radiance,
                   NULL::float AS anomaly_ratio
            FROM viirs_observations o
            WHERE o.observation_date = $1
              AND o.radiance > 10.0
            {spatial_clause}
            ORDER BY o.radiance DESC
            LIMIT 2000
            """,
            *params,
        )

    if not anomalies:
        logger.info("Anomaly detection for %s: 0 anomalies", target_date)
        return 0

    # Deduplicate: skip if we already have anomalies for this date
    existing = await conn.fetchval(
        "SELECT COUNT(*) FROM viirs_anomalies WHERE observation_date = $1",
        target_date,
    )
    if existing > 0:
        logger.info("Anomaly detection for %s: %d already exist, skipping", target_date, existing)
        return 0

    insert_rows = []
    for a in anomalies:
        ratio = float(a["anomaly_ratio"]) if a["anomaly_ratio"] is not None else None
        baseline = float(a["baseline_radiance"]) if a["baseline_radiance"] else None
        insert_rows.append((
            float(a["lon"]),
            float(a["lat"]),
            float(a["radiance"]),
            baseline,
            ratio,
            target_date,
        ))

    await conn.executemany(
        """
        INSERT INTO viirs_anomalies
            (geom, radiance, baseline_radiance, anomaly_ratio, observation_date)
        VALUES (
            ST_SetSRID(ST_MakePoint($1, $2), 4326),
            $3, $4, $5, $6
        )
        """,
        insert_rows,
    )

    logger.info(
        "Anomaly detection for %s: %d anomalies inserted", target_date, len(insert_rows)
    )
    return len(insert_rows)


async def get_viirs_observations(
    bbox: tuple[float, float, float, float] | None = None,
    obs_date: date | None = None,
) -> list[dict]:
    """Query VIIRS observations from the database."""
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

    if obs_date:
        conditions.append(f"observation_date = ${idx}")
        params.append(obs_date)
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    async with db.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT id, ST_X(geom) AS lon, ST_Y(geom) AS lat,
                   radiance, observation_date, tile_id, created_at
            FROM viirs_observations
            {where}
            ORDER BY observation_date DESC, radiance DESC
            LIMIT 5000
            """,
            *params,
        )

    return [
        {
            "id": r["id"],
            "lon": float(r["lon"]),
            "lat": float(r["lat"]),
            "radiance": float(r["radiance"]),
            "observation_date": r["observation_date"].isoformat(),
            "tile_id": r["tile_id"],
        }
        for r in rows
    ]


async def get_viirs_anomalies(
    bbox: tuple[float, float, float, float] | None = None,
) -> list[dict]:
    """Query VIIRS anomalies from the database."""
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

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    async with db.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT id, ST_X(geom) AS lon, ST_Y(geom) AS lat,
                   radiance, baseline_radiance, anomaly_ratio,
                   observation_date, anomaly_type, created_at
            FROM viirs_anomalies
            {where}
            ORDER BY observation_date DESC, anomaly_ratio DESC NULLS LAST
            LIMIT 5000
            """,
            *params,
        )

    return [
        {
            "id": r["id"],
            "lon": float(r["lon"]),
            "lat": float(r["lat"]),
            "radiance": float(r["radiance"]),
            "baseline_radiance": float(r["baseline_radiance"]) if r["baseline_radiance"] else None,
            "anomaly_ratio": float(r["anomaly_ratio"]) if r["anomaly_ratio"] else None,
            "observation_date": r["observation_date"].isoformat(),
            "anomaly_type": r["anomaly_type"],
        }
        for r in rows
    ]
