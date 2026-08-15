import pytest
from pydantic import ValidationError

from vector_pulse.ingestion.mqtt_consumer import (
    parse_telemetry_payload,
)


def valid_payload() -> bytes:
    return b"""
    {
        "tag_id": "tag-001",
        "sequence_number": 42,
        "timestamp": "2026-08-14T12:00:00Z",
        "position": {
            "x": 10.5,
            "y": 4.2,
            "quality": 0.95
        },
        "motion": {
            "speed_mps": 1.2
        },
        "condition": {
            "temperature_c": 25.0,
            "vibration_rms": 0.15,
            "battery_percent": 88.0
        }
    }
    """


def test_parse_valid_mqtt_payload() -> None:
    telemetry = parse_telemetry_payload(valid_payload())

    assert telemetry.tag_id == "tag-001"
    assert telemetry.sequence_number == 42
    assert telemetry.position.x == 10.5


def test_parse_invalid_json_is_rejected() -> None:
    with pytest.raises(ValidationError):
        parse_telemetry_payload(b"not-json")


def test_parse_invalid_telemetry_is_rejected() -> None:
    payload = valid_payload().replace(
        b'"battery_percent": 88.0',
        b'"battery_percent": 500.0',
    )

    with pytest.raises(ValidationError):
        parse_telemetry_payload(payload)