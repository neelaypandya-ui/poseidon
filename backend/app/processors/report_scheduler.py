"""Scheduled report background processor.

Checks scheduled_reports table periodically and triggers digest
generation for enabled reports that are due based on their cron schedule.
Uses a simple hour-based check rather than full cron parsing.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta

from app.database import get_db
from app.services.scheduled_report_service import generate_digest

logger = logging.getLogger("poseidon.report_scheduler")

CHECK_INTERVAL = 300  # 5 minutes


async def run_report_scheduler() -> None:
    """Background task: check for and run due scheduled reports."""
    logger.info("Report scheduler starting (interval=%ds)", CHECK_INTERVAL)
    await asyncio.sleep(20)  # Wait for DB init

    while True:
        try:
            await _check_and_run_reports()
        except asyncio.CancelledError:
            logger.info("Report scheduler cancelled")
            return
        except Exception as e:
            logger.error("Report scheduler error: %s", e)

        await asyncio.sleep(CHECK_INTERVAL)


async def _check_and_run_reports() -> None:
    """Check for reports that need to be run."""
    db = get_db()
    now = datetime.now(timezone.utc)

    # Find enabled reports that haven't run in the last 23 hours
    # (simplified cron: just check if enough time has passed)
    rows = await db.fetch(
        """
        SELECT id, name, schedule_cron, config
        FROM scheduled_reports
        WHERE enabled = TRUE
          AND (last_run_at IS NULL OR last_run_at < NOW() - INTERVAL '23 hours')
        """
    )

    for report in rows:
        # Parse simple cron hour (e.g., "0 6 * * *" -> hour 6)
        try:
            cron_parts = report["schedule_cron"].split()
            cron_hour = int(cron_parts[1]) if len(cron_parts) >= 2 else 6
        except (ValueError, IndexError):
            cron_hour = 6

        # Only run if we're within 30 minutes of the scheduled hour
        if abs(now.hour - cron_hour) > 0 and abs(now.hour - cron_hour) != 24:
            continue

        logger.info("Running scheduled report: %s (id=%d)", report["name"], report["id"])

        # Create output record
        output_row = await db.fetchrow(
            """
            INSERT INTO scheduled_report_outputs (report_id, status)
            VALUES ($1, 'generating')
            RETURNING id
            """,
            report["id"],
        )

        try:
            await generate_digest(report["id"], output_row["id"])
        except Exception as e:
            logger.error("Failed to generate report %d: %s", report["id"], e)
            await db.execute(
                "UPDATE scheduled_report_outputs SET status = 'failed' WHERE id = $1",
                output_row["id"],
            )
