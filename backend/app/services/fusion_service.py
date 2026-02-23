"""Bayesian signal fusion service.

Combines confidence scores from multiple intelligence sources (AIS, SAR,
VIIRS, acoustic) into a single posterior score for each vessel.  Results
are persisted in the signal_fusion_results table for historical analysis.
"""

import logging
import math
from datetime import datetime, timezone, timedelta

from app.database import get_db

logger = logging.getLogger("poseidon.fusion_service")

# ---------------------------------------------------------------------------
# Tuning constants
# ---------------------------------------------------------------------------
AIS_FRESH_THRESHOLD_MIN = 30       # fully fresh if last seen < 30 min
AIS_DECAY_HALF_LIFE_MIN = 120     # confidence halves every 2 hours
AIS_FRESH_CONFIDENCE = 0.85       # confidence when position is fresh

VIIRS_SEARCH_RADIUS_M = 50_000    # 50 km radius for VIIRS proximity check


# ---------------------------------------------------------------------------
# Individual signal confidence functions
# ---------------------------------------------------------------------------

def _ais_confidence(last_seen: datetime | None) -> float:
    """Compute AIS confidence from position freshness.

    Returns >0.8 if last seen within 30 minutes, then decays
    exponentially with a 2-hour half-life.  Returns 0.05 if no
    position is available at all (prior floor).
    """
    if last_seen is None:
        return 0.05

    now = datetime.now(timezone.utc)
    age_min = (now - last_seen).total_seconds() / 60.0

    if age_min < 0:
        age_min = 0

    if age_min <= AIS_FRESH_THRESHOLD_MIN:
        return AIS_FRESH_CONFIDENCE
    else:
        # Exponential decay after the fresh threshold
        excess_min = age_min - AIS_FRESH_THRESHOLD_MIN
        decay = math.exp(-math.log(2) * excess_min / AIS_DECAY_HALF_LIFE_MIN)
        return max(0.05, AIS_FRESH_CONFIDENCE * decay)


async def _sar_confidence(mmsi: int, conn) -> float:
    """SAR confidence: based on matched SAR detections for this vessel.

    Returns high confidence if at least one recent SAR match exists.
    """
    row = await conn.fetchrow(
        """
        SELECT COUNT(*) AS cnt,
               MAX(m.created_at) AS latest_match
        FROM sar_vessel_matches m
        WHERE m.mmsi = $1
          AND m.created_at > NOW() - INTERVAL '7 days'
        """,
        mmsi,
    )

    if not row or row["cnt"] == 0:
        return 0.1  # low prior - no SAR evidence

    # More matches -> higher confidence, capped at 0.9
    cnt = row["cnt"]
    return min(0.9, 0.5 + 0.1 * cnt)


async def _viirs_confidence(mmsi: int, conn) -> float:
    """VIIRS confidence: check for anomalies near vessel's last position.

    Queries viirs_anomalies within 50 km of the vessel's latest known
    position (last 7 days of anomalies).
    """
    row = await conn.fetchrow(
        """
        SELECT COUNT(*) AS cnt
        FROM viirs_anomalies va, latest_vessel_positions lvp
        WHERE lvp.mmsi = $1
          AND va.observation_date > (CURRENT_DATE - INTERVAL '7 days')
          AND ST_DWithin(
                va.geom::geography,
                lvp.geom::geography,
                $2
          )
        """,
        mmsi,
        float(VIIRS_SEARCH_RADIUS_M),
    )

    if not row or row["cnt"] == 0:
        return 0.1  # no VIIRS evidence

    cnt = row["cnt"]
    return min(0.85, 0.4 + 0.1 * cnt)


async def _acoustic_confidence(mmsi: int, conn) -> float:
    """Acoustic confidence: check for correlated acoustic events."""
    row = await conn.fetchrow(
        """
        SELECT COUNT(*) AS cnt,
               MAX(correlation_confidence) AS max_conf
        FROM acoustic_events
        WHERE correlated_mmsi = $1
          AND event_time > NOW() - INTERVAL '7 days'
        """,
        mmsi,
    )

    if not row or row["cnt"] == 0:
        return 0.1  # no acoustic evidence

    # Use the highest single correlation confidence, boosted by count
    base = float(row["max_conf"]) if row["max_conf"] is not None else 0.3
    return min(0.9, base + 0.05 * (row["cnt"] - 1))


# ---------------------------------------------------------------------------
# Bayesian posterior
# ---------------------------------------------------------------------------

