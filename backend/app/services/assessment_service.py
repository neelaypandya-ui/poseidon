"""Automated forensic assessment engine for any vessel."""

import logging
from datetime import datetime, timezone

from app.database import get_db

logger = logging.getLogger("poseidon.assessment")

# Valid MID prefixes (first digit 2-7 per ITU)
VALID_MID_FIRST_DIGITS = {2, 3, 4, 5, 6, 7}

# Speed thresholds by vessel type (knots)
SPEED_LIMITS = {
    "cargo": 25,
    "tanker": 20,
    "fishing": 18,
    "passenger": 35,
    "tug": 16,
    "pleasure": 40,
    "military": 45,
    "hsc": 60,
    "sar": 40,
    "unknown": 50,
}

NAV_STATUS_STATIONARY = {"at_anchor", "moored", "aground"}


async def compute_assessment(mmsi: int) -> dict | None:
    """Run full forensic assessment on a vessel, returning structured findings."""
    db = get_db()
    async with db.acquire() as conn:
        # --- Gather all data ---
        vessel = await conn.fetchrow(
            """SELECT mmsi, imo, name, callsign, ship_type, ais_type_code,
                      destination, created_at, updated_at
               FROM vessels WHERE mmsi = $1""",
            mmsi,
        )
        if not vessel:
            return None

        latest = await conn.fetchrow(
            """SELECT ST_X(geom) AS lon, ST_Y(geom) AS lat, sog, cog,
                      heading, nav_status, timestamp
               FROM latest_vessel_positions WHERE mmsi = $1""",
            mmsi,
        )

        track_stats = await conn.fetchrow(
            """SELECT COUNT(*) AS total,
                      COUNT(DISTINCT DATE(timestamp)) AS days_active,
                      MIN(timestamp) AS first_seen,
                      MAX(timestamp) AS last_seen
               FROM vessel_positions WHERE mmsi = $1""",
            mmsi,
        )

        forensic_summary = await conn.fetchrow(
            """SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE flag_impossible_speed) AS impossible_speed,
                COUNT(*) FILTER (WHERE flag_sart_on_non_sar) AS sart_on_non_sar,
                COUNT(*) FILTER (WHERE flag_no_identity) AS no_identity,
                COUNT(*) FILTER (WHERE flag_position_jump) AS position_jump,
                COUNT(*) FILTER (WHERE receiver_class = 'terrestrial') AS terrestrial,
                COUNT(*) FILTER (WHERE receiver_class = 'satellite') AS satellite
               FROM ais_raw_messages
               WHERE mmsi = $1 AND timestamp > NOW() - INTERVAL '24 hours'""",
            mmsi,
        )

        identity_changes = await conn.fetchval(
            "SELECT COUNT(*) FROM vessel_identity_history WHERE mmsi = $1",
            mmsi,
        )

        spoof_signals = await conn.fetchval(
            """SELECT COUNT(*) FROM spoof_signals
               WHERE mmsi = $1 AND detected_at > NOW() - INTERVAL '24 hours'""",
            mmsi,
        )

        dark_alerts = await conn.fetchval(
            """SELECT COUNT(*) FROM dark_vessel_alerts
               WHERE mmsi = $1 AND status = 'active'""",
            mmsi,
        )

        # --- Analyze ---
        findings = []
        severity = "clean"  # clean -> low -> medium -> high -> critical
        severity_score = 0

        mmsi_str = str(mmsi)
        ship_type = vessel["ship_type"] or "unknown"

        # 1. MMSI format validation
        if len(mmsi_str) != 9:
            findings.append({
                "category": "identity",
                "severity": "critical",
                "title": "Invalid MMSI length",
                "detail": f"MMSI has {len(mmsi_str)} digits (expected 9). "
                          f"Non-standard identifier suggests spoofed or test transponder.",
            })
            severity_score += 30
        else:
            mid = int(mmsi_str[:3])
            first_digit = int(mmsi_str[0])
            if first_digit not in VALID_MID_FIRST_DIGITS:
                findings.append({
                    "category": "identity",
                    "severity": "high",
                    "title": "Unallocated MID prefix",
                    "detail": f"MID {mid} (first digit {first_digit}) is not allocated by ITU. "
                              f"Valid maritime MMSIs start with digits 2-7.",
                })
                severity_score += 20

        # 2. Identity completeness
        has_name = bool(vessel["name"])
        has_imo = bool(vessel["imo"])
        has_callsign = bool(vessel["callsign"])
        id_fields = sum([has_name, has_imo, has_callsign])

        if id_fields == 0:
            findings.append({
                "category": "identity",
                "severity": "high",
                "title": "No identity data",
                "detail": "Vessel has no name, IMO number, or callsign. "
                          "Complete absence of identification is a strong spoofing indicator.",
            })
            severity_score += 20
        elif id_fields == 1:
            missing = []
            if not has_name:
                missing.append("name")
            if not has_imo:
                missing.append("IMO")
            if not has_callsign:
                missing.append("callsign")
            findings.append({
                "category": "identity",
                "severity": "medium",
                "title": "Incomplete identity",
                "detail": f"Missing: {', '.join(missing)}. Partial identity may indicate "
                          f"an unconfigured transponder or deliberate omission.",
            })
            severity_score += 8

        # 3. Speed analysis
        if latest and latest["sog"] is not None:
            sog = float(latest["sog"])
            limit = SPEED_LIMITS.get(ship_type, 50)

            if sog > 50.0 and abs(sog - 102.3) > 0.1:
                findings.append({
                    "category": "kinematics",
                    "severity": "critical",
                    "title": "Impossible speed",
                    "detail": f"SOG {sog:.1f} kn exceeds any known vessel capability. "
                              f"This is a definitive anomaly flag.",
                })
                severity_score += 25
            elif sog > limit:
                findings.append({
                    "category": "kinematics",
                    "severity": "medium",
                    "title": f"Excessive speed for {ship_type}",
                    "detail": f"SOG {sog:.1f} kn exceeds typical {ship_type} maximum of ~{limit} kn.",
                })
                severity_score += 10

        # 4. Nav status consistency
        if latest and latest["nav_status"] and latest["sog"] is not None:
            nav = latest["nav_status"]
            sog = float(latest["sog"])

            if nav in NAV_STATUS_STATIONARY and sog > 3.0:
                findings.append({
                    "category": "kinematics",
                    "severity": "high",
                    "title": "Nav status contradicts speed",
                    "detail": f"Reports '{nav.replace('_', ' ')}' but SOG is {sog:.1f} kn. "
                              f"Stationary status with significant speed is contradictory.",
                })
                severity_score += 15

        # 5. Heading vs COG discrepancy
        if latest and latest["heading"] is not None and latest["cog"] is not None:
            heading = float(latest["heading"])
            cog = float(latest["cog"])
            sog = float(latest["sog"] or 0)

            if heading < 360 and sog > 2.0:
                diff = abs(heading - cog)
                if diff > 180:
                    diff = 360 - diff
                if diff > 45:
                    findings.append({
                        "category": "kinematics",
                        "severity": "medium",
                        "title": "Heading/COG discrepancy",
                        "detail": f"Heading {heading:.0f} vs COG {cog:.1f} "
                                  f"({diff:.0f} difference). At {sog:.1f} kn, this divergence "
                                  f"is unusual unless in strong crosscurrent.",
                    })
                    severity_score += 8

        # 6. Receiver classification
        if forensic_summary and forensic_summary["total"] > 0:
            total = forensic_summary["total"]
            sat = forensic_summary["satellite"]
            terr = forensic_summary["terrestrial"]
            sat_pct = sat / total * 100

            if sat_pct == 100 and total >= 1:
                findings.append({
                    "category": "reception",
                    "severity": "low",
                    "title": "Satellite-only reception",
                    "detail": f"All {total} messages received via S-AIS. "
                              f"Consistent with remote ocean position but also common for spoofed signals.",
                })
                severity_score += 3

        # 7. Track sparsity
        if track_stats:
            total_pos = track_stats["total"]
            if total_pos == 1:
                findings.append({
                    "category": "behavior",
                    "severity": "high",
                    "title": "Single-ping phantom",
                    "detail": "Only 1 position ever recorded. Single-appearance vessels "
                              "are strongly associated with spoofed or test transmissions.",
                })
                severity_score += 18
            elif total_pos < 5:
                findings.append({
                    "category": "behavior",
                    "severity": "medium",
                    "title": "Sparse track history",
                    "detail": f"Only {total_pos} positions recorded. Limited track data "
                              f"reduces confidence in vessel legitimacy.",
                })
                severity_score += 8

        # 8. Forensic flags
        if forensic_summary:
            flag_total = (
                forensic_summary["impossible_speed"]
                + forensic_summary["sart_on_non_sar"]
                + forensic_summary["no_identity"]
                + forensic_summary["position_jump"]
            )
            if flag_total > 0:
                flags = []
                if forensic_summary["impossible_speed"]:
                    flags.append(f"{forensic_summary['impossible_speed']} impossible speed")
                if forensic_summary["sart_on_non_sar"]:
                    flags.append(f"{forensic_summary['sart_on_non_sar']} SART-on-non-SAR")
                if forensic_summary["no_identity"]:
                    flags.append(f"{forensic_summary['no_identity']} no-identity")
                if forensic_summary["position_jump"]:
                    flags.append(f"{forensic_summary['position_jump']} position-jump")

                findings.append({
                    "category": "forensic_flags",
                    "severity": "high" if flag_total > 2 else "medium",
                    "title": f"{flag_total} forensic flag(s) in 24h",
                    "detail": "; ".join(flags),
                })
                severity_score += min(flag_total * 5, 20)

        # 9. Identity changes
        if identity_changes and identity_changes > 2:
            findings.append({
                "category": "identity",
                "severity": "medium",
                "title": f"{identity_changes} identity changes",
                "detail": "Frequent identity changes may indicate MMSI recycling or spoofing.",
            })
            severity_score += min(identity_changes * 3, 15)

        # 10. Active dark vessel alert
        if dark_alerts and dark_alerts > 0:
            findings.append({
                "category": "behavior",
                "severity": "high",
                "title": "Active dark vessel alert",
                "detail": "This vessel currently has an active AIS gap alert.",
            })
            severity_score += 12

        # 11. Spoof signals
        if spoof_signals and spoof_signals > 0:
            findings.append({
                "category": "forensic_flags",
                "severity": "high",
                "title": f"{spoof_signals} spoof signal(s) detected",
                "detail": "Anomaly detector has flagged recent transmissions from this MMSI.",
            })
            severity_score += 15

        # --- Determine overall severity ---
        if severity_score >= 50:
            severity = "critical"
        elif severity_score >= 30:
            severity = "high"
        elif severity_score >= 15:
            severity = "medium"
        elif severity_score > 0:
            severity = "low"
        else:
            severity = "clean"

        # --- Build verdict ---
        if severity == "critical":
            verdict = "Almost certainly spoofed or malfunctioning. Multiple definitive anomaly indicators."
        elif severity == "high":
            verdict = "Highly suspicious. Significant anomalies warrant investigation."
        elif severity == "medium":
            verdict = "Some anomalies detected. Monitor for additional suspicious activity."
        elif severity == "low":
            verdict = "Minor irregularities noted. Likely legitimate with minor data issues."
        else:
            verdict = "No anomalies detected. Vessel appears legitimate."

        # Receiver breakdown
        receiver = None
        if forensic_summary and forensic_summary["total"] > 0:
            total = forensic_summary["total"]
            receiver = {
                "terrestrial": forensic_summary["terrestrial"],
                "satellite": forensic_summary["satellite"],
                "terrestrial_pct": round(forensic_summary["terrestrial"] / total * 100, 1),
                "satellite_pct": round(forensic_summary["satellite"] / total * 100, 1),
            }

        return {
            "mmsi": mmsi,
            "severity": severity,
            "severity_score": min(severity_score, 100),
            "verdict": verdict,
            "finding_count": len(findings),
            "findings": findings,
            "vessel_summary": {
                "name": vessel["name"],
                "imo": vessel["imo"],
                "callsign": vessel["callsign"],
                "ship_type": ship_type,
                "has_name": has_name,
                "has_imo": has_imo,
                "has_callsign": has_callsign,
            },
            "track_summary": {
                "total_positions": track_stats["total"] if track_stats else 0,
                "days_active": track_stats["days_active"] if track_stats else 0,
                "first_seen": track_stats["first_seen"].isoformat() if track_stats and track_stats["first_seen"] else None,
                "last_seen": track_stats["last_seen"].isoformat() if track_stats and track_stats["last_seen"] else None,
            },
            "receiver": receiver,
            "identity_changes": identity_changes or 0,
            "active_spoof_signals": spoof_signals or 0,
            "active_dark_alerts": dark_alerts or 0,
            "assessed_at": datetime.now(timezone.utc).isoformat(),
        }
