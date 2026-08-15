import asyncio

import pytest

from vector_pulse.application.asset_registry import AssetRegistry
from vector_pulse.application.processor import process_telemetry
from vector_pulse.ingestion.schemas import (
    Condition,
    Motion,
    Position,
    TelemetryMessage,
)


@pytest.mark.asyncio
async def test_processor_consumes_message_from_queue(
    capsys: pytest.CaptureFixture[str],
) -> None:
    queue: asyncio.Queue[TelemetryMessage] = asyncio.Queue()
    registry = AssetRegistry()

    telemetry = TelemetryMessage(
        tag_id="tag-001",
        sequence_number=1,
        timestamp="2026-08-14T12:00:00Z",
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

    await queue.put(telemetry)

    processor_task = asyncio.create_task(
        process_telemetry(
            queue,
            registry,
        )
    )

    await asyncio.wait_for(
        queue.join(),
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