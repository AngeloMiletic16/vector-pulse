from datetime import UTC, datetime

import pytest

from vector_pulse.application.asset_registry import (
    AssetStatus,
)
from vector_pulse.application.event_broadcaster import (
    EventBroadcaster,
)
from vector_pulse.application.events import (
    AssetEvent,
    AssetEventType,
)
from vector_pulse.ingestion.schemas import (
    Condition,
    Motion,
    Position,
    TelemetryMessage,
)


def build_event(
    sequence_number: int = 1,
) -> AssetEvent:
    now = datetime(
        2026,
        8,
        20,
        20,
        0,
        tzinfo=UTC,
    )

    telemetry = TelemetryMessage(
        tag_id="tag-001",
        sequence_number=sequence_number,
        timestamp=now,
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

    return AssetEvent(
        type=AssetEventType.TELEMETRY_UPDATED,
        tag_id="tag-001",
        status=AssetStatus.ONLINE,
        occurred_at=now,
        last_seen=now,
        telemetry=telemetry,
    )


@pytest.mark.asyncio
async def test_subscriber_receives_event() -> None:
    broadcaster = EventBroadcaster()
    subscriber = broadcaster.subscribe()

    event = build_event()

    await broadcaster.publish(event)

    received = await subscriber.get()

    assert received == event


@pytest.mark.asyncio
async def test_multiple_subscribers_receive_event() -> None:
    broadcaster = EventBroadcaster()

    first = broadcaster.subscribe()
    second = broadcaster.subscribe()

    event = build_event()

    await broadcaster.publish(event)

    assert await first.get() == event
    assert await second.get() == event


@pytest.mark.asyncio
async def test_unsubscribed_client_receives_no_events() -> None:
    broadcaster = EventBroadcaster()

    subscriber = broadcaster.subscribe()

    broadcaster.unsubscribe(subscriber)

    await broadcaster.publish(
        build_event()
    )

    assert subscriber.empty()
    assert broadcaster.subscriber_count == 0


@pytest.mark.asyncio
async def test_slow_subscriber_drops_oldest_event() -> None:
    broadcaster = EventBroadcaster(
        queue_max_size=1
    )

    subscriber = broadcaster.subscribe()

    await broadcaster.publish(
        build_event(sequence_number=1)
    )

    await broadcaster.publish(
        build_event(sequence_number=2)
    )

    received = await subscriber.get()

    assert (
        received.telemetry.sequence_number
        == 2
    )