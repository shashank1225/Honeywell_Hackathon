from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    app_name: str = "AABOS"
    app_version: str = "0.1.0"
    debug: bool = False

    # Use 127.0.0.1 to prefer IPv4 so macOS localhost IPv6 Postgres isn't used
    database_url: str = "postgresql://aabos:aabos@127.0.0.1:5433/aabos"
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_telemetry_topic: str = "aabos.telemetry"

    simulation_enabled: bool = True
    simulation_interval_seconds: float = 5.0

    mcp_host: str = "0.0.0.0"
    mcp_port: int = 8001

    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
