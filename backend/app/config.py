from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # AIS
    aisstream_api_key: str = ""

    # Database
    postgres_user: str = "poseidon"
    postgres_password: str = "poseidon_secret"
    postgres_db: str = "poseidon"
    postgres_host: str = "postgis"
    postgres_port: int = 5432

    # Redis
    redis_host: str = "redis"
    redis_port: int = 6379

    # Ingestor
    buffer_flush_interval: float = 2.0
    buffer_batch_size: int = 500

    # Dark vessel detection
    dark_vessel_check_interval: int = 300  # seconds
    dark_vessel_gap_hours: float = 2.0
    dark_vessel_active_window_hours: float = 24.0

    # Copernicus / Sentinel-1
    copernicus_client_id: str = ""
    copernicus_client_secret: str = ""
    copernicus_username: str = ""
    copernicus_password: str = ""

    # NASA Earthdata (VIIRS / FIRMS)
    earthdata_username: str = ""
    earthdata_token: str = ""

    # Equasis
    equasis_email: str = ""
    equasis_password: str = ""

    # OpenSanctions
    opensanctions_api_key: str = ""

    # AOI monitoring
    aoi_check_interval: int = 60

    # Spoof detection
    spoof_scan_interval: int = 120
    spoof_impossible_speed_knots: float = 50.0
    spoof_cluster_window_minutes: int = 5

    # SAR processing
    sar_scene_cache_dir: str = "/app/sar_data"
    sar_cfar_guard_pixels: int = 4
    sar_cfar_bg_pixels: int = 16
    sar_cfar_pfa: float = 1e-3
    sar_match_radius_m: float = 5000.0
    sar_match_time_window_s: float = 3600.0

    # JWT Authentication
    auth_enabled: bool = False
    jwt_secret_key: str = "poseidon-secret-change-in-production"
    jwt_expire_minutes: int = 480  # 8 hours

    # CMEMS Ocean Currents
    cmems_username: str = ""
    cmems_password: str = ""

    # EEZ monitoring
    eez_check_interval: int = 120  # seconds

    # Acoustic events
    acoustic_fetch_interval: int = 600  # seconds

    # Scheduled reports
    report_check_interval: int = 300  # seconds

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
