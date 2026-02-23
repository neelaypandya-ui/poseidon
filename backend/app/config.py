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

    # SAR processing
    sar_scene_cache_dir: str = "/app/sar_data"
    sar_cfar_guard_pixels: int = 4
    sar_cfar_bg_pixels: int = 16
    sar_cfar_pfa: float = 1e-3
    sar_match_radius_m: float = 5000.0
    sar_match_time_window_s: float = 3600.0

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
