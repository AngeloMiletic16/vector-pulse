from datetime import UTC, datetime
from pathlib import Path

import pytest

from vector_pulse.application.asset_registry import (
    AssetState,
    AssetStatus,
)
from vector_pulse.application.events import (
    AssetEvent,
    AssetEventType,
)
from vector_pulse.application.geofencing import (
    ZoneName,
)
from vector_pulse.ingestion.schemas import (
    Condition,
    Motion,
    Position,
    TelemetryMessage,
)
from vector_pulse.persistence.sqlite_storage import (
    SQLiteStorage,
)


def build_state() -> AssetState:
    now = datetime(
        2026,
        8,
        21,
        12,
        0,
        tzinfo=UTC,
    )

    telemetry = TelemetryMessage(
        tag_id="tag-001",
        sequence_number=10,
        timestamp=now,
        position=Position(
            x=15.0,
            y=5.0,
            quality=0.95,
        ),
        motion=Motion(
            speed_mps=1.0,
        ),
        condition=Condition(
            temperature_c=25.0,
            vibration_rms=0.1,
            battery_percent=90.0,
        ),
    )

    return AssetState(
        telemetry=telemetry,
        last_seen=now,
        status=AssetStatus.ONLINE,
        current_zone=ZoneName.STORAGE,
        zone_entered_at=now,
    )


@pytest.mark.asyncio
async def test_current_zone_is_persisted(
    tmp_path: Path,
) -> None:
    storage = SQLiteStorage(
        tmp_path / "test.db"
    )
    await storage.initialize()

    await storage.save_accepted_telemetry(
        build_state()
    )

    state = await storage.get_asset_state(
        "tag-001"
    )

    assert state is not None
    assert (
        state.current_zone
        is ZoneName.STORAGE
    )
    assert state.zone_entered_at is not None


@pytest.mark.asyncio
async def test_telemetry_history_contains_resolved_zone(
    tmp_path: Path,
) -> None:
    storage = SQLiteStorage(
        tmp_path / "test.db"
    )
    await storage.initialize()

    await storage.save_accepted_telemetry(
        build_state()
    )

    history = (
        await storage.load_telemetry_history(
            "tag-001"
        )
    )

    assert len(history) == 1
    assert (
        history[0].resolved_zone
        is ZoneName.STORAGE
    )


@pytest.mark.asyncio
async def test_zone_transition_history_is_persisted(
    tmp_path: Path,
) -> None:
    storage = SQLiteStorage(
        tmp_path / "test.db"
    )
    await storage.initialize()

    state = build_state()

    await storage.save_accepted_telemetry(
        state
    )

    event = AssetEvent.from_state(
        AssetEventType.ZONE_ENTERED,
        state,
        occurred_at=state.last_seen,
        zone=ZoneName.STORAGE,
        previous_zone=ZoneName.RECEIVING,
    )

    await storage.save_zone_transition(
        event
    )

    transitions = (
        await storage.load_zone_transitions(
            "tag-001"
        )
    )

    assert len(transitions) == 1
    assert (
        transitions[0].event_type
        is AssetEventType.ZONE_ENTERED
    )
    assert (
        transitions[0].zone
        is ZoneName.STORAGE
    )
    assert (
        transitions[0].previous_zone
        is ZoneName.RECEIVING
    )