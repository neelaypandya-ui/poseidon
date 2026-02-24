"""Equasis vessel registry lookup — ownership, inspections, flag history."""

import logging
import re
from datetime import datetime, timezone, timedelta

import aiohttp

from app.config import settings
from app.database import get_db

logger = logging.getLogger("poseidon.equasis")

EQUASIS_LOGIN_URL = "https://www.equasis.org/EquasisWeb/authen/HomePage"
EQUASIS_SEARCH_URL = "https://www.equasis.org/EquasisWeb/restricted/Search"
EQUASIS_SHIP_URL = "https://www.equasis.org/EquasisWeb/restricted/ShipInfo"

CACHE_TTL_HOURS = 72  # Cache for 3 days


async def lookup_vessel(imo: int, force_refresh: bool = False) -> dict | None:
    """Look up vessel details from Equasis by IMO number.

    Returns cached results if available and fresh. Otherwise scrapes Equasis.
    """
    if not imo:
        return None

    db = get_db()

    # Check cache
    if not force_refresh:
        cached = await _get_cached(db, imo)
        if cached is not None:
            return cached

    # Scrape Equasis
    email = settings.equasis_email
    password = settings.equasis_password
    if not email or not password:
        logger.warning("Equasis credentials not configured")
        return None

    try:
        result = await _scrape_equasis(email, password, imo)
        if result:
            await _cache_result(db, imo, result)
            return result
    except Exception as e:
        logger.error("Equasis lookup failed for IMO %d: %s", imo, e)

    return None


async def _get_cached(db, imo: int) -> dict | None:
    """Return cached Equasis data if fresh."""
    import json as _json

    cutoff = datetime.now(timezone.utc) - timedelta(hours=CACHE_TTL_HOURS)
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM equasis_cache WHERE imo = $1 AND fetched_at > $2",
            imo, cutoff,
        )
        if not row:
            return None

        # asyncpg returns JSONB as strings — parse them
        inspections = row["inspections"]
        if isinstance(inspections, str):
            inspections = _json.loads(inspections)
        flag_history = row["flag_history"]
        if isinstance(flag_history, str):
            flag_history = _json.loads(flag_history)

        return {
            "imo": imo,
            "vessel_name": row["vessel_name"],
            "flag_state": row["flag_state"],
            "gross_tonnage": row["gross_tonnage"],
            "deadweight": row["deadweight"],
            "year_built": row["year_built"],
            "registered_owner": row["registered_owner"],
            "operator": row["operator"],
            "class_society": row["class_society"],
            "inspections": inspections or [],
            "flag_history": flag_history or [],
            "fetched_at": row["fetched_at"].isoformat(),
            "cached": True,
        }


async def _scrape_equasis(email: str, password: str, imo: int) -> dict | None:
    """Authenticate and scrape vessel details from Equasis."""
    timeout = aiohttp.ClientTimeout(total=60)
    jar = aiohttp.CookieJar()

    async with aiohttp.ClientSession(timeout=timeout, cookie_jar=jar) as session:
        # Login
        login_data = {
            "j_email": email,
            "j_password": password,
            "submit": "Login",
        }
        async with session.post(EQUASIS_LOGIN_URL, data=login_data) as resp:
            if resp.status != 200:
                logger.warning("Equasis login failed with status %d", resp.status)
                return None

        # Search by IMO
        search_data = {"P_IMO": str(imo)}
        async with session.post(EQUASIS_SEARCH_URL, data=search_data) as resp:
            if resp.status != 200:
                return None
            html = await resp.text()

        # Also try the ship info page directly
        async with session.get(
            EQUASIS_SHIP_URL, params={"P_IMO": str(imo)},
        ) as resp:
            if resp.status == 200:
                html = await resp.text()

    return _parse_vessel_html(imo, html)


