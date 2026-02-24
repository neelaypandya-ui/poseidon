"""Scheduled reports REST endpoints."""

import os
import logging

from fastapi import APIRouter, Query, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.database import get_db
from app.services.scheduled_report_service import (
    get_scheduled_reports,
    create_scheduled_report,
    get_report_outputs,
    generate_digest,
)

logger = logging.getLogger("poseidon.api.scheduled_reports")

router = APIRouter()


class CreateReportRequest(BaseModel):
    name: str
    report_type: str = "daily_digest"
    schedule_cron: str = Field(default="0 6 * * *", alias="cron_expression")
    config: dict | None = None

    model_config = {"populate_by_name": True}


@router.get("")
async def list_reports():
    """List all scheduled reports."""
    reports = await get_scheduled_reports()
    return {"count": len(reports), "reports": reports}


@router.post("")
async def create_report(req: CreateReportRequest):
    """Create a new scheduled report."""
    report = await create_scheduled_report(
        name=req.name,
        report_type=req.report_type,
        schedule_cron=req.schedule_cron,
        config=req.config,
    )
    return {"status": "created", "report": report}


@router.post("/{report_id}/run")
async def run_report_now(report_id: int, background_tasks: BackgroundTasks):
    """Trigger immediate generation of a scheduled report."""
    db = get_db()

    report = await db.fetchrow("SELECT id FROM scheduled_reports WHERE id = $1", report_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")

    output_row = await db.fetchrow(
        """
        INSERT INTO scheduled_report_outputs (report_id, status)
        VALUES ($1, 'generating')
        RETURNING id
        """,
        report_id,
    )

    async def _run_digest(rid: int, oid: int):
        try:
            await generate_digest(rid, oid)
        except Exception as e:
            logger.error("Report generation failed for report %d: %s", rid, e)
            await db.execute(
                "UPDATE scheduled_report_outputs SET status = 'failed' WHERE id = $1", oid
            )

    background_tasks.add_task(_run_digest, report_id, output_row["id"])
    return {"status": "generating", "output_id": output_row["id"]}


@router.get("/{report_id}/outputs")
async def list_report_outputs(report_id: int, limit: int = Query(20, ge=1, le=100)):
    """Get output history for a scheduled report."""
    outputs = await get_report_outputs(report_id, limit)
    return {"count": len(outputs), "outputs": outputs}


@router.get("/outputs/{output_id}/download")
async def download_report_output(output_id: int):
    """Download a generated report PDF."""
    db = get_db()
    row = await db.fetchrow(
        "SELECT status, pdf_path FROM scheduled_report_outputs WHERE id = $1",
        output_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail=f"Output {output_id} not found")

    if row["status"] != "completed":
        raise HTTPException(status_code=409, detail=f"Report not completed (status: {row['status']})")

    if not row["pdf_path"] or not os.path.exists(row["pdf_path"]):
        raise HTTPException(status_code=404, detail="PDF file not found")

    return FileResponse(
        path=row["pdf_path"],
        media_type="application/pdf",
        filename=os.path.basename(row["pdf_path"]),
    )


@router.delete("/{report_id}")
async def delete_report(report_id: int):
    """Delete a scheduled report and its outputs."""
    db = get_db()
    result = await db.execute("DELETE FROM scheduled_reports WHERE id = $1", report_id)
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")
    return {"status": "deleted"}


@router.patch("/{report_id}/toggle")
async def toggle_report(report_id: int):
    """Toggle enabled/disabled status of a scheduled report."""
    db = get_db()
    row = await db.fetchrow(
        "UPDATE scheduled_reports SET enabled = NOT enabled WHERE id = $1 RETURNING id, enabled",
        report_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")
    return {"id": row["id"], "enabled": row["enabled"]}
