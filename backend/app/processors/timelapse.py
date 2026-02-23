import os
import asyncio
import logging
from pathlib import Path

import numpy as np

from app.database import get_db

logger = logging.getLogger("poseidon.timelapse")

OUTPUT_WIDTH = 3840
OUTPUT_HEIGHT = 2160


def _build_frames(tiff_paths: list[str]) -> list[np.ndarray]:
    """Read TCI TIFFs and resize to 3840x2160 frames. Runs in a thread."""
    import rasterio
    from rasterio.enums import Resampling

    frames = []
    for path in tiff_paths:
        try:
            with rasterio.open(path) as src:
                # Read RGB bands (TCI is bands 1, 2, 3)
                data = src.read(
                    [1, 2, 3],
                    out_shape=(3, OUTPUT_HEIGHT, OUTPUT_WIDTH),
                    resampling=Resampling.bilinear,
                )
                # Convert from (C, H, W) to (H, W, C) for imageio
                frame = np.moveaxis(data, 0, -1).astype(np.uint8)
                frames.append(frame)
        except Exception as e:
            logger.warning("Failed to read TIFF %s: %s", path, e)
            continue

    return frames


def _compile_mp4(frames: list[np.ndarray], output_path: str, fps: int = 2) -> None:
    """Compile frames into an MP4 video. Runs in a thread."""
    import imageio.v3 as iio

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Write MP4 using imageio with ffmpeg plugin
    iio.imwrite(
        output_path,
        frames,
        plugin="pyav",
        codec="libx264",
        fps=fps,
    )
    logger.info("Timelapse MP4 written: %s (%d frames)", output_path, len(frames))


async def generate_timelapse(job_id: int) -> None:
    """
    Generate a timelapse MP4 for a timelapse_jobs record.

    Finds completed optical_scenes within the job's bbox and date range,
    reads their TCI TIFFs, resizes to 3840x2160, and compiles into MP4.
    """
    db = get_db()

    # Fetch job details
    async with db.acquire() as conn:
        job = await conn.fetchrow(
            """
            SELECT id, start_date, end_date, composite_type,
                   ST_AsText(bbox_geom) as bbox_wkt
            FROM timelapse_jobs WHERE id = $1
            """,
            job_id,
        )
    if not job:
        logger.error("Timelapse job %d not found", job_id)
        return

    # Mark as processing
    async with db.acquire() as conn:
        await conn.execute(
            "UPDATE timelapse_jobs SET status = 'processing' WHERE id = $1", job_id
        )

    try:
        # Find completed optical scenes within bbox and date range
        async with db.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, file_path
                FROM optical_scenes
                WHERE status IN ('completed', 'downloaded')
                  AND ST_Intersects(
                      footprint,
                      (SELECT bbox_geom FROM timelapse_jobs WHERE id = $1)
                  )
                  AND acquisition_date >= $2
                  AND acquisition_date <= $3
                ORDER BY acquisition_date ASC
                """,
                job_id,
                job["start_date"],
                job["end_date"],
            )

        if not rows:
            logger.warning("Timelapse job %d: no completed optical scenes found", job_id)
            async with db.acquire() as conn:
                await conn.execute(
                    "UPDATE timelapse_jobs SET status = 'failed', scene_count = 0 WHERE id = $1",
                    job_id,
                )
            return

        tiff_paths = [r["file_path"] for r in rows if r["file_path"] and r["file_path"].startswith("/")]

        if not tiff_paths:
            logger.warning("Timelapse job %d: no local TIFF files available", job_id)
            async with db.acquire() as conn:
                await conn.execute(
                    "UPDATE timelapse_jobs SET status = 'failed', scene_count = 0 WHERE id = $1",
                    job_id,
                )
            return

        # Update scene count
        async with db.acquire() as conn:
            await conn.execute(
                "UPDATE timelapse_jobs SET scene_count = $1 WHERE id = $2",
                len(tiff_paths),
                job_id,
            )

        # Build frames in a thread (CPU-bound rasterio work)
        frames = await asyncio.to_thread(_build_frames, tiff_paths)

        if not frames:
            logger.warning("Timelapse job %d: no valid frames could be built", job_id)
            async with db.acquire() as conn:
                await conn.execute(
                    "UPDATE timelapse_jobs SET status = 'failed' WHERE id = $1", job_id
                )
            return

        # Compile MP4 in a thread (CPU-bound encoding work)
        output_dir = os.path.join("/app/sar_data/timelapse")
        output_path = os.path.join(output_dir, f"{job_id}.mp4")

        await asyncio.to_thread(_compile_mp4, frames, output_path)

        # Mark as completed
        async with db.acquire() as conn:
            await conn.execute(
                """
                UPDATE timelapse_jobs
                SET status = 'completed', output_path = $1, scene_count = $2
                WHERE id = $3
                """,
                output_path,
                len(frames),
                job_id,
            )

        logger.info(
            "Timelapse job %d completed: %d frames -> %s",
            job_id, len(frames), output_path,
        )

    except Exception as e:
        logger.error("Timelapse job %d failed: %s", job_id, e)
        async with db.acquire() as conn:
            await conn.execute(
                "UPDATE timelapse_jobs SET status = 'failed' WHERE id = $1", job_id
            )
