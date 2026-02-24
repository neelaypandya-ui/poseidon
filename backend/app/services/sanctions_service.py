"""OpenSanctions integration — screen vessels against global sanctions lists."""

import logging
from datetime import datetime, timezone, timedelta

import aiohttp

from app.config import settings
from app.database import get_db

logger = logging.getLogger("poseidon.sanctions")

OPENSANCTIONS_SEARCH_URL = "https://api.opensanctions.org/search/default"
OPENSANCTIONS_MATCH_URL = "https://api.opensanctions.org/match/default"

# Cache results for 24 hours
CACHE_TTL_HOURS = 24


async def screen_vessel(
    mmsi: int | None = None,
    imo: int | None = None,
    name: str | None = None,
    force_refresh: bool = False,
) -> dict:
    """Screen a vessel against OpenSanctions. Returns match results.

    Checks cache first; refreshes if stale or force_refresh=True.
    """
    db = get_db()

    # Check cache first
    if not force_refresh:
        cached = await _get_cached(db, mmsi, imo)
        if cached is not None:
            return cached

    # Query OpenSanctions
    matches = await _query_opensanctions(mmsi, imo, name)

    # Cache results
    await _cache_results(db, mmsi, imo, name, matches)

    return {
        "mmsi": mmsi,
        "imo": imo,
        "sanctioned": len(matches) > 0,
        "match_count": len(matches),
        "matches": matches,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


async def _get_cached(db, mmsi: int | None, imo: int | None) -> dict | None:
    """Return cached sanctions result if fresh enough."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=CACHE_TTL_HOURS)
    async with db.acquire() as conn:
        rows = None
        if mmsi:
            rows = await conn.fetch(
                "SELECT * FROM sanctions_matches WHERE mmsi = $1 AND checked_at > $2",
                mmsi, cutoff,
            )
        elif imo:
            rows = await conn.fetch(
                "SELECT * FROM sanctions_matches WHERE imo = $1 AND checked_at > $2",
                imo, cutoff,
            )

        if rows is None or len(rows) == 0:
            return None

        matches = [
            {
                "entity_id": r["entity_id"],
                "entity_name": r["entity_name"],
                "datasets": r["datasets"],
                "score": r["match_score"],
                "properties": r["properties"],
            }
            for r in rows
        ]

        return {
            "mmsi": mmsi,
            "imo": imo,
            "sanctioned": len(matches) > 0,
            "match_count": len(matches),
            "matches": matches,
            "checked_at": rows[0]["checked_at"].isoformat(),
            "cached": True,
        }


async def _query_opensanctions(
    mmsi: int | None, imo: int | None, name: str | None,
) -> list[dict]:
    """Query OpenSanctions API for vessel matches."""
    api_key = settings.opensanctions_api_key
    headers = {}
    if api_key:
        headers["Authorization"] = f"ApiKey {api_key}"

    matches = []

    # Search by name first (most likely to return results)
    queries = []
    if name:
        queries.append(name)
    if imo:
        queries.append(str(imo))
    if mmsi:
        queries.append(str(mmsi))

    if not queries:
        return []

    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for q in queries:
                params = {"q": q, "limit": 10}
                async with session.get(
                    OPENSANCTIONS_SEARCH_URL, params=params, headers=headers,
                ) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        logger.warning("OpenSanctions search failed (%d): %s", resp.status, text[:200])
                        continue

                    data = await resp.json()
                    results = data.get("results", [])

                    for r in results:
                        score = r.get("score", 0)
                        if score < 0.5:
                            continue

                        entity_id = r.get("id", "")
                        # Deduplicate
                        if any(m["entity_id"] == entity_id for m in matches):
                            continue

                        props = r.get("properties", {})
                        datasets = r.get("datasets", [])

                        matches.append({
                            "entity_id": entity_id,
                            "entity_name": r.get("caption", ""),
                            "datasets": datasets,
                            "score": round(score, 3),
                            "properties": {
                                "schema": r.get("schema", ""),
                                "countries": props.get("country", []),
                                "topics": r.get("topics", []),
                                "first_seen": r.get("first_seen"),
                                "last_seen": r.get("last_seen"),
                            },
                        })

    except Exception as e:
        logger.error("OpenSanctions query failed: %s", e)

    return matches


async def _cache_results(
    db, mmsi: int | None, imo: int | None, name: str | None, matches: list[dict],
):
    """Store match results in DB cache."""
    async with db.acquire() as conn:
        # Clear old entries for this vessel
        if mmsi:
            await conn.execute("DELETE FROM sanctions_matches WHERE mmsi = $1", mmsi)
        elif imo:
            await conn.execute("DELETE FROM sanctions_matches WHERE imo = $1", imo)

        if not matches:
            # Store a "no match" sentinel
            await conn.execute(
                """INSERT INTO sanctions_matches
                   (mmsi, imo, vessel_name, entity_id, entity_name, datasets, match_score, properties)
                   VALUES ($1, $2, $3, '__none__', 'No match', '{}', 0, '{}')""",
                mmsi, imo, name,
            )
            return

        for m in matches:
            await conn.execute(
                """INSERT INTO sanctions_matches
                   (mmsi, imo, vessel_name, entity_id, entity_name, datasets, match_score, properties)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)""",
                mmsi, imo, name,
                m["entity_id"], m["entity_name"], m["datasets"],
                m["score"],
                __import__("json").dumps(m["properties"]),
            )
