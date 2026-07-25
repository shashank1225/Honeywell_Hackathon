from functools import lru_cache
from pathlib import Path

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
    kafka_consumer_group: str = "aabos-telemetry-processor"
    telemetry_window_samples: int = 12
    strategic_worker_enabled: bool = True
    autonomous_control_enabled: bool = True
    autonomous_power_threshold_kw: float = 3.5
    autonomous_min_comfort_pct: float = 90.0

    simulation_enabled: bool = True
    simulation_interval_seconds: float = 5.0

    energyplus_executable: str | None = None
    energyplus_idf_path: Path | None = None
    energyplus_baseline_idf_path: Path = Path("energyplus/baseline.idf")
    energyplus_generated_idf_path: Path = Path("energyplus/generated/modified.idf")
    energyplus_weather_path: Path | None = None
    energyplus_output_dir: Path = Path("var/energyplus")
    energyplus_zone_name: str = "main"

    mcp_host: str = "0.0.0.0"
    mcp_port: int = 8001

    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
