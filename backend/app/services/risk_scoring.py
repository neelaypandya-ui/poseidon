"""
Vessel risk scoring service.

Computes a composite risk score (0-100) based on identity completeness,
flag state risk, anomaly behavior, and dark vessel history.
"""

import logging
from datetime import datetime, timezone

from app.database import get_db

logger = logging.getLogger("poseidon.risk_scoring")

# High-risk flag states (convenience flags and known IUU-associated registries)
# Higher tier = higher risk
FLAG_RISK_TIERS = {
    # Tier 3 - Highest risk (score 18-20)
    "comoros": 20,
    "tanzania": 20,
    "togo": 19,
    "moldova": 19,
    "cambodia": 18,
    "mongolia": 18,
    "bolivia": 18,
    "sierra leone": 18,
    # Tier 2 - Elevated risk (score 12-17)
    "panama": 15,
    "liberia": 14,
    "marshall islands": 14,
    "honduras": 16,
    "belize": 16,
    "saint vincent and the grenadines": 15,
    "antigua and barbuda": 13,
    "dominica": 13,
    "vanuatu": 14,
    "palau": 13,
    "tuvalu": 13,
    "kiribati": 12,
    # Tier 1 - Moderate risk (score 6-11)
    "bahamas": 8,
    "malta": 7,
    "cyprus": 7,
    "bermuda": 6,
    "gibraltar": 6,
    "isle of man": 6,
    "cayman islands": 7,
    "barbados": 8,
    "saint kitts and nevis": 9,
    "cook islands": 10,
}


def _compute_identity_score(vessel: dict) -> tuple[int, dict]:
    """Compute identity completeness score (0-20).

    Checks presence and validity of vessel identifiers.

    Returns:
        Tuple of (score, details_dict).
    """
    score = 0
    details = {}

    # MMSI format check (should be 9 digits, first digit indicates region)
    mmsi_str = str(vessel.get("mmsi", ""))
    if len(mmsi_str) == 9 and mmsi_str[0] in "2345679":
        score += 0  # Valid MMSI reduces risk
        details["mmsi_valid"] = True
    else:
        score += 5
        details["mmsi_valid"] = False

    # Vessel name present
    name = vessel.get("name")
    if not name or name.strip() == "" or name.strip().upper() == "UNKNOWN":
        score += 5
        details["name_present"] = False
    else:
        details["name_present"] = True

    # Ship type present and known
    ship_type = vessel.get("ship_type")
    if not ship_type or ship_type == "unknown":
        score += 5
        details["ship_type_known"] = False
    else:
        details["ship_type_known"] = True

    # IMO number present (strong identifier)
    imo = vessel.get("imo")
    if not imo or imo == 0:
        score += 5
        details["imo_present"] = False
    else:
        details["imo_present"] = True

    # Cap at 20
    score = min(score, 20)
    details["identity_score"] = score

    return score, details


def _compute_flag_risk_score(vessel: dict) -> tuple[int, dict]:
    """Compute flag state risk score (0-20).

    Checks vessel's flag/destination against known high-risk registries.

    Returns:
        Tuple of (score, details_dict).
    """
    details = {}

    # Try to determine flag from MMSI MID (Maritime Identification Digits)
    # First 3 digits of MMSI (or digits 2-4 for coast stations)
    mmsi_str = str(vessel.get("mmsi", ""))
    mid = mmsi_str[:3] if len(mmsi_str) == 9 else ""
    details["mid"] = mid

    # Check destination field for flag hints (some systems encode flag in name)
    destination = (vessel.get("destination") or "").lower().strip()
    name = (vessel.get("name") or "").lower().strip()

    # Check against flag risk tiers
    flag_score = 0
    matched_flag = None

    # Check destination/name for flag state mentions
    for flag, risk in FLAG_RISK_TIERS.items():
        if flag in destination or flag in name:
            if risk > flag_score:
                flag_score = risk
                matched_flag = flag

    # If no flag detected, assign a mild score for unknown flag
    if matched_flag is None:
        flag_score = 3
        details["flag_detected"] = None
        details["flag_note"] = "Flag state not determined from available data"
    else:
        details["flag_detected"] = matched_flag
        details["flag_note"] = f"Matched high-risk flag state: {matched_flag}"

    # Cap at 20
    flag_score = min(flag_score, 20)
    details["flag_risk_score"] = flag_score

    return flag_score, details


