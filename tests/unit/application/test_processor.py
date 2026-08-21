import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from vector_pulse.application.asset_registry import (
    AssetRegistry,
)
from vector_pulse.application.event_broadcaster import (
    EventBroadcaster,
)
from vector_pulse.application.events import (
    AssetEventType,
)
from vector_pulse.application.processor import (
    process_telemetry,
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


def build_telemetry(
    sequence_number: int,
) -> TelemetryMessage:
    return TelemetryMessage(
        tag_id="tag-001",
        sequence_number=sequence_number,
        timestamp=datetime(
            2026,
            8,
            20,
            20,
            sequence_number,
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
            temperature_c=24.0,
            vibration_rms=0.1,
            battery_percent=90.0,
        ),
    )


@pytest.mark.asyncio
async def test_processor_consumes_message_from_queue(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    queue: asyncio.Queue[TelemetryMessage] = (
        asyncio.Queue()
    )

    registry = AssetRegistry()

    storage = SQLiteStorage(
        tmp_path / "test.db"
    )
    await storage.initialize()

    broadcaster = EventBroadcaster()
    events = broadcaster.subscribe()

    await queue.put(
        build_telemetry(sequence_number=1)
    )

    processor_task = asyncio.create_task(
        process_telemetry(
            queue,
            registry,
            storage,
            broadcaster,
        )
    )

    await asyncio.wait_for(
        queue.join(),
        timeout=1.0,
    )

    event = await asyncio.wait_for(
        events.get(),
        timeout=1.0,
    )

    processor_task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await processor_task

    captured = capsys.readouterr()

    assert "Processed tag=tag-001" in captured.out
    assert queue.empty()

    latest = registry.get_latest("tag-001")

    assert latest is not None
    assert latest.sequence_number == 1

    assert (
        event.type
        is AssetEventType.TELEMETRY_UPDATED
    )

    assert event.tag_id == "tag-001"

    persisted_states = (
        await storage.load_asset_states()
    )

    assert len(persisted_states) == 1
    assert (
        persisted_states[0]
        .telemetry.sequence_number
        == 1
    )

    assert await storage.telemetry_count() == 1


@pytest.mark.asyncio
async def test_processor_emits_online_event_when_asset_returns(
    tmp_path: Path,
) -> None:
    queue: asyncio.Queue[TelemetryMessage] = (
        asyncio.Queue()
    )

    registry = AssetRegistry()

    storage = SQLiteStorage(
        tmp_path / "test.db"
    )
    await storage.initialize()

    broadcaster = EventBroadcaster()
    events = broadcaster.subscribe()

    first_seen = datetime(
        2026,
        8,
        20,
        20,
        0,
        tzinfo=UTC,
    )

    registry.update(
        build_telemetry(sequence_number=1),
        received_at=first_seen,
    )

    registry.mark_offline(
        now=first_seen + timedelta(seconds=20),
        offline_after=timedelta(seconds=15),
    )

    state = registry.get_state("tag-001")

    assert state is not None

    await storage.save_accepted_telemetry(
        state
    )

    await queue.put(
        build_telemetry(sequence_number=2)
    )

    processor_task = asyncio.create_task(
        process_telemetry(
            queue,
            registry,
            storage,
            broadcaster,
        )
    )

    await asyncio.wait_for(
        queue.join(),
        timeout=1.0,
    )

    online_event = await asyncio.wait_for(
        events.get(),
        timeout=1.0,
    )

    telemetry_event = await asyncio.wait_for(
        events.get(),
        timeout=1.0,
    )

    processor_task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await processor_task

    assert (
        online_event.type
        is AssetEventType.ASSET_ONLINE
    )

    assert (
        telemetry_event.type
        is AssetEventType.TELEMETRY_UPDATED
    )