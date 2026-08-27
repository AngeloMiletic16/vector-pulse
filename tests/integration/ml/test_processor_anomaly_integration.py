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
from vector_pulse.ml import AnomalyDetection
from vector_pulse.persistence.sqlite_storage import (
    SQLiteStorage,
)


class FakeAnomalyService:
    def evaluate(
        self,
        telemetry: TelemetryMessage,
        *,
        occurred_at: datetime,
    ) -> AnomalyDetection:
        return AnomalyDetection(
            tag_id=telemetry.tag_id,
            sequence_number=(
                telemetry.sequence_number
            ),
            occurred_at=occurred_at,
            anomaly_score=0.42,
            decision_function=-0.42,
            feature_values={
                "temperature_c": (
                    telemetry.condition.temperature_c
                ),
                "vibration_rms": (
                    telemetry.condition.vibration_rms
                ),
                "speed_mps": (
                    telemetry.motion.speed_mps
                ),
                "battery_percent": (
                    telemetry.condition.battery_percent
                ),
                "position_quality": (
                    telemetry.position.quality
                ),
            },
            model_trained_at=datetime.now(UTC),
            model_sample_count=500,
        )


def build_anomalous_telemetry(
) -> TelemetryMessage:
    return TelemetryMessage(
        tag_id="ml-runtime-test",
        sequence_number=1,
        timestamp=datetime.now(UTC),
        position=Position(
            x=5.0,
            y=5.0,
            quality=0.95,
        ),
        motion=Motion(
            speed_mps=1.0,
        ),
        condition=Condition(
            temperature_c=95.0,
            vibration_rms=8.0,
            battery_percent=90.0,
        ),
    )


@pytest.mark.asyncio
async def test_ml_detection_is_persisted_and_broadcast(
    tmp_path: Path,
) -> None:
    storage = SQLiteStorage(
        tmp_path / "test.db"
    )

    await storage.initialize()

    registry = AssetRegistry()
    broadcaster = EventBroadcaster()
    event_queue = broadcaster.subscribe()

    telemetry_queue: asyncio.Queue[
        TelemetryMessage
    ] = asyncio.Queue()

    processor_task = asyncio.create_task(
        process_telemetry(
            telemetry_queue,
            registry,
            storage,
            broadcaster,
            create_default_geofence(),
            anomaly_service=FakeAnomalyService(),  # type: ignore[arg-type]
        )
    )

    try:
        await telemetry_queue.put(
            build_anomalous_telemetry()
        )

        await telemetry_queue.join()

    finally:
        processor_task.cancel()

        await asyncio.gather(
            processor_task,
            return_exceptions=True,
        )

    alerts = await storage.load_alerts(
        tag_id="ml-runtime-test"
    )

    assert len(alerts) == 1

    alert = alerts[0]

    assert (
        alert.type
        is RuleAlertType.ANOMALY_DETECTED
    )

    assert (
        alert.details["anomaly_score"]
        == 0.42
    )

    assert (
        alert.details["temperature_c"]
        == 95.0
    )

    events = []

    while not event_queue.empty():
        event = event_queue.get_nowait()

        events.append(event)

        event_queue.task_done()

    broadcaster.unsubscribe(
        event_queue
    )

    assert (
        AssetEventType.ANOMALY_DETECTED
        in {
            event.type
            for event in events
        }
    )