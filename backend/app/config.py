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