async def _compute_anomaly_score(mmsi: int) -> tuple[int, dict]:
    """Compute behavioral anomaly score (0-30).

    Counts dark vessel alerts in the last 90 days and normalizes.

    Returns:
        Tuple of (score, details_dict).
    """
    db = get_db()
    details = {}

    # Count dark vessel alerts in last 90 days
    alert_count = await db.fetchval(
        """
        SELECT COUNT(*)
        FROM dark_vessel_alerts
        WHERE mmsi = $1 AND detected_at > NOW() - INTERVAL '90 days'
        """,
        mmsi,
    )
    alert_count = alert_count or 0
    details["dark_alerts_90d"] = alert_count

    # Normalize: 0 alerts = 0, 1 = 10, 2 = 18, 3 = 24, 4+ = 28-30
    if alert_count == 0:
        score = 0
    elif alert_count == 1:
        score = 10
    elif alert_count == 2:
        score = 18
    elif alert_count == 3:
        score = 24
    else:
        score = min(30, 24 + (alert_count - 3) * 2)

    details["anomaly_score"] = score

    return score, details


async def _compute_dark_history_score(mmsi: int) -> tuple[int, dict]:
    """Compute dark vessel history score (0-30).

    Evaluates the count and total duration of AIS gaps.

    Returns:
        Tuple of (score, details_dict).
    """
    db = get_db()
    details = {}

    # Get dark vessel alert history
    rows = await db.fetch(
        """
        SELECT gap_hours, last_seen_at, detected_at, status::text
        FROM dark_vessel_alerts
        WHERE mmsi = $1
        ORDER BY detected_at DESC
        """,
        mmsi,
    )

    total_gaps = len(rows)
    total_gap_hours = sum(float(r["gap_hours"] or 0) for r in rows)
    active_gaps = sum(1 for r in rows if r["status"] == "active")

    details["total_dark_events"] = total_gaps
    details["total_gap_hours"] = round(total_gap_hours, 1)
    details["active_dark_alerts"] = active_gaps

    # Scoring: combine count and duration
    # Count component (0-15): 0=0, 1-2=5, 3-5=10, 6+=15
    if total_gaps == 0:
        count_score = 0
    elif total_gaps <= 2:
        count_score = 5
    elif total_gaps <= 5:
        count_score = 10
    else:
        count_score = 15

    # Duration component (0-15): based on total gap hours
    if total_gap_hours < 1:
        duration_score = 0
    elif total_gap_hours < 12:
        duration_score = 5
    elif total_gap_hours < 48:
        duration_score = 10
    else:
        duration_score = 15

    score = count_score + duration_score
    # Bonus for currently active dark alerts
    if active_gaps > 0:
        score = min(30, score + 5)

    score = min(score, 30)
    details["dark_history_score"] = score
    details["count_component"] = count_score
    details["duration_component"] = duration_score

    return score, details


async def compute_risk_score(mmsi: int) -> dict:
    """Compute overall vessel risk score (0-100).

    Components:
        - identity_score (0-20): Vessel identity completeness
        - flag_risk_score (0-20): Flag state risk tier
        - anomaly_score (0-30): Recent dark vessel alerts
        - dark_history_score (0-30): Historical AIS gap analysis

    Args:
        mmsi: Maritime Mobile Service Identity of the vessel.

    Returns:
        Dictionary containing all scores, details, and overall risk level.
    """
    db = get_db()

    # Get vessel details
    vessel = await db.fetchrow(
        """
        SELECT v.mmsi, v.imo, v.name, v.callsign, v.ship_type::text,
               v.destination, v.eta,
               ST_X(lv.geom) as lon, ST_Y(lv.geom) as lat,
               lv.sog, lv.cog, lv.timestamp as last_seen
        FROM vessels v
        LEFT JOIN latest_vessel_positions lv ON v.mmsi = lv.mmsi
        WHERE v.mmsi = $1
        """,
        mmsi,
    )

    if not vessel:
        logger.warning("Vessel not found for MMSI %d", mmsi)
        return {"error": "Vessel not found", "mmsi": mmsi}

    vessel_dict = dict(vessel)

    # Compute component scores
    identity_score, identity_details = _compute_identity_score(vessel_dict)
    flag_risk_score, flag_details = _compute_flag_risk_score(vessel_dict)
    anomaly_score, anomaly_details = await _compute_anomaly_score(mmsi)
    dark_history_score, dark_details = await _compute_dark_history_score(mmsi)

    # Overall score
    overall_score = identity_score + flag_risk_score + anomaly_score + dark_history_score
    overall_score = min(100, max(0, overall_score))

    # Risk level classification
    if overall_score >= 75:
        risk_level = "critical"
    elif overall_score >= 50:
        risk_level = "high"
    elif overall_score >= 25:
        risk_level = "medium"
    else:
        risk_level = "low"

    scored_at = datetime.now(timezone.utc)

    # Store in vessel_risk_scores table
    try:
        await db.execute(
            """
            INSERT INTO vessel_risk_scores
                (mmsi, overall_score, identity_score, flag_risk_score,
                 anomaly_score, dark_history_score, risk_level, details, scored_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9)
            """,
            mmsi,
            overall_score,
            identity_score,
            flag_risk_score,
            anomaly_score,
            dark_history_score,
            risk_level,
            __import__("json").dumps({
                "identity": identity_details,
                "flag": flag_details,
                "anomaly": anomaly_details,
                "dark_history": dark_details,
            }),
            scored_at,
        )
    except Exception as e:
        logger.error("Failed to store risk score for MMSI %d: %s", mmsi, e)

    result = {
        "mmsi": mmsi,
        "vessel_name": vessel_dict.get("name"),
        "ship_type": vessel_dict.get("ship_type"),
        "overall_score": overall_score,
        "risk_level": risk_level,
        "identity_score": identity_score,
        "flag_risk_score": flag_risk_score,
        "anomaly_score": anomaly_score,
        "dark_history_score": dark_history_score,
        "details": {
            "identity": identity_details,
            "flag": flag_details,
            "anomaly": anomaly_details,
            "dark_history": dark_details,
        },
        "scored_at": scored_at.isoformat(),
    }

    logger.info(
        "Risk score for MMSI %d: %d (%s) [id=%d, flag=%d, anom=%d, dark=%d]",
        mmsi, overall_score, risk_level,
        identity_score, flag_risk_score, anomaly_score, dark_history_score,
    )

    return result


