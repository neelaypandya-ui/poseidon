"""
Route prediction service for vessels.

Uses dead reckoning with confidence cones to project vessel routes
forward based on current position, speed, and course over ground.
"""

import math
import logging
from datetime import datetime, timezone

from app.database import get_db

logger = logging.getLogger("poseidon.route_prediction")

# Conversion constants
NM_TO_KM = 1.852
DEG_LAT_KM = 111.32
BASE_UNCERTAINTY_NM = 5.0
UNCERTAINTY_GROWTH_NM = 3.0


def _project_point(lat: float, lon: float, sog_knots: float, cog_deg: float, hours: float) -> tuple[float, float]:
    """Project a position forward using dead reckoning.

    Args:
        lat: Current latitude in degrees.
        lon: Current longitude in degrees.
        sog_knots: Speed over ground in knots.
        cog_deg: Course over ground in degrees.
        hours: Time to project forward in hours.

    Returns:
        Tuple of (new_lat, new_lon) in degrees.
    """
    if sog_knots is None or cog_deg is None or sog_knots <= 0:
        return lat, lon

    cog_rad = math.radians(cog_deg)
    lat_rad = math.radians(lat)

    distance_km = sog_knots * NM_TO_KM * hours

    new_lat = lat + (distance_km / DEG_LAT_KM) * math.cos(cog_rad)
    new_lon = lon + (distance_km / (DEG_LAT_KM * math.cos(lat_rad))) * math.sin(cog_rad)

    # Clamp latitude
    new_lat = max(-90.0, min(90.0, new_lat))
    # Wrap longitude
    new_lon = ((new_lon + 180) % 360) - 180

    return new_lat, new_lon


def _generate_confidence_cone(
    route_points: list[tuple[float, float, float]],
    confidence_nm: float,
) -> list[list[float]]:
    """Generate a confidence polygon around the predicted route.

    Creates a polygon by offsetting route points laterally by the
    uncertainty distance at each point.

    Args:
        route_points: List of (lat, lon, uncertainty_nm) tuples.
        confidence_nm: Multiplier for confidence band (1.04 for 70%, 1.645 for 90%).

    Returns:
        List of [lon, lat] coordinate pairs forming a closed polygon.
    """
    if len(route_points) < 2:
        return []

    left_side = []
    right_side = []

    for lat, lon, uncertainty_nm in route_points:
        offset_nm = uncertainty_nm * confidence_nm
        offset_deg_lat = offset_nm / 60.0
        lat_rad = math.radians(lat)
        offset_deg_lon = offset_nm / (60.0 * max(math.cos(lat_rad), 0.01))

        # For simplicity, offset perpendicular to the route direction
        # Using the next/prev point to determine direction is complex;
        # use lateral offset in lat/lon space
        left_side.append([lon - offset_deg_lon, lat + offset_deg_lat])
        right_side.append([lon + offset_deg_lon, lat - offset_deg_lat])

    # Close the polygon: left side forward, right side backward
    right_side.reverse()
    polygon = left_side + right_side + [left_side[0]]

    return polygon


