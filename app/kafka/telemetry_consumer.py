"""Fault-isolated Kafka consumer that decouples telemetry producers from processors."""

from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Callable

from kafka import KafkaConsumer
from kafka.errors import KafkaError

from app.config import get_settings
from app.schemas.telemetry import BuildingTelemetry

logger = logging.getLogger(__name__)


class TelemetryKafkaConsumer:
    """Consumes telemetry events in a resilient background thread."""

    def __init__(self, handler: Callable[[BuildingTelemetry], None]) -> None:
        self._handler = handler
        self._running = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._running.set()
        self._thread = threading.Thread(target=self._run, name="aabos-kafka-consumer", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running.clear()
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    def _run(self) -> None:
        settings = get_settings()
        while self._running.is_set():
            consumer = None
            try:
                consumer = KafkaConsumer(
                    settings.kafka_telemetry_topic,
                    bootstrap_servers=settings.kafka_bootstrap_servers.split(","),
                    group_id=settings.kafka_consumer_group,
                    auto_offset_reset="latest",
                    enable_auto_commit=True,
                    consumer_timeout_ms=1000,
                    value_deserializer=lambda value: value.decode("utf-8"),
                )
                while self._running.is_set():
                    for message in consumer:
                        try:
                            self._handler(BuildingTelemetry.model_validate(json.loads(message.value)))
                        except Exception:
                            logger.exception("Ignoring malformed Kafka telemetry event")
            except KafkaError:
                logger.warning("Kafka telemetry consumer unavailable; retrying in 2 seconds")
                time.sleep(2)
            except Exception:
                logger.exception("Kafka telemetry consumer failure; retrying in 2 seconds")
                time.sleep(2)
            finally:
                if consumer is not None:
                    consumer.close()
