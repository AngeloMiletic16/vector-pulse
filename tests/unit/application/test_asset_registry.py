from datetime import UTC, datetime, timedelta

from vector_pulse.application.asset_registry import (
    AssetRegistry,
    AssetStatus,
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
        timestamp=datetime(
            2026,
            8,
            17,
            12,
            0,
            tzinfo=UTC,
        ),
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

    result = registry.update(
        telemetry(sequence_number=1)
    )

    assert result.status is UpdateStatus.ACCEPTED
    assert registry.asset_count() == 1


def test_latest_telemetry_is_stored() -> None:
    registry = AssetRegistry()

    registry.update(
        telemetry(sequence_number=1)
    )
    registry.update(
        telemetry(sequence_number=2)
    )

    latest = registry.get_latest("tag-001")

    assert latest is not None
    assert latest.sequence_number == 2


def test_duplicate_message_is_rejected() -> None:
    registry = AssetRegistry()

    registry.update(
        telemetry(sequence_number=10)
    )

    result = registry.update(
        telemetry(sequence_number=10)
    )

    assert result.status is UpdateStatus.DUPLICATE


def test_out_of_order_message_is_rejected() -> None:
    registry = AssetRegistry()

    registry.update(
        telemetry(sequence_number=10)
    )

    result = registry.update(
        telemetry(sequence_number=8)
    )

    assert result.status is UpdateStatus.OUT_OF_ORDER

    latest = registry.get_latest("tag-001")

    assert latest is not None
    assert latest.sequence_number == 10


def test_sequence_gap_is_detected() -> None:
    registry = AssetRegistry()

    registry.update(
        telemetry(sequence_number=10)
    )

    result = registry.update(
        telemetry(sequence_number=14)
    )

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

    first = registry.get_latest("tag-001")
    second = registry.get_latest("tag-002")

    assert first is not None
    assert second is not None

    assert first.sequence_number == 5
    assert second.sequence_number == 12
    assert registry.asset_count() == 2


def test_asset_becomes_offline_after_timeout() -> None:
    registry = AssetRegistry()

    first_seen = datetime(
        2026,
        8,
        17,
        12,
        0,
        tzinfo=UTC,
    )

    registry.update(
        telemetry(sequence_number=1),
        received_at=first_seen,
    )

    newly_offline = registry.mark_offline(
        now=first_seen + timedelta(seconds=16),
        offline_after=timedelta(seconds=15),
    )

    state = registry.get_state("tag-001")

    assert state is not None
    assert state.status is AssetStatus.OFFLINE
    assert len(newly_offline) == 1


def test_offline_asset_returns_online() -> None:
    registry = AssetRegistry()

    first_seen = datetime(
        2026,
        8,
        17,
        12,
        0,
        tzinfo=UTC,
    )

    registry.update(
        telemetry(sequence_number=1),
        received_at=first_seen,
    )

    registry.mark_offline(
        now=first_seen + timedelta(seconds=16),
        offline_after=timedelta(seconds=15),
    )

    result = registry.update(
        telemetry(sequence_number=2),
        received_at=first_seen + timedelta(seconds=20),
    )

    state = registry.get_state("tag-001")

    assert state is not None
    assert state.status is AssetStatus.ONLINE
    assert result.came_online is True


def test_offline_asset_can_restart_sequence() -> None:
    registry = AssetRegistry()

    first_seen = datetime(
        2026,
        8,
        17,
        12,
        0,
        tzinfo=UTC,
    )

    registry.update(
        telemetry(sequence_number=50),
        received_at=first_seen,
    )

    registry.mark_offline(
        now=first_seen + timedelta(seconds=16),
        offline_after=timedelta(seconds=15),
    )

    result = registry.update(
        telemetry(sequence_number=1),
        received_at=first_seen + timedelta(seconds=20),
    )

    state = registry.get_state("tag-001")

    assert state is not None
    assert state.status is AssetStatus.ONLINE
    assert state.telemetry.sequence_number == 1
    assert result.status is UpdateStatus.ACCEPTED
    assert result.came_online is True