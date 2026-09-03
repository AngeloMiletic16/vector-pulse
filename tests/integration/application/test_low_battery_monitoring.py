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
from vector_pulse.application.events import (
    AssetEventType,
)
from vector_pulse.application.geofencing import (
    create_default_geofence,
)
from vector_pulse.application.processor import (
    process_telemetry,
)
from vector_pulse.application.rules import (
    RuleAlertType,
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
    *,
    sequence_number: int,
    battery_percent: float,
) -> TelemetryMessage:
    return TelemetryMessage(
        tag_id="battery-integration-tag",
        sequence_number=sequence_number,
        timestamp=datetime(
            2026,
            9,
            2,
            12,
            0,
            sequence_number,
            tzinfo=UTC,
        ),
        position=Position(
            x=5.0,
            y=5.0,
            quality=0.95,
        ),
        motion=Motion(
            speed_mps=0.5,
        ),
        condition=Condition(
            temperature_c=25.0,
            vibration_rms=0.1,
            battery_percent=battery_percent,
        ),
    )


@pytest.mark.asyncio
async def test_processor_persists_and_broadcasts_low_battery_alert(
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

    geofence = create_default_geofence()

    await queue.put(
        build_telemetry(
            sequence_number=1,
            battery_percent=21.0,
        )
    )

    await queue.put(
        build_telemetry(
            sequence_number=2,
            battery_percent=20.0,
        )
    )

    processor_task = asyncio.create_task(
        process_telemetry(
            queue,
            registry,
            storage,
            broadcaster,
            geofence,
        )
    )

    await asyncio.wait_for(
        queue.join(),
        timeout=1.0,
    )

    received_events = [
        await asyncio.wait_for(
            events.get(),
            timeout=1.0,
        )
        for _ in range(4)
    ]

    processor_task.cancel()

    with pytest.raises(
        asyncio.CancelledError
    ):
        await processor_task

    assert [
        event.type
        for event in received_events
    ] == [
        AssetEventType.ZONE_ENTERED,
        AssetEventType.TELEMETRY_UPDATED,
        AssetEventType.LOW_BATTERY,
        AssetEventType.TELEMETRY_UPDATED,
    ]

    alerts = await storage.load_alerts(
        tag_id="battery-integration-tag"
    )

    assert len(alerts) == 1

    assert (
        alerts[0].type
        is RuleAlertType.LOW_BATTERY
    )

    assert alerts[0].details[
        "battery_percent"
    ] == 20.0

    assert alerts[0].details[
        "threshold_percent"
    ] == 20.0

    broadcaster.unsubscribe(
        events
    )