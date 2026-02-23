from datetime import datetime
from pydantic import BaseModel
from app.models.enums import VesselType, NavStatus, AlertStatus


class VesselBase(BaseModel):
    mmsi: int
    imo: int | None = None
    name: str | None = None
    callsign: str | None = None
    ship_type: VesselType = VesselType.UNKNOWN
    destination: str | None = None


class VesselPosition(BaseModel):
    mmsi: int
    lon: float
    lat: float
    h3_index: str | None = None
    sog: float | None = None
    cog: float | None = None
    heading: int | None = None
    nav_status: NavStatus | None = None
    timestamp: datetime


class VesselWithPosition(VesselBase):
    lon: float
    lat: float
    sog: float | None = None
    cog: float | None = None
    heading: int | None = None
    nav_status: NavStatus | None = None
    timestamp: datetime


class VesselDetail(VesselBase):
    ais_type_code: int | None = None
    dim_bow: int | None = None
    dim_stern: int | None = None
    dim_port: int | None = None
    dim_starboard: int | None = None
    eta: datetime | None = None
    lon: float | None = None
    lat: float | None = None
    sog: float | None = None
    cog: float | None = None
    heading: int | None = None
    nav_status: NavStatus | None = None
    last_seen: datetime | None = None
    track_points_6h: int = 0


class TrackPoint(BaseModel):
    lon: float
    lat: float
    sog: float | None = None
    cog: float | None = None
    timestamp: datetime


class DarkVesselAlert(BaseModel):
    id: int
    mmsi: int
    status: AlertStatus
    vessel_name: str | None = None
    ship_type: VesselType | None = None
    last_known_lon: float
    last_known_lat: float
    predicted_lon: float | None = None
    predicted_lat: float | None = None
    last_sog: float | None = None
    last_cog: float | None = None
    gap_hours: float | None = None
    search_radius_nm: float | None = None
    last_seen_at: datetime
    detected_at: datetime


class LiveVesselMessage(BaseModel):
    mmsi: int
    lon: float
    lat: float
    sog: float | None = None
    cog: float | None = None
    heading: int | None = None
    nav_status: str | None = None
    ship_type: str = "unknown"
    name: str | None = None
    timestamp: str
