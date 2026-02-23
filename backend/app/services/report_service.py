"""
PDF report generation service for vessel intelligence reports.

Uses fpdf2 to generate structured PDF reports containing vessel identity,
risk assessment, track summary, dark activity, and SAR detections.
"""

import os
import math
import logging
from datetime import datetime, timezone

from fpdf import FPDF

from app.database import get_db

logger = logging.getLogger("poseidon.report_service")

REPORTS_DIR = "/app/reports"


class PoseidonReport(FPDF):
    """Custom FPDF subclass with Poseidon branding."""

    def header(self):
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(5, 13, 26)  # Navy #050D1A
        self.cell(0, 10, "POSEIDON MARITIME INTELLIGENCE REPORT", align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(10, 22, 40)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f"Poseidon Maritime Intelligence | Page {self.page_no()}/{{nb}}", align="C")

    def section_header(self, title: str):
        """Add a styled section header."""
        self.ln(3)
        self.set_font("Helvetica", "B", 12)
        self.set_fill_color(10, 22, 40)
        self.set_text_color(255, 255, 255)
        self.cell(0, 8, f"  {title}", fill=True, new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0, 0, 0)
        self.ln(2)

    def key_value(self, key: str, value: str):
        """Add a key-value line."""
        self.set_font("Helvetica", "B", 10)
        self.cell(50, 6, f"{key}:", new_x="END")
        self.set_font("Helvetica", "", 10)
        self.cell(0, 6, str(value), new_x="LMARGIN", new_y="NEXT")

    def risk_bar(self, label: str, score: int, max_score: int):
        """Draw a colored risk score bar."""
        self.set_font("Helvetica", "", 9)
        self.cell(45, 6, f"{label}:", new_x="END")

        # Bar dimensions
        bar_width = 80
        bar_height = 5
        filled_width = (score / max_score) * bar_width if max_score > 0 else 0

        x = self.get_x()
        y = self.get_y() + 0.5

        # Background
        self.set_fill_color(220, 220, 220)
        self.rect(x, y, bar_width, bar_height, style="F")

        # Filled portion with color based on score ratio
        ratio = score / max_score if max_score > 0 else 0
        if ratio >= 0.75:
            self.set_fill_color(220, 38, 38)  # Red
        elif ratio >= 0.5:
            self.set_fill_color(245, 158, 11)  # Amber
        elif ratio >= 0.25:
            self.set_fill_color(234, 179, 8)  # Yellow
        else:
            self.set_fill_color(34, 197, 94)  # Green

        if filled_width > 0:
            self.rect(x, y, filled_width, bar_height, style="F")

        # Score text
        self.set_x(x + bar_width + 3)
        self.set_font("Helvetica", "B", 9)
        self.cell(20, 6, f"{score}/{max_score}", new_x="LMARGIN", new_y="NEXT")


