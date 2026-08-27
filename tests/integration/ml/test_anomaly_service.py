from datetime import (
    UTC,
    datetime,
    timedelta,
)
from pathlib import Path

import pytest

from vector_pulse.ingestion.schemas import (
    Condition,
    Motion,
    Position,
    TelemetryMessage,
)
from vector_pulse.ml import (
    AnomalyService,
    InsufficientTrainingDataError,
)


def baseline_messages(
    count: int,
) -> list[TelemetryMessage]:
    return [
        TelemetryMessage(
            tag_id=(
                f"tag-{index % 5:03d}"
            ),
            sequence_number=index + 1,
            timestamp=datetime.now(UTC),
            position=Position(
                x=5.0,
                y=5.0,
                quality=(
                    0.94
                    + (index % 4) * 0.01
                ),
            ),
            motion=Motion(
                speed_mps=(
                    0.8
                    + (index % 6) * 0.04
                ),
            ),
            condition=Condition(
                temperature_c=(
                    24.0
                    + (index % 5) * 0.1
                ),
                vibration_rms=(
                    0.10
                    + (index % 7) * 0.003
                ),
                battery_percent=(
                    88.0
                    + (index % 8) * 0.2
                ),
            ),
        )
        for index in range(count)
    ]


def extreme_message(
    sequence_number: int,
) -> TelemetryMessage:
    return TelemetryMessage(
        tag_id="tag-anomaly",
        sequence_number=sequence_number,
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
            battery_percent=89.0,
        ),
    )


class FakeTrainingRepository:
    def __init__(
        self,
        messages: list[TelemetryMessage],
    ) -> None:
        self._messages = messages

    async def load_recent_telemetry(
        self,
        *,
        limit: int,
    ) -> list[TelemetryMessage]:
        return self._messages[
            -limit:
        ]


@pytest.mark.asyncio
async def test_service_starts_not_ready_without_model(
    tmp_path: Path,
) -> None:
    service = AnomalyService(
        FakeTrainingRepository(
            baseline_messages(150)
        ),
        tmp_path
        / "model.joblib",
    )

    await service.initialize()

    status = service.status()

    assert status.ready is False
    assert status.training is False


@pytest.mark.asyncio
async def test_training_requires_enough_samples(
    tmp_path: Path,
) -> None:
    service = AnomalyService(
        FakeTrainingRepository(
            baseline_messages(20)
        ),
        tmp_path
        / "model.joblib",
        minimum_training_samples=100,
    )

    with pytest.raises(
        InsufficientTrainingDataError
    ):
        await service.train(
            limit=100,
            nu=0.03,
        )


@pytest.mark.asyncio
async def test_training_persists_model_and_marks_service_ready(
    tmp_path: Path,
) -> None:
    model_path = (
        tmp_path
        / "model.joblib"
    )

    service = AnomalyService(
        FakeTrainingRepository(
            baseline_messages(150)
        ),
        model_path,
    )

    status = await service.train(
        limit=150,
        nu=0.03,
    )

    assert status.ready is True
    assert status.sample_count == 150
    assert status.nu == 0.03
    assert model_path.exists()


@pytest.mark.asyncio
async def test_persisted_model_is_loaded_after_restart(
    tmp_path: Path,
) -> None:
    model_path = (
        tmp_path
        / "model.joblib"
    )

    repository = FakeTrainingRepository(
        baseline_messages(150)
    )

    first_service = AnomalyService(
        repository,
        model_path,
    )

    await first_service.train(
        limit=150,
        nu=0.03,
    )

    restarted_service = (
        AnomalyService(
            repository,
            model_path,
        )
    )

    await restarted_service.initialize()

    restarted_status = (
        restarted_service.status()
    )

    assert restarted_status.ready is True

    assert (
        restarted_status.sample_count
        == 150
    )

    assert restarted_status.nu == 0.03


@pytest.mark.asyncio
async def test_three_consecutive_anomalies_trigger_detection(
    tmp_path: Path,
) -> None:
    service = AnomalyService(
        FakeTrainingRepository(
            baseline_messages(200)
        ),
        tmp_path
        / "model.joblib",
        required_consecutive_anomalies=3,
    )

    await service.train(
        limit=200,
        nu=0.02,
    )

    now = datetime.now(UTC)

    first = service.evaluate(
        extreme_message(1),
        occurred_at=now,
    )

    second = service.evaluate(
        extreme_message(2),
        occurred_at=(
            now
            + timedelta(seconds=1)
        ),
    )

    third = service.evaluate(
        extreme_message(3),
        occurred_at=(
            now
            + timedelta(seconds=2)
        ),
    )

    assert first is None
    assert second is None

    assert third is not None

    assert (
        third.tag_id
        == "tag-anomaly"
    )

    assert third.sequence_number == 3

    assert (
        third.anomaly_score
        > 0
    )

    assert (
        third.decision_function
        < 0
    )

    assert (
        third.feature_values[
            "temperature_c"
        ]
        == 95.0
    )

    assert (
        third.feature_values[
            "vibration_rms"
        ]
        == 8.0
    )


@pytest.mark.asyncio
async def test_cooldown_suppresses_repeated_alerts(
    tmp_path: Path,
) -> None:
    service = AnomalyService(
        FakeTrainingRepository(
            baseline_messages(200)
        ),
        tmp_path
        / "model.joblib",
        required_consecutive_anomalies=1,
        alert_cooldown_seconds=30.0,
    )

    await service.train(
        limit=200,
        nu=0.02,
    )

    now = datetime.now(UTC)

    first = service.evaluate(
        extreme_message(1),
        occurred_at=now,
    )

    second = service.evaluate(
        extreme_message(2),
        occurred_at=(
            now
            + timedelta(seconds=5)
        ),
    )

    third = service.evaluate(
        extreme_message(3),
        occurred_at=(
            now
            + timedelta(seconds=31)
        ),
    )

    assert first is not None
    assert second is None
    assert third is not None