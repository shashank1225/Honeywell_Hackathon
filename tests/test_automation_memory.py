import time
from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.automation_episode import AutomationEpisodeRecord
from app.schemas.telemetry import AutomationEpisode, OperatingPolicy
from app.services import automation_memory as automation_memory_module
from app.services.automation_memory import AutomationMemory


def episode() -> AutomationEpisode:
    return AutomationEpisode(
        timestamp=datetime.now(UTC),
        policy=OperatingPolicy.ENERGY_SAVER,
        reward=0.7,
        energy_kwh=0.01,
        comfort_score=0.95,
        carbon_kg=0.004,
        confidence=0.8,
    )


def test_memory_persists_episodes_asynchronously(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(automation_memory_module, "get_engine", lambda: engine)
    monkeypatch.setattr(automation_memory_module, "get_session_factory", lambda: sessions)
    memory = AutomationMemory(persist_to_database=True)
    memory.start()
    try:
        memory.record(episode())
        for _ in range(50):
            with sessions() as session:
                records = session.scalars(select(AutomationEpisodeRecord)).all()
            if records:
                break
            time.sleep(0.01)
        assert len(records) == 1
        assert records[0].policy == OperatingPolicy.ENERGY_SAVER.value
    finally:
        memory.stop()