def _haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance in nautical miles."""
    R_NM = 3440.065
    lat1_r, lon1_r = math.radians(lat1), math.radians(lon1)
    lat2_r, lon2_r = math.radians(lat2), math.radians(lon2)
    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return R_NM * c


async def generate_vessel_report(mmsi: int) -> str:
    """Generate a comprehensive PDF intelligence report for a vessel.

    Args:
        mmsi: Maritime Mobile Service Identity of the vessel.

    Returns:
        File path of the generated PDF report.

    Raises:
        ValueError: If vessel is not found in the database.
    """
    db = get_db()

    # 1. Get vessel details
    vessel = await db.fetchrow(
        """
        SELECT v.mmsi, v.imo, v.name, v.callsign, v.ship_type::text,
               v.ais_type_code, v.dim_bow, v.dim_stern, v.dim_port, v.dim_starboard,
               v.destination, v.eta,
               ST_X(lv.geom) as lon, ST_Y(lv.geom) as lat,
               lv.sog, lv.cog, lv.heading, lv.nav_status::text,
               lv.timestamp as last_seen
        FROM vessels v
        LEFT JOIN latest_vessel_positions lv ON v.mmsi = lv.mmsi
        WHERE v.mmsi = $1
        """,
        mmsi,
    )

    if not vessel:
        raise ValueError(f"Vessel with MMSI {mmsi} not found")

    vessel = dict(vessel)

    # 2. Get risk score
    risk_row = await db.fetchrow(
        """
        SELECT overall_score, identity_score, flag_risk_score,
               anomaly_score, dark_history_score, risk_level, details, scored_at
        FROM vessel_risk_scores
        WHERE mmsi = $1
        ORDER BY scored_at DESC
        LIMIT 1
        """,
        mmsi,
    )

    # 3. Get recent track (last 7 days)
    track = await db.fetch(
        """
        SELECT ST_X(geom) as lon, ST_Y(geom) as lat, sog, cog, timestamp
        FROM vessel_positions
        WHERE mmsi = $1 AND timestamp > NOW() - INTERVAL '7 days'
        ORDER BY timestamp ASC
        """,
        mmsi,
    )

    # 4. Get dark vessel alerts
    dark_alerts = await db.fetch(
        """
        SELECT id, status::text, gap_hours, last_seen_at, detected_at, resolved_at,
               ST_X(last_known_geom) as last_known_lon, ST_Y(last_known_geom) as last_known_lat,
               last_sog, last_cog, search_radius_nm
        FROM dark_vessel_alerts
        WHERE mmsi = $1
        ORDER BY detected_at DESC
        LIMIT 20
        """,
        mmsi,
    )

    # 5. Get SAR detections if any
    sar_detections = []
    try:
        sar_detections = await db.fetch(
            """
            SELECT id, ST_X(geom) as lon, ST_Y(geom) as lat,
                   intensity_db, estimated_length_m, detected_at, matched_mmsi
            FROM sar_detections
            WHERE matched_mmsi = $1
            ORDER BY detected_at DESC
            LIMIT 10
            """,
            mmsi,
        )
    except Exception:
        # SAR detections table may not exist yet
        logger.debug("SAR detections table not available")

    # 6. Build PDF
    pdf = PoseidonReport()
    pdf.alias_nb_pages()
    pdf.add_page()
    generated_at = datetime.now(timezone.utc)

    # Generation info
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 5, f"Generated: {generated_at.strftime('%Y-%m-%d %H:%M UTC')} | MMSI: {mmsi}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # --- Vessel Identity Section ---
    pdf.section_header("VESSEL IDENTITY")
    pdf.key_value("MMSI", str(vessel.get("mmsi", "N/A")))
    pdf.key_value("IMO", str(vessel.get("imo") or "N/A"))
    pdf.key_value("Name", vessel.get("name") or "Unknown")
    pdf.key_value("Callsign", vessel.get("callsign") or "N/A")
    pdf.key_value("Type", (vessel.get("ship_type") or "unknown").upper())
    pdf.key_value("Destination", vessel.get("destination") or "N/A")

    if vessel.get("eta"):
        pdf.key_value("ETA", str(vessel["eta"]))

    # Dimensions
    dim_parts = []
    if vessel.get("dim_bow") and vessel.get("dim_stern"):
        length = (vessel["dim_bow"] or 0) + (vessel["dim_stern"] or 0)
        dim_parts.append(f"Length: {length}m")
    if vessel.get("dim_port") and vessel.get("dim_starboard"):
        beam = (vessel["dim_port"] or 0) + (vessel["dim_starboard"] or 0)
        dim_parts.append(f"Beam: {beam}m")
    if dim_parts:
        pdf.key_value("Dimensions", " | ".join(dim_parts))

    # Current position
    if vessel.get("lon") is not None and vessel.get("lat") is not None:
        pdf.key_value("Last Position", f"{vessel['lat']:.5f}N, {vessel['lon']:.5f}E")
        pdf.key_value("SOG / COG", f"{vessel.get('sog', 0):.1f} kn / {vessel.get('cog', 0):.1f} deg")
        pdf.key_value("Nav Status", (vessel.get("nav_status") or "N/A").replace("_", " ").title())
        if vessel.get("last_seen"):
            pdf.key_value("Last Seen", vessel["last_seen"].strftime("%Y-%m-%d %H:%M UTC"))

    # --- Risk Assessment Section ---
    pdf.section_header("RISK ASSESSMENT")

    if risk_row:
        risk = dict(risk_row)
        overall = risk.get("overall_score", 0)
        level = (risk.get("risk_level") or "unknown").upper()

        # Overall score with color
        pdf.set_font("Helvetica", "B", 14)
        if overall >= 75:
            pdf.set_text_color(220, 38, 38)
        elif overall >= 50:
            pdf.set_text_color(245, 158, 11)
        elif overall >= 25:
            pdf.set_text_color(234, 179, 8)
        else:
            pdf.set_text_color(34, 197, 94)
        pdf.cell(0, 8, f"Overall Risk Score: {overall}/100 ({level})", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
        pdf.ln(2)

        # Component bars
        pdf.risk_bar("Identity Risk", risk.get("identity_score", 0), 20)
        pdf.risk_bar("Flag State Risk", risk.get("flag_risk_score", 0), 20)
        pdf.risk_bar("Anomaly Score", risk.get("anomaly_score", 0), 30)
        pdf.risk_bar("Dark History", risk.get("dark_history_score", 0), 30)

        if risk.get("scored_at"):
            pdf.ln(2)
            pdf.set_font("Helvetica", "I", 8)
            pdf.cell(0, 5, f"Score computed: {risk['scored_at'].strftime('%Y-%m-%d %H:%M UTC')}", new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.set_font("Helvetica", "I", 10)
        pdf.cell(0, 6, "No risk assessment available. Run risk scoring first.", new_x="LMARGIN", new_y="NEXT")

    # --- Track Summary Section ---
    pdf.section_header("TRACK SUMMARY (7 DAYS)")

    track_list = [dict(r) for r in track]
    num_positions = len(track_list)
    pdf.key_value("Positions Recorded", str(num_positions))

    if num_positions >= 2:
        # Calculate total distance
        total_distance_nm = 0.0
        for i in range(1, len(track_list)):
            p1 = track_list[i - 1]
            p2 = track_list[i]
            total_distance_nm += _haversine_nm(
                float(p1["lat"]), float(p1["lon"]),
                float(p2["lat"]), float(p2["lon"]),
            )

        pdf.key_value("Distance Traveled", f"{total_distance_nm:.1f} NM")

        # Time span
        first_ts = track_list[0]["timestamp"]
        last_ts = track_list[-1]["timestamp"]
        duration = last_ts - first_ts
        hours = duration.total_seconds() / 3600
        pdf.key_value("Time Span", f"{hours:.1f} hours")

        # Average speed
        if hours > 0:
            avg_speed = total_distance_nm / hours
            pdf.key_value("Average Speed", f"{avg_speed:.1f} knots")

        # Speed statistics from track
        sogs = [float(t["sog"]) for t in track_list if t["sog"] is not None]
        if sogs:
            pdf.key_value("Max SOG", f"{max(sogs):.1f} knots")
            pdf.key_value("Min SOG", f"{min(sogs):.1f} knots")
    elif num_positions == 0:
        pdf.set_font("Helvetica", "I", 10)
        pdf.cell(0, 6, "No track data available for the last 7 days.", new_x="LMARGIN", new_y="NEXT")

    # --- Dark Activity Section ---
    pdf.section_header("DARK ACTIVITY (AIS GAPS)")

    dark_list = [dict(r) for r in dark_alerts]
    if dark_list:
        pdf.key_value("Total Dark Events", str(len(dark_list)))
        active_count = sum(1 for d in dark_list if d["status"] == "active")
        if active_count > 0:
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(220, 38, 38)
            pdf.cell(0, 6, f"  ** {active_count} ACTIVE ALERT(S) **", new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(0, 0, 0)

        pdf.ln(2)

        # Table header
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_fill_color(240, 240, 240)
        pdf.cell(15, 5, "ID", border=1, fill=True, align="C")
        pdf.cell(20, 5, "Status", border=1, fill=True, align="C")
        pdf.cell(25, 5, "Gap (hrs)", border=1, fill=True, align="C")
        pdf.cell(45, 5, "Last Seen", border=1, fill=True, align="C")
        pdf.cell(45, 5, "Detected", border=1, fill=True, align="C")
        pdf.cell(30, 5, "Radius (NM)", border=1, fill=True, align="C", new_x="LMARGIN", new_y="NEXT")

        pdf.set_font("Helvetica", "", 8)
        for d in dark_list[:15]:  # Limit to 15 rows
            pdf.cell(15, 5, str(d.get("id", "")), border=1, align="C")
            pdf.cell(20, 5, d.get("status", ""), border=1, align="C")
            pdf.cell(25, 5, f"{d.get('gap_hours', 0):.1f}", border=1, align="C")
            last_seen = d.get("last_seen_at")
            pdf.cell(45, 5, last_seen.strftime("%Y-%m-%d %H:%M") if last_seen else "N/A", border=1, align="C")
            detected = d.get("detected_at")
            pdf.cell(45, 5, detected.strftime("%Y-%m-%d %H:%M") if detected else "N/A", border=1, align="C")
            pdf.cell(30, 5, f"{d.get('search_radius_nm', 0):.1f}", border=1, align="C", new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(34, 197, 94)
        pdf.cell(0, 6, "No dark vessel alerts recorded.", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)

    # --- SAR Detections Section ---
    pdf.section_header("SAR DETECTIONS")

    sar_list = [dict(r) for r in sar_detections]
    if sar_list:
        pdf.key_value("Matched Detections", str(len(sar_list)))
        pdf.ln(2)

        pdf.set_font("Helvetica", "B", 8)
        pdf.set_fill_color(240, 240, 240)
        pdf.cell(15, 5, "ID", border=1, fill=True, align="C")
        pdf.cell(35, 5, "Position", border=1, fill=True, align="C")
        pdf.cell(25, 5, "Intensity", border=1, fill=True, align="C")
        pdf.cell(25, 5, "Est. Length", border=1, fill=True, align="C")
        pdf.cell(45, 5, "Detected At", border=1, fill=True, align="C", new_x="LMARGIN", new_y="NEXT")

        pdf.set_font("Helvetica", "", 8)
        for s in sar_list:
            pdf.cell(15, 5, str(s.get("id", "")), border=1, align="C")
            pdf.cell(35, 5, f"{s.get('lat', 0):.4f}, {s.get('lon', 0):.4f}", border=1, align="C")
            intensity = s.get("intensity_db")
            pdf.cell(25, 5, f"{intensity:.1f} dB" if intensity else "N/A", border=1, align="C")
            length = s.get("estimated_length_m")
            pdf.cell(25, 5, f"{length:.0f}m" if length else "N/A", border=1, align="C")
            det_at = s.get("detected_at")
            pdf.cell(45, 5, det_at.strftime("%Y-%m-%d %H:%M") if det_at else "N/A", border=1, align="C", new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, "No SAR detections matched to this vessel.", new_x="LMARGIN", new_y="NEXT")

    # --- Classification footer ---
    pdf.ln(10)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(128, 128, 128)
    pdf.cell(0, 5, "CLASSIFICATION: UNCLASSIFIED // FOR OFFICIAL USE ONLY", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, "This report is auto-generated by the Poseidon Maritime Intelligence Platform.", align="C", new_x="LMARGIN", new_y="NEXT")

    # 7. Save PDF
    os.makedirs(REPORTS_DIR, exist_ok=True)
    timestamp_str = generated_at.strftime("%Y%m%d_%H%M%S")
    filename = f"{mmsi}_{timestamp_str}.pdf"
    filepath = os.path.join(REPORTS_DIR, filename)

    pdf.output(filepath)

    logger.info(
        "Generated report for MMSI %d: %s (%d track points, %d alerts, %d SAR)",
        mmsi, filepath, num_positions, len(dark_list), len(sar_list),
    )

    return filepath
