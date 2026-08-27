from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from vector_pulse.application.asset_registry import (
    AssetRegistry,
)
from vector_pulse.ingestion.schemas import (
    Condition,
    Motion,
    Position,
    TelemetryMessage,
)
from vector_pulse.persistence.ml_repository import (
    MLTrainingRepository,
)
from vector_pulse.persistence.sqlite_storage import (
    SQLiteStorage,
)


def build_telemetry(
    sequence_number: int,
) -> TelemetryMessage:
    return TelemetryMessage(
        tag_id="training-tag",
        sequence_number=sequence_number,
        timestamp=(
            datetime.now(UTC)
            + timedelta(
                seconds=sequence_number
            )
        ),
        position=Position(
            x=5.0,
            y=5.0,
            quality=0.95,
        ),
        motion=Motion(
            speed_mps=1.0,
        ),
        condition=Condition(
            temperature_c=(
                24.0
                + sequence_number * 0.1
            ),
            vibration_rms=0.1,
            battery_percent=90.0,
        ),
    )


@pytest.mark.asyncio
async def test_repository_loads_recent_persisted_telemetry(
    tmp_path: Path,
) -> None:
    database_path = (
        tmp_path
        / "vectorpulse.db"
    )

    storage = SQLiteStorage(
        database_path
    )

    await storage.initialize()

    registry = AssetRegistry()

    for sequence_number in range(
        1,
        4,
    ):
        telemetry = build_telemetry(
            sequence_number
        )

        registry.update(
            telemetry
        )

        state = registry.get_state(
            telemetry.tag_id
        )

        assert state is not None

        await storage.save_accepted_telemetry(
            state
        )

    repository = MLTrainingRepository(
        database_path
    )

    telemetry_messages = (
        await repository
        .load_recent_telemetry(
            limit=2
        )
    )

    assert [
        telemetry.sequence_number
        for telemetry in telemetry_messages
    ] == [
        2,
        3,
    ]