def _bayesian_posterior(confidences: list[float]) -> float:
    """Simple Bayesian fusion: treat each signal as an independent
    likelihood of vessel presence.

    P(vessel | signals) = product(P_i) / (product(P_i) + product(1 - P_i))

    This is the standard naive-Bayes update with a uniform prior.
    """
    if not confidences:
        return 0.0

    log_prod = 0.0
    log_comp = 0.0
    for p in confidences:
        # Clamp to avoid log(0)
        p = max(1e-6, min(1.0 - 1e-6, p))
        log_prod += math.log(p)
        log_comp += math.log(1.0 - p)

    # Numerical stability: work in log space
    # posterior = exp(log_prod) / (exp(log_prod) + exp(log_comp))
    diff = log_comp - log_prod
    if diff > 500:
        return 0.0
    if diff < -500:
        return 1.0
    return 1.0 / (1.0 + math.exp(diff))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def compute_fusion(mmsi: int) -> dict:
    """Compute and store a Bayesian fusion result for a vessel.

    Returns a dict with all individual signal confidences, the
    posterior score, and the database record id.
    """
    db = get_db()

    async with db.acquire() as conn:
        # --- AIS confidence (from latest_vessel_positions) ---
        pos_row = await conn.fetchrow(
            "SELECT timestamp FROM latest_vessel_positions WHERE mmsi = $1",
            mmsi,
        )
        last_seen = pos_row["timestamp"] if pos_row else None
        ais_conf = _ais_confidence(last_seen)

        # --- SAR confidence ---
        sar_conf = await _sar_confidence(mmsi, conn)

        # --- VIIRS confidence ---
        viirs_conf = await _viirs_confidence(mmsi, conn)

        # --- Acoustic confidence ---
        acoustic_conf = await _acoustic_confidence(mmsi, conn)

        # --- Bayesian posterior ---
        posterior = _bayesian_posterior([
            ais_conf, sar_conf, viirs_conf, acoustic_conf,
        ])

        # --- Classify intent based on posterior ---
        if posterior >= 0.8:
            classification = "confirmed"
        elif posterior >= 0.5:
            classification = "probable"
        elif posterior >= 0.3:
            classification = "possible"
        else:
            classification = "low_confidence"

        # --- Persist ---
        row = await conn.fetchrow(
            """
            INSERT INTO signal_fusion_results
                (mmsi, ais_confidence, sar_confidence, viirs_confidence,
                 acoustic_confidence, posterior_score, classification)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id, timestamp
            """,
            mmsi,
            ais_conf,
            sar_conf,
            viirs_conf,
            acoustic_conf,
            posterior,
            classification,
        )

    result = {
        "id": row["id"],
        "mmsi": mmsi,
        "timestamp": row["timestamp"].isoformat(),
        "ais_confidence": round(ais_conf, 4),
        "sar_confidence": round(sar_conf, 4),
        "viirs_confidence": round(viirs_conf, 4),
        "acoustic_confidence": round(acoustic_conf, 4),
        "posterior_score": round(posterior, 4),
        "classification": classification,
    }

    logger.info(
        "Fusion for MMSI %d: posterior=%.3f (%s)",
        mmsi, posterior, classification,
    )
    return result


async def get_fusion_history(mmsi: int, limit: int = 20) -> list[dict]:
    """Retrieve past fusion results for a vessel, most recent first."""
    db = get_db()

    rows = await db.fetch(
        """
        SELECT id, mmsi, timestamp,
               ais_confidence, sar_confidence, viirs_confidence,
               acoustic_confidence, rf_confidence,
               posterior_score, classification, intent_category,
               created_at
        FROM signal_fusion_results
        WHERE mmsi = $1
        ORDER BY timestamp DESC
        LIMIT $2
        """,
        mmsi,
        limit,
    )

    return [
        {
            "id": r["id"],
            "mmsi": r["mmsi"],
            "timestamp": r["timestamp"].isoformat(),
            "ais_confidence": float(r["ais_confidence"]) if r["ais_confidence"] else 0.0,
            "sar_confidence": float(r["sar_confidence"]) if r["sar_confidence"] else 0.0,
            "viirs_confidence": float(r["viirs_confidence"]) if r["viirs_confidence"] else 0.0,
            "acoustic_confidence": float(r["acoustic_confidence"]) if r["acoustic_confidence"] else 0.0,
            "rf_confidence": float(r["rf_confidence"]) if r["rf_confidence"] else 0.0,
            "posterior_score": float(r["posterior_score"]) if r["posterior_score"] else 0.0,
            "classification": r["classification"],
            "intent_category": r["intent_category"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]
