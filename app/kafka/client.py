from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable

from app.config import get_settings

_producer: KafkaProducer | None = None


def get_kafka_producer() -> KafkaProducer | None:
    """Return a singleton Kafka producer, or None if brokers are unavailable."""
    global _producer
    if _producer is None:
        settings = get_settings()
        try:
            _producer = KafkaProducer(
                bootstrap_servers=settings.kafka_bootstrap_servers.split(","),
                value_serializer=lambda value: value.encode("utf-8"),
            )
        except NoBrokersAvailable:
            return None
    return _producer


def check_kafka_connection() -> bool:
    """Verify Kafka broker connectivity for health checks."""
    producer = get_kafka_producer()
    if producer is None:
        return False
    try:
        producer.bootstrap_connected()
        return True
    except Exception:
        return False