def _parse_vessel_html(imo: int, html: str) -> dict | None:
    """Extract vessel details from Equasis HTML response."""
    if not html or "No ship found" in html or len(html) < 500:
        return None

    def _extract(pattern: str, text: str, default=None):
        m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        return m.group(1).strip() if m else default

    vessel_name = _extract(r'Ship\s*name[^<]*</td>\s*<td[^>]*>([^<]+)', html)
    flag_state = _extract(r'Flag[^<]*</td>\s*<td[^>]*>([^<]+)', html)
    gross_tonnage = _extract(r'Gross\s*tonnage[^<]*</td>\s*<td[^>]*>([\d,.]+)', html)
    deadweight = _extract(r'Deadweight[^<]*</td>\s*<td[^>]*>([\d,.]+)', html)
    year_built = _extract(r'Year\s*of\s*build[^<]*</td>\s*<td[^>]*>(\d{4})', html)
    registered_owner = _extract(r'Registered\s*owner[^<]*</td>\s*<td[^>]*>([^<]+)', html)
    operator = _extract(r'(?:Ship\s*manager|Operator)[^<]*</td>\s*<td[^>]*>([^<]+)', html)
    class_society = _extract(r'Class(?:ification)?\s*society[^<]*</td>\s*<td[^>]*>([^<]+)', html)

    # Parse inspection table if present
    inspections = []
    insp_matches = re.findall(
        r'<tr[^>]*>.*?(\d{1,2}/\d{1,2}/\d{4}).*?'
        r'(?:deficiencies|detentions).*?(\d+).*?(\d+)',
        html, re.IGNORECASE | re.DOTALL,
    )
    for date_str, deficiencies, detentions in insp_matches[:10]:
        inspections.append({
            "date": date_str,
            "deficiencies": int(deficiencies),
            "detentions": int(detentions),
        })

    # Parse flag history
    flag_history = []
    flag_matches = re.findall(
        r'<tr[^>]*>.*?(\d{1,2}/\d{1,2}/\d{4}).*?([A-Z][a-z][\w\s]+?)(?:</td|<)',
        html, re.DOTALL,
    )
    for date_str, flag_name in flag_matches[:10]:
        flag_history.append({"date": date_str, "flag": flag_name.strip()})

    def _to_float(v):
        if not v:
            return None
        return float(v.replace(",", ""))

    def _to_int(v):
        if not v:
            return None
        return int(v)

    return {
        "imo": imo,
        "vessel_name": vessel_name,
        "flag_state": flag_state,
        "gross_tonnage": _to_float(gross_tonnage),
        "deadweight": _to_float(deadweight),
        "year_built": _to_int(year_built),
        "registered_owner": registered_owner,
        "operator": operator,
        "class_society": class_society,
        "inspections": inspections,
        "flag_history": flag_history,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


async def _cache_result(db, imo: int, result: dict):
    """Store Equasis result in cache."""
    import json

    async with db.acquire() as conn:
        await conn.execute(
            """INSERT INTO equasis_cache
               (imo, vessel_name, flag_state, gross_tonnage, deadweight, year_built,
                registered_owner, operator, class_society, inspections, flag_history)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb, $11::jsonb)
               ON CONFLICT (imo) DO UPDATE SET
                   vessel_name = EXCLUDED.vessel_name,
                   flag_state = EXCLUDED.flag_state,
                   gross_tonnage = EXCLUDED.gross_tonnage,
                   deadweight = EXCLUDED.deadweight,
                   year_built = EXCLUDED.year_built,
                   registered_owner = EXCLUDED.registered_owner,
                   operator = EXCLUDED.operator,
                   class_society = EXCLUDED.class_society,
                   inspections = EXCLUDED.inspections,
                   flag_history = EXCLUDED.flag_history,
                   fetched_at = NOW()""",
            imo,
            result.get("vessel_name"),
            result.get("flag_state"),
            result.get("gross_tonnage"),
            result.get("deadweight"),
            result.get("year_built"),
            result.get("registered_owner"),
            result.get("operator"),
            result.get("class_society"),
            json.dumps(result.get("inspections", [])),
            json.dumps(result.get("flag_history", [])),
        )
