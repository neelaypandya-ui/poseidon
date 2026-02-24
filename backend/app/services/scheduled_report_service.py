"""Scheduled report generation service.

Generates periodic digest reports (daily, weekly) as PDFs containing
vessel activity summaries, alert statistics, and key events.
"""

import os
import json
import logging
from datetime import datetime, timezone, timedelta

from fpdf import FPDF

from app.database import get_db

logger = logging.getLogger("poseidon.scheduled_report_service")

REPORTS_DIR = "/app/reports/scheduled"


class DigestReport(FPDF):
    """Custom FPDF subclass for scheduled digest reports."""

    def header(self):
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(5, 13, 26)
        self.cell(0, 10, "POSEIDON - SCHEDULED INTELLIGENCE DIGEST", align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(10, 22, 40)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f"Poseidon Digest | Page {self.page_no()}/{{nb}}", align="C")


async def generate_digest(report_id: int, output_id: int) -> str:
    """Generate a digest PDF for a scheduled report.

    Returns the file path of the generated PDF.
    """
    db = get_db()

    # Get report config
    report = await db.fetchrow(
        "SELECT id, name, report_type, config FROM scheduled_reports WHERE id = $1",
        report_id,
    )
    if not report:
        raise ValueError(f"Scheduled report {report_id} not found")

    config = json.loads(report["config"]) if report["config"] else {}
    hours = config.get("hours_back", 24)
    now = datetime.now(timezone.utc)

    # Gather statistics
    stats = {}

    # Active vessels
    row = await db.fetchrow(
        "SELECT COUNT(*) as cnt FROM latest_vessel_positions WHERE timestamp > NOW() - make_interval(hours => $1)",
        hours,
    )
    stats["active_vessels"] = row["cnt"]

    # Dark vessel alerts
    row = await db.fetchrow(
        "SELECT COUNT(*) as cnt FROM dark_vessel_alerts WHERE status = 'active'"
    )
    stats["active_dark_alerts"] = row["cnt"]

    row = await db.fetchrow(
        "SELECT COUNT(*) as cnt FROM dark_vessel_alerts WHERE detected_at > NOW() - make_interval(hours => $1)",
        hours,
    )
    stats["new_dark_alerts"] = row["cnt"]

    # Spoof signals
    try:
        row = await db.fetchrow(
            "SELECT COUNT(*) as cnt FROM spoof_signals WHERE detected_at > NOW() - make_interval(hours => $1)",
            hours,
        )
        stats["new_spoof_signals"] = row["cnt"]
    except Exception:
        stats["new_spoof_signals"] = 0

    # High risk vessels
    try:
        row = await db.fetchrow(
            "SELECT COUNT(*) as cnt FROM vessel_risk_scores WHERE overall_score >= 75"
        )
        stats["high_risk_vessels"] = row["cnt"]
    except Exception:
        stats["high_risk_vessels"] = 0

    # EEZ crossings
    try:
        row = await db.fetchrow(
            "SELECT COUNT(*) as cnt FROM eez_entry_events WHERE timestamp > NOW() - make_interval(hours => $1)",
            hours,
        )
        stats["eez_crossings"] = row["cnt"]
    except Exception:
        stats["eez_crossings"] = 0

    # Top 10 most active vessels
    top_vessels = await db.fetch(
        """
        SELECT mmsi, COUNT(*) as pos_count
        FROM vessel_positions
        WHERE timestamp > NOW() - make_interval(hours => $1)
        GROUP BY mmsi
        ORDER BY pos_count DESC
        LIMIT 10
        """,
        hours,
    )

    # Build PDF
    pdf = DigestReport()
    pdf.alias_nb_pages()
    pdf.add_page()

    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 5, f"Report: {report['name']} | Period: Last {hours} hours | Generated: {now.strftime('%Y-%m-%d %H:%M UTC')}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # Summary section
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_fill_color(10, 22, 40)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 8, "  OPERATIONAL SUMMARY", fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(3)

    pdf.set_font("Helvetica", "", 10)
    for key, label in [
        ("active_vessels", "Active Vessels"),
        ("active_dark_alerts", "Active Dark Vessel Alerts"),
        ("new_dark_alerts", "New Dark Alerts (period)"),
        ("new_spoof_signals", "New Spoof Signals (period)"),
        ("high_risk_vessels", "High Risk Vessels (score >= 75)"),
        ("eez_crossings", "EEZ Boundary Crossings (period)"),
    ]:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(60, 6, f"{label}:", new_x="END")
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, str(stats.get(key, 0)), new_x="LMARGIN", new_y="NEXT")

    # Top active vessels
    if top_vessels:
        pdf.ln(5)
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_fill_color(10, 22, 40)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(0, 8, "  MOST ACTIVE VESSELS", fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
        pdf.ln(3)

        pdf.set_font("Helvetica", "B", 9)
        pdf.set_fill_color(240, 240, 240)
        pdf.cell(40, 5, "MMSI", border=1, fill=True, align="C")
        pdf.cell(40, 5, "Positions", border=1, fill=True, align="C", new_x="LMARGIN", new_y="NEXT")

        pdf.set_font("Helvetica", "", 9)
        for v in top_vessels:
            pdf.cell(40, 5, str(v["mmsi"]), border=1, align="C")
            pdf.cell(40, 5, str(v["pos_count"]), border=1, align="C", new_x="LMARGIN", new_y="NEXT")

    # Classification footer
    pdf.ln(10)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(128, 128, 128)
    pdf.cell(0, 5, "CLASSIFICATION: UNCLASSIFIED // FOR OFFICIAL USE ONLY", align="C", new_x="LMARGIN", new_y="NEXT")

    # Save PDF
    os.makedirs(REPORTS_DIR, exist_ok=True)
    timestamp_str = now.strftime("%Y%m%d_%H%M%S")
    filename = f"digest_{report_id}_{timestamp_str}.pdf"
    filepath = os.path.join(REPORTS_DIR, filename)
    pdf.output(filepath)

    # Update output record
    summary = json.dumps(stats)
    await db.execute(
        """
        UPDATE scheduled_report_outputs
        SET status = 'completed', pdf_path = $1, summary = $2::jsonb, generated_at = NOW()
        WHERE id = $3
        """,
        filepath, summary, output_id,
    )

    # Update last_run_at on the report
    await db.execute(
        "UPDATE scheduled_reports SET last_run_at = NOW() WHERE id = $1",
        report_id,
    )

    logger.info("Generated digest report %d -> %s", report_id, filepath)
    return filepath


async def get_scheduled_reports() -> list[dict]:
    """List all scheduled reports."""
    db = get_db()
    rows = await db.fetch(
        """
        SELECT id, name, report_type, schedule_cron, config,
               enabled, last_run_at, created_at
        FROM scheduled_reports
        ORDER BY created_at DESC
        """
    )
    return [
        {
            "id": r["id"],
            "name": r["name"],
            "report_type": r["report_type"],
            "schedule_cron": r["schedule_cron"],
            "config": json.loads(r["config"]) if r["config"] else {},
            "enabled": r["enabled"],
            "last_run_at": r["last_run_at"].isoformat() if r["last_run_at"] else None,
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]


async def create_scheduled_report(name: str, report_type: str = "daily_digest",
                                   schedule_cron: str = "0 6 * * *",
                                   config: dict | None = None) -> dict:
    """Create a new scheduled report."""
    db = get_db()
    row = await db.fetchrow(
        """
        INSERT INTO scheduled_reports (name, report_type, schedule_cron, config)
        VALUES ($1, $2, $3, $4::jsonb)
        RETURNING id, name, report_type, schedule_cron, enabled, created_at
        """,
        name, report_type, schedule_cron, json.dumps(config or {}),
    )
    return {
        "id": row["id"],
        "name": row["name"],
        "report_type": row["report_type"],
        "schedule_cron": row["schedule_cron"],
        "enabled": row["enabled"],
        "created_at": row["created_at"].isoformat(),
    }


async def get_report_outputs(report_id: int, limit: int = 20) -> list[dict]:
    """Get output history for a scheduled report."""
    db = get_db()
    rows = await db.fetch(
        """
        SELECT id, report_id, status, pdf_path, summary, generated_at
        FROM scheduled_report_outputs
        WHERE report_id = $1
        ORDER BY generated_at DESC
        LIMIT $2
        """,
        report_id, limit,
    )
    return [
        {
            "id": r["id"],
            "report_id": r["report_id"],
            "status": r["status"],
            "has_pdf": r["pdf_path"] is not None,
            "summary": json.loads(r["summary"]) if r["summary"] else None,
            "generated_at": r["generated_at"].isoformat() if r["generated_at"] else None,
        }
        for r in rows
    ]