async def predict_route(mmsi: int, hours: float = 24) -> dict:
    """Predict a vessel's future route using dead reckoning.

    Args:
        mmsi: Maritime Mobile Service Identity of the vessel.
        hours: Number of hours to project forward (default 24).

    Returns:
        Dictionary containing:
            - mmsi: Vessel MMSI
            - route_geom: List of [lon, lat] predicted positions
            - confidence_70: GeoJSON polygon for 70% confidence band
            - confidence_90: GeoJSON polygon for 90% confidence band
            - eta: Estimated time of arrival if destination known
            - predicted_at: Timestamp of prediction
            - hours_ahead: Hours projected forward
    """
    db = get_db()

    # Get last known position
    latest = await db.fetchrow(
        """
        SELECT mmsi, ST_X(geom) as lon, ST_Y(geom) as lat,
               sog, cog, heading, timestamp, name, ship_type::text, destination
        FROM latest_vessel_positions
        WHERE mmsi = $1
        """,
        mmsi,
    )

    if not latest:
        logger.warning("No position found for MMSI %d", mmsi)
        return {"error": "Vessel not found", "mmsi": mmsi}

    sog = float(latest["sog"] or 0)
    cog = float(latest["cog"] or 0)
    lat = float(latest["lat"])
    lon = float(latest["lon"])

    if sog < 0.5:
        logger.info("MMSI %d is stationary (SOG=%.1f), returning single point", mmsi, sog)
        return {
            "mmsi": mmsi,
            "route_geom": [[lon, lat]],
            "confidence_70": None,
            "confidence_90": None,
            "eta": None,
            "predicted_at": datetime.now(timezone.utc).isoformat(),
            "hours_ahead": hours,
            "vessel_name": latest["name"],
            "ship_type": latest["ship_type"],
        }

    # Get historical track for potential course adjustments
    history = await db.fetch(
        """
        SELECT ST_X(geom) as lon, ST_Y(geom) as lat, sog, cog, timestamp
        FROM vessel_positions
        WHERE mmsi = $1 AND timestamp > NOW() - INTERVAL '48 hours'
        ORDER BY timestamp ASC
        """,
        mmsi,
    )

    # If we have enough history, compute weighted average COG for stability
    if len(history) >= 5:
        recent_cogs = []
        recent_sogs = []
        for h in history[-10:]:
            h_cog = h["cog"]
            h_sog = h["sog"]
            if h_cog is not None and h_sog is not None and h_sog > 0.5:
                recent_cogs.append(math.radians(float(h_cog)))
                recent_sogs.append(float(h_sog))

        if recent_cogs:
            # Circular mean for COG
            sin_sum = sum(math.sin(c) for c in recent_cogs)
            cos_sum = sum(math.cos(c) for c in recent_cogs)
            avg_cog_rad = math.atan2(sin_sum, cos_sum)
            cog = math.degrees(avg_cog_rad) % 360

            # Average SOG
            sog = sum(recent_sogs) / len(recent_sogs)

    # Project route forward at hourly intervals
    route_points = []  # (lat, lon, uncertainty_nm)
    route_geom = [[lon, lat]]  # [lon, lat] pairs for output
    current_lat, current_lon = lat, lon

    # Generate points at 1-hour intervals
    num_steps = int(hours)
    step_hours = 1.0
    if hours < 1:
        num_steps = 1
        step_hours = hours

    for i in range(1, num_steps + 1):
        t = i * step_hours
        new_lat, new_lon = _project_point(current_lat, current_lon, sog, cog, step_hours)

        # Uncertainty grows with sqrt of time
        uncertainty_nm = BASE_UNCERTAINTY_NM + UNCERTAINTY_GROWTH_NM * math.sqrt(t)

        route_points.append((new_lat, new_lon, uncertainty_nm))
        route_geom.append([new_lon, new_lat])
        current_lat, current_lon = new_lat, new_lon

    # Generate confidence cones
    # Add the starting point with zero uncertainty
    all_points = [(lat, lon, 0.0)] + route_points

    # 70% confidence band (z = 1.04)
    cone_70 = _generate_confidence_cone(all_points, 1.04)
    # 90% confidence band (z = 1.645)
    cone_90 = _generate_confidence_cone(all_points, 1.645)

    confidence_70_geojson = {
        "type": "Feature",
        "properties": {"confidence": 0.70},
        "geometry": {
            "type": "Polygon",
            "coordinates": [cone_70],
        },
    } if cone_70 else None

    confidence_90_geojson = {
        "type": "Feature",
        "properties": {"confidence": 0.90},
        "geometry": {
            "type": "Polygon",
            "coordinates": [cone_90],
        },
    } if cone_90 else None

    # Check for ETA if destination known
    eta = None
    if latest["destination"]:
        eta_row = await db.fetchrow(
            "SELECT eta FROM vessels WHERE mmsi = $1 AND eta IS NOT NULL",
            mmsi,
        )
        if eta_row and eta_row["eta"]:
            eta = eta_row["eta"].isoformat()

    predicted_at = datetime.now(timezone.utc)

    # Store prediction in route_predictions table
    try:
        route_geojson = {
            "type": "LineString",
            "coordinates": route_geom,
        }
        await db.execute(
            """
            INSERT INTO route_predictions
                (mmsi, predicted_route, confidence_70, confidence_90,
                 hours_ahead, sog_used, cog_used, predicted_at)
            VALUES ($1, $2::jsonb, $3::jsonb, $4::jsonb, $5, $6, $7, $8)
            """,
            mmsi,
            __import__("json").dumps(route_geojson),
            __import__("json").dumps(confidence_70_geojson) if confidence_70_geojson else None,
            __import__("json").dumps(confidence_90_geojson) if confidence_90_geojson else None,
            hours,
            sog,
            cog,
            predicted_at,
        )
    except Exception as e:
        logger.error("Failed to store route prediction for MMSI %d: %s", mmsi, e)

    result = {
        "mmsi": mmsi,
        "route_geom": route_geom,
        "confidence_70": confidence_70_geojson,
        "confidence_90": confidence_90_geojson,
        "eta": eta,
        "predicted_at": predicted_at.isoformat(),
        "hours_ahead": hours,
        "vessel_name": latest["name"],
        "ship_type": latest["ship_type"],
        "sog_used": round(sog, 2),
        "cog_used": round(cog, 2),
    }

    logger.info(
        "Route prediction for MMSI %d: %d points, %.1f hours, SOG=%.1f, COG=%.1f",
        mmsi, len(route_geom), hours, sog, cog,
    )

    return result


async def get_predictions(mmsi: int, limit: int = 5) -> list[dict]:
    """Get stored route predictions for a vessel.

    Args:
        mmsi: Maritime Mobile Service Identity of the vessel.
        limit: Maximum number of predictions to return (default 5).

    Returns:
        List of prediction dictionaries.
    """
    db = get_db()

    rows = await db.fetch(
        """
        SELECT id, mmsi, predicted_route, confidence_70, confidence_90,
               hours_ahead, sog_used, cog_used, predicted_at
        FROM route_predictions
        WHERE mmsi = $1
        ORDER BY predicted_at DESC
        LIMIT $2
        """,
        mmsi,
        limit,
    )

    results = []
    for row in rows:
        import json
        record = {
            "id": row["id"],
            "mmsi": row["mmsi"],
            "predicted_route": json.loads(row["predicted_route"]) if row["predicted_route"] else None,
            "confidence_70": json.loads(row["confidence_70"]) if row["confidence_70"] else None,
            "confidence_90": json.loads(row["confidence_90"]) if row["confidence_90"] else None,
            "hours_ahead": row["hours_ahead"],
            "sog_used": row["sog_used"],
            "cog_used": row["cog_used"],
            "predicted_at": row["predicted_at"].isoformat() if row["predicted_at"] else None,
        }
        results.append(record)

    return results
