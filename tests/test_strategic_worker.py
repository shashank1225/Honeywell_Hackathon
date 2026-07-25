import time
from datetime import UTC, datetime

from app.schemas.telemetry import BuildingTelemetry, GoalType, StrategicGoal, StrategicJobStatus
from app.services.strategic_worker import StrategicWorkQueue
from app.services.telemetry_aggregation import TelemetryWindowAggregator


def test_strategic_work_runs_asynchronously_from_aggregated_context():
    aggregator = TelemetryWindowAggregator(max_samples=2)
    aggregator.add(BuildingTelemetry(timestamp=datetime.now(UTC), temperature_c=22, humidity_pct=45, occupancy_pct=50, power_kw=7))
    worker = StrategicWorkQueue(aggregator=aggregator)
    worker.start()
    try:
        job = worker.submit(StrategicGoal(objective=GoalType.ENERGY_REDUCTION, target_percent=10))
        for _ in range(20):
            job = worker.get(job.id)
            if job and job.status in {StrategicJobStatus.COMPLETED, StrategicJobStatus.FAILED}:
                break
            time.sleep(0.02)
        assert job is not None
        assert job.status == StrategicJobStatus.COMPLETED
        assert job.plan is not None
    finally:
        worker.stop()