async def get_risk_score(mmsi: int) -> dict | None:
    """Get the latest stored risk score for a vessel.

    Args:
        mmsi: Maritime Mobile Service Identity of the vessel.

    Returns:
        Risk score dictionary or None if no score exists.
    """
    db = get_db()

    row = await db.fetchrow(
        """
        SELECT id, mmsi, overall_score, identity_score, flag_risk_score,
               anomaly_score, dark_history_score, risk_level, details, scored_at
        FROM vessel_risk_scores
        WHERE mmsi = $1
        ORDER BY scored_at DESC
        LIMIT 1
        """,
        mmsi,
    )

    if not row:
        return None

    import json
    return {
        "id": row["id"],
        "mmsi": row["mmsi"],
        "overall_score": row["overall_score"],
        "identity_score": row["identity_score"],
        "flag_risk_score": row["flag_risk_score"],
        "anomaly_score": row["anomaly_score"],
        "dark_history_score": row["dark_history_score"],
        "risk_level": row["risk_level"],
        "details": json.loads(row["details"]) if row["details"] else {},
        "scored_at": row["scored_at"].isoformat() if row["scored_at"] else None,
    }


async def get_high_risk_vessels(threshold: float = 50) -> list[dict]:
    """Get all vessels with risk scores above a threshold.

    Args:
        threshold: Minimum overall score to include (default 50).

    Returns:
        List of high-risk vessel dictionaries ordered by score descending.
    """
    db = get_db()

    rows = await db.fetch(
        """
        SELECT DISTINCT ON (rs.mmsi)
               rs.id, rs.mmsi, rs.overall_score, rs.identity_score,
               rs.flag_risk_score, rs.anomaly_score, rs.dark_history_score,
               rs.risk_level, rs.scored_at,
               v.name as vessel_name, v.ship_type::text as ship_type,
               ST_X(lv.geom) as lon, ST_Y(lv.geom) as lat,
               lv.sog, lv.timestamp as last_seen
        FROM vessel_risk_scores rs
        JOIN vessels v ON rs.mmsi = v.mmsi
        LEFT JOIN latest_vessel_positions lv ON rs.mmsi = lv.mmsi
        WHERE rs.overall_score >= $1
        ORDER BY rs.mmsi, rs.scored_at DESC
        """,
        threshold,
    )

    results = []
    for row in rows:
        results.append({
            "id": row["id"],
            "mmsi": row["mmsi"],
            "vessel_name": row["vessel_name"],
            "ship_type": row["ship_type"],
            "overall_score": row["overall_score"],
            "identity_score": row["identity_score"],
            "flag_risk_score": row["flag_risk_score"],
            "anomaly_score": row["anomaly_score"],
            "dark_history_score": row["dark_history_score"],
            "risk_level": row["risk_level"],
            "lon": row["lon"],
            "lat": row["lat"],
            "sog": row["sog"],
            "last_seen": row["last_seen"].isoformat() if row["last_seen"] else None,
            "scored_at": row["scored_at"].isoformat() if row["scored_at"] else None,
        })

    # Sort by overall score descending
    results.sort(key=lambda x: x["overall_score"], reverse=True)

    return results
