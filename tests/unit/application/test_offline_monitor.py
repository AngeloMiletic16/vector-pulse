from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from vector_pulse.application.asset_registry import (
    AssetRegistry,
    AssetStatus,
)
from vector_pulse.application.event_broadcaster import (
    EventBroadcaster,
)
from vector_pulse.application.events import (
    AssetEventType,
)
from vector_pulse.application.offline_monitor import (
    check_offline_assets,
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


@pytest.mark.asyncio
async def test_offline_transition_is_persisted(
    tmp_path: Path,
) -> None:
    registry = AssetRegistry()

    storage = SQLiteStorage(
        tmp_path / "vectorpulse.db"
    )
    await storage.initialize()

    broadcaster = EventBroadcaster()
    events = broadcaster.subscribe()

    first_seen = datetime(
        2026,
        8,
        20,
        12,
        0,
        tzinfo=UTC,
    )

    telemetry = TelemetryMessage(
        tag_id="tag-001",
        sequence_number=1,
        timestamp=first_seen,
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

    registry.update(
        telemetry,
        received_at=first_seen,
    )

    state = registry.get_state("tag-001")

    assert state is not None

    await storage.save_accepted_telemetry(
        state
    )

    newly_offline = await check_offline_assets(
        registry,
        storage,
        broadcaster,
        now=first_seen + timedelta(seconds=16),
        offline_after_seconds=15,
    )

    assert len(newly_offline) == 1

    event = await events.get()

    assert (
        event.type
        is AssetEventType.ASSET_OFFLINE
    )

    assert event.tag_id == "tag-001"

    persisted_states = (
        await storage.load_asset_states()
    )

    assert len(persisted_states) == 1

    assert (
        persisted_states[0].status
        is AssetStatus.OFFLINE
    )