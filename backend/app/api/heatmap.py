from fastapi import APIRouter, Query

from app.database import get_db

router = APIRouter()


@router.get("/spoof")
async def spoof_heatmap(
    hours: int = Query(24, ge=1, le=720),
):
    """Return spoof signal points for frontend heatmap rendering."""
    db = get_db()
    async with db.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT ST_X(geom) AS lon, ST_Y(geom) AS lat,
                   anomaly_type::text AS anomaly_type
            FROM spoof_signals
            WHERE detected_at > NOW() - make_interval(hours => $1)
            ORDER BY detected_at DESC
            LIMIT 10000
            """,
            hours,
        )

    return {
        "count": len(rows),
        "points": [
            {
                "lon": float(r["lon"]),
                "lat": float(r["lat"]),
                "anomaly_type": r["anomaly_type"],
                "weight": 1,
            }
            for r in rows
        ],
    }
