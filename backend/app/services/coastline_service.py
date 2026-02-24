"""Classify AIS positions as terrestrial or satellite based on distance to coastline."""

import json
import logging
from pathlib import Path

from shapely.geometry import shape, Point
from shapely.ops import unary_union
from shapely.prepared import prep

logger = logging.getLogger("poseidon.coastline")

# 50 nautical miles in degrees (approximate at equator: 1 degree ≈ 60 nm)
BUFFER_DEG = 50.0 / 60.0  # ~0.8333 degrees

_prepared_buffer = None


async def init_coastline_buffer():
    """Load Natural Earth land polygons, buffer by 50nm, and prepare for fast queries."""
    global _prepared_buffer

    geojson_path = Path(__file__).parent.parent / "data" / "ne_110m_land.geojson"
    logger.info(f"Loading coastline data from {geojson_path}")

    with open(geojson_path) as f:
        data = json.load(f)

    polygons = []
    for feature in data["features"]:
        geom = shape(feature["geometry"])
        if geom.is_valid:
            polygons.append(geom)

    merged = unary_union(polygons)
    buffered = merged.buffer(BUFFER_DEG)
    _prepared_buffer = prep(buffered)

    logger.info("Coastline buffer initialized (50nm from land)")


def classify_receiver(lon: float, lat: float) -> str:
    """Return 'terrestrial' if point is within 50nm of coastline, else 'satellite'."""
    if _prepared_buffer is None:
        return "unknown"

    point = Point(lon, lat)
    if _prepared_buffer.contains(point):
        return "terrestrial"
    return "satellite"
