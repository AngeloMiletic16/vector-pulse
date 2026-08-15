from datetime import UTC, datetime

from vector_pulse.application.asset_registry import (
    AssetRegistry,
    UpdateStatus,
)
from vector_pulse.ingestion.schemas import (
    Condition,
    Motion,
    Position,
    TelemetryMessage,
)


def telemetry(
    tag_id: str = "tag-001",
    sequence_number: int = 1,
) -> TelemetryMessage:
    return TelemetryMessage(
        tag_id=tag_id,
        sequence_number=sequence_number,
        timestamp=datetime.now(UTC),
        position=Position(
            x=1.0,
            y=2.0,
            quality=0.9,
        ),
        motion=Motion(
            speed_mps=0.5,
        ),
        condition=Condition(
            temperature_c=25.0,
            vibration_rms=0.1,
            battery_percent=90.0,
        ),
    )

def test_first_message_is_accepted() -> None:
    registry = AssetRegistry()

    result = registry.update(telemetry(sequence_number=1))

    assert result.status is UpdateStatus.ACCEPTED
    assert registry.asset_count() == 1


def test_latest_telemetry_is_stored() -> None:
    registry = AssetRegistry()

    registry.update(telemetry(sequence_number=1))
    registry.update(telemetry(sequence_number=2))

    latest = registry.get_latest("tag-001")

    assert latest is not None
    assert latest.sequence_number == 2


def test_duplicate_message_is_rejected() -> None:
    registry = AssetRegistry()

    registry.update(telemetry(sequence_number=10))
    result = registry.update(telemetry(sequence_number=10))

    assert result.status is UpdateStatus.DUPLICATE


def test_out_of_order_message_is_rejected() -> None:
    registry = AssetRegistry()

    registry.update(telemetry(sequence_number=10))
    result = registry.update(telemetry(sequence_number=8))

    assert result.status is UpdateStatus.OUT_OF_ORDER

    latest = registry.get_latest("tag-001")

    assert latest is not None
    assert latest.sequence_number == 10


def test_sequence_gap_is_detected() -> None:
    registry = AssetRegistry()

    registry.update(telemetry(sequence_number=10))
    result = registry.update(telemetry(sequence_number=14))

    assert result.status is UpdateStatus.GAP_DETECTED
    assert result.missing_messages == 3

    latest = registry.get_latest("tag-001")

    assert latest is not None
    assert latest.sequence_number == 14


def test_assets_are_tracked_independently() -> None:
    registry = AssetRegistry()

    registry.update(
        telemetry(
            tag_id="tag-001",
            sequence_number=5,
        )
    )

    registry.update(
        telemetry(
            tag_id="tag-002",
            sequence_number=12,
        )
    )

    assert registry.asset_count() == 2
    assert registry.get_latest("tag-001").sequence_number == 5
    assert registry.get_latest("tag-002").sequence_number == 12