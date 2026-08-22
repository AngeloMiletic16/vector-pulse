from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from vector_pulse.application.asset_registry import (
    AssetRegistry,
)
from vector_pulse.application.dwell_monitor import (
    check_dwell_alerts,
)
from vector_pulse.application.event_broadcaster import (
    EventBroadcaster,
)
from vector_pulse.application.events import AssetEventType
from vector_pulse.application.geofencing import ZoneName
from vector_pulse.application.rules import (
    DwellPolicy,
    DwellRuleEngine,
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
async def test_dwell_alert_is_persisted_and_broadcast_once(
    tmp_path: Path,
) -> None:
    entered_at = datetime(
        2026,
        8,
        22,
        12,
        0,
        tzinfo=UTC,
    )

    registry = AssetRegistry()

    telemetry = TelemetryMessage(
        tag_id="tag-001",
        sequence_number=1,
        timestamp=entered_at,
        position=Position(
            x=5.0,
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

    registry.update(
        telemetry,
        received_at=entered_at,
    )

    registry.apply_zone(
        "tag-001",
        ZoneName.RECEIVING,
        entered_at,
    )

    storage = SQLiteStorage(
        tmp_path / "test.db"
    )
    await storage.initialize()

    state = registry.get_state("tag-001")

    assert state is not None

    await storage.save_accepted_telemetry(
        state
    )

    broadcaster = EventBroadcaster()
    events = broadcaster.subscribe()

    rules = DwellRuleEngine(
        (
            DwellPolicy(
                zone=ZoneName.RECEIVING,
                threshold_seconds=30.0,
            ),
        )
    )

    first_alerts = await check_dwell_alerts(
        registry,
        storage,
        broadcaster,
        rules,
        now=entered_at + timedelta(seconds=31),
    )

    second_alerts = await check_dwell_alerts(
        registry,
        storage,
        broadcaster,
        rules,
        now=entered_at + timedelta(seconds=40),
    )

    assert len(first_alerts) == 1
    assert second_alerts == []

    event = events.get_nowait()

    assert (
        event.type
        is AssetEventType.DWELL_TIME_EXCEEDED
    )

    assert await storage.alert_count() == 1

    persisted = await storage.get_asset_state(
        "tag-001"
    )

    assert persisted is not None
    assert persisted.dwell_alerted is True


def test_zone_change_resets_dwell_alert_flag() -> None:
    entered_at = datetime(
        2026,
        8,
        22,
        12,
        0,
        tzinfo=UTC,
    )

    registry = AssetRegistry()

    telemetry = TelemetryMessage(
        tag_id="tag-001",
        sequence_number=1,
        timestamp=entered_at,
        position=Position(
            x=5.0,
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

    registry.update(
        telemetry,
        received_at=entered_at,
    )

    registry.apply_zone(
        "tag-001",
        ZoneName.RECEIVING,
        entered_at,
    )

    registry.mark_dwell_alerted(
        "tag-001"
    )

    registry.apply_zone(
        "tag-001",
        ZoneName.STORAGE,
        entered_at + timedelta(seconds=60),
    )

    state = registry.get_state("tag-001")

    assert state is not None
    assert state.dwell_alerted is False
    assert state.current_zone is ZoneName.STORAGE