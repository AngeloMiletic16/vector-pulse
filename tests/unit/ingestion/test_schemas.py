import pytest
from pydantic import ValidationError

from vector_pulse.ingestion.schemas import TelemetryMessage


def valid_payload() -> dict:
    return {
        "tag_id": "tag-001",
        "sequence_number": 1,
        "timestamp": "2026-08-12T12:00:00Z",
        "position": {
            "x": 4.2,
            "y": 7.8,
            "quality": 0.94,
        },
        "motion": {
            "speed_mps": 0.8,
        },
        "condition": {
            "temperature_c": 26.4,
            "vibration_rms": 0.12,
            "battery_percent": 91,
        },
    }


def test_valid_telemetry_is_accepted() -> None:
    message = TelemetryMessage.model_validate(valid_payload())

    assert message.tag_id == "tag-001"
    assert message.sequence_number == 1
    assert message.position.quality == 0.94
    assert message.condition.battery_percent == 91


def test_battery_above_100_is_rejected() -> None:
    payload = valid_payload()
    payload["condition"]["battery_percent"] = 500

    with pytest.raises(ValidationError):
        TelemetryMessage.model_validate(payload)


def test_negative_position_quality_is_rejected() -> None:
    payload = valid_payload()
    payload["position"]["quality"] = -0.5

    with pytest.raises(ValidationError):
        TelemetryMessage.model_validate(payload)


def test_negative_speed_is_rejected() -> None:
    payload = valid_payload()
    payload["motion"]["speed_mps"] = -10

    with pytest.raises(ValidationError):
        TelemetryMessage.model_validate(payload)


def test_unknown_field_is_rejected() -> None:
    payload = valid_payload()
    payload["banana"] = "hello"

    with pytest.raises(ValidationError):
        TelemetryMessage.model_validate(payload)