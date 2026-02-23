"""
Replay engine service for historical vessel movement playback.

Creates replay jobs that allow the frontend to animate historical
vessel positions within a specified time range and geographic area.
"""

import logging
from datetime import datetime, timezone

from app.database import get_db

logger = logging.getLogger("poseidon.replay_service")

# Default time bucket interval for frame grouping (seconds)
DEFAULT_BUCKET_SECONDS = 60


async def create_replay_job(
    mmsi: int | None,
    bbox: tuple[float, float, float, float] | None,
    start_time: str,
    end_time: str,
    speed: float = 10,
) -> int:
    """Create a new replay job in the database.

    Args:
        mmsi: Optional MMSI to filter to a single vessel.
        bbox: Optional bounding box (min_lon, min_lat, max_lon, max_lat).
        start_time: ISO 8601 start time for the replay window.
        end_time: ISO 8601 end time for the replay window.
        speed: Playback speed multiplier (default 10x).

    Returns:
        The newly created job ID.
    """
    db = get_db()

    start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
    end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))

    if end_dt <= start_dt:
        raise ValueError("end_time must be after start_time")

    job_id = await db.fetchval(
        """
        INSERT INTO replay_jobs
            (mmsi, min_lon, min_lat, max_lon, max_lat,
             start_time, end_time, speed, status, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'created', NOW())
        RETURNING id
        """,
        mmsi,
        bbox[0] if bbox else None,
        bbox[1] if bbox else None,
        bbox[2] if bbox else None,
        bbox[3] if bbox else None,
        start_dt,
        end_dt,
        speed,
    )

    logger.info(
        "Created replay job %d: MMSI=%s, bbox=%s, %s to %s, speed=%sx",
        job_id, mmsi, bbox, start_time, end_time, speed,
    )

    return job_id


async def get_replay_data(job_id: int) -> dict:
    """Get all vessel position frames for a replay job.

    Queries vessel_positions for the job's time range and optional filters,
    groups positions into time buckets (1-minute intervals), and returns
    structured frame data for frontend animation.

    Args:
        job_id: The replay job ID.

    Returns:
        Dictionary containing:
            - job_id: The replay job ID
            - frames: List of frame dicts with timestamp and vessel positions
            - total_frames: Total number of frames
            - start_time: Replay start time
            - end_time: Replay end time
            - speed: Playback speed multiplier
    """
    db = get_db()

    # Get job details
    job = await db.fetchrow(
        """
        SELECT id, mmsi, min_lon, min_lat, max_lon, max_lat,
               start_time, end_time, speed, status
        FROM replay_jobs
        WHERE id = $1
        """,
        job_id,
    )

    if not job:
        return {"error": "Replay job not found", "job_id": job_id}

    job = dict(job)

    # Update status to processing
    await db.execute(
        "UPDATE replay_jobs SET status = 'processing' WHERE id = $1",
        job_id,
    )

    # Build query based on job parameters
    query = """
        SELECT vp.mmsi,
               ST_X(vp.geom) as lon, ST_Y(vp.geom) as lat,
               vp.sog, vp.cog, vp.timestamp
        FROM vessel_positions vp
        WHERE vp.timestamp >= $1 AND vp.timestamp <= $2
    """
    params: list = [job["start_time"], job["end_time"]]
    idx = 3

    # Filter by MMSI if specified
    if job["mmsi"] is not None:
        query += f" AND vp.mmsi = ${idx}"
        params.append(job["mmsi"])
        idx += 1

    # Filter by bounding box if specified
    if all(job.get(k) is not None for k in ["min_lon", "min_lat", "max_lon", "max_lat"]):
        query += f"""
            AND ST_Intersects(
                vp.geom,
                ST_MakeEnvelope(${idx}, ${idx+1}, ${idx+2}, ${idx+3}, 4326)
            )
        """
        params.extend([job["min_lon"], job["min_lat"], job["max_lon"], job["max_lat"]])
        idx += 4

    query += " ORDER BY vp.timestamp ASC"

    rows = await db.fetch(query, *params)

    # Group into time buckets (1-minute intervals)
    frames: dict[str, list[dict]] = {}

    for row in rows:
        ts = row["timestamp"]
        # Truncate to minute for bucketing
        bucket_ts = ts.replace(second=0, microsecond=0)
        bucket_key = bucket_ts.isoformat()

        if bucket_key not in frames:
            frames[bucket_key] = []

        # Deduplicate by MMSI within the same bucket (keep latest)
        existing_mmsis = {v["mmsi"] for v in frames[bucket_key]}
        if row["mmsi"] in existing_mmsis:
            # Replace with newer position
            frames[bucket_key] = [
                v for v in frames[bucket_key] if v["mmsi"] != row["mmsi"]
            ]

        frames[bucket_key].append({
            "mmsi": row["mmsi"],
            "lon": float(row["lon"]),
            "lat": float(row["lat"]),
            "sog": float(row["sog"]) if row["sog"] is not None else 0,
            "cog": float(row["cog"]) if row["cog"] is not None else 0,
        })

    # Convert to sorted frame list
    sorted_keys = sorted(frames.keys())
    frame_list = [
        {"timestamp": key, "vessels": frames[key]}
        for key in sorted_keys
    ]

    # Update job status
    await db.execute(
        "UPDATE replay_jobs SET status = 'ready', total_frames = $1 WHERE id = $2",
        len(frame_list),
        job_id,
    )

    logger.info(
        "Replay job %d: %d frames, %d total positions",
        job_id, len(frame_list), len(rows),
    )

    return {
        "job_id": job_id,
        "frames": frame_list,
        "total_frames": len(frame_list),
        "start_time": job["start_time"].isoformat(),
        "end_time": job["end_time"].isoformat(),
        "speed": job["speed"],
    }


async def get_replay_status(job_id: int) -> dict:
    """Get the current status of a replay job.

    Args:
        job_id: The replay job ID.

    Returns:
        Dictionary with job status information.
    """
    db = get_db()

    row = await db.fetchrow(
        """
        SELECT id, mmsi, min_lon, min_lat, max_lon, max_lat,
               start_time, end_time, speed, status, total_frames, created_at
        FROM replay_jobs
        WHERE id = $1
        """,
        job_id,
    )

    if not row:
        return {"error": "Replay job not found", "job_id": job_id}

    return {
        "job_id": row["id"],
        "mmsi": row["mmsi"],
        "bbox": {
            "min_lon": row["min_lon"],
            "min_lat": row["min_lat"],
            "max_lon": row["max_lon"],
            "max_lat": row["max_lat"],
        } if row["min_lon"] is not None else None,
        "start_time": row["start_time"].isoformat() if row["start_time"] else None,
        "end_time": row["end_time"].isoformat() if row["end_time"] else None,
        "speed": row["speed"],
        "status": row["status"],
        "total_frames": row["total_frames"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }
