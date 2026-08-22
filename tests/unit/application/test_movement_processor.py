import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest

from vector_pulse.application.asset_registry import (
    AssetRegistry,
)
from vector_pulse.application.event_broadcaster import (
    EventBroadcaster,
)
from vector_pulse.application.events import AssetEventType
from vector_pulse.application.geofencing import (
    ZoneName,
    create_default_geofence,
)
from vector_pulse.application.processor import (
    process_telemetry,
)
from vector_pulse.application.rules import (
    create_default_movement_rules,
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


def telemetry(
    *,
    sequence_number: int,
    second: int,
    x: float,
    speed_mps: float = 1.0,
) -> TelemetryMessage:
    return TelemetryMessage(
        tag_id="tag-rule-demo",
        sequence_number=sequence_number,
        timestamp=datetime(
            2026,
            8,
            22,
            12,
            0,
            second,
            tzinfo=UTC,
        ),
        position=Position(
            x=x,
            y=5.0,
            quality=0.95,
        ),
        motion=Motion(
            speed_mps=speed_mps,
        ),
        condition=Condition(
            temperature_c=25.0,
            vibration_rms=0.1,
            battery_percent=90.0,
        ),
    )


@pytest.mark.asyncio
async def test_processor_emits_impossible_movement_alert(
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
        telemetry(
            sequence_number=1,
            second=0,
            x=5.0,
        )
    )

    await queue.put(
        telemetry(
            sequence_number=2,
            second=1,
            x=50.0,
        )
    )

    task = asyncio.create_task(
        process_telemetry(
            queue,
            registry,
            storage,
            broadcaster,
            create_default_geofence(),
            create_default_movement_rules(),
        )
    )

    await asyncio.wait_for(
        queue.join(),
        timeout=1.0,
    )

    received = []

    while not events.empty():
        received.append(
            events.get_nowait()
        )

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert any(
        event.type
        is AssetEventType.IMPOSSIBLE_MOVEMENT
        for event in received
    )

    assert await storage.alert_count() == 1

    state = registry.get_state(
        "tag-rule-demo"
    )

    assert state is not None
    assert state.current_zone is ZoneName.SHIPPING


@pytest.mark.asyncio
async def test_processor_emits_excessive_speed_alert(
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
        telemetry(
            sequence_number=1,
            second=0,
            x=5.0,
            speed_mps=20.0,
        )
    )

    task = asyncio.create_task(
        process_telemetry(
            queue,
            registry,
            storage,
            broadcaster,
            create_default_geofence(),
            create_default_movement_rules(),
        )
    )

    await asyncio.wait_for(
        queue.join(),
        timeout=1.0,
    )

    received = []

    while not events.empty():
        received.append(
            events.get_nowait()
        )

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert any(
        event.type
        is AssetEventType.EXCESSIVE_SPEED
        for event in received
    )

    assert await storage.alert_count() == 1