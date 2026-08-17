from datetime import UTC, datetime
from pathlib import Path

import pytest

from vector_pulse.application.asset_registry import (
    AssetState,
    AssetStatus,
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


def build_state(
    sequence_number: int,
    status: AssetStatus = AssetStatus.ONLINE,
) -> AssetState:
    telemetry = TelemetryMessage(
        tag_id="tag-001",
        sequence_number=sequence_number,
        timestamp=datetime(
            2026,
            8,
            17,
            12,
            0,
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
            temperature_c=25.0,
            vibration_rms=0.1,
            battery_percent=90.0,
        ),
    )

    return AssetState(
        telemetry=telemetry,
        last_seen=datetime(
            2026,
            8,
            17,
            12,
            sequence_number,
            tzinfo=UTC,
        ),
        status=status,
    )


@pytest.mark.asyncio
async def test_latest_asset_state_survives_new_storage_instance(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "vectorpulse.db"

    first_storage = SQLiteStorage(database_path)
    await first_storage.initialize()

    await first_storage.save_accepted_telemetry(
        build_state(sequence_number=1)
    )

    second_storage = SQLiteStorage(database_path)
    await second_storage.initialize()

    states = await second_storage.load_asset_states()

    assert len(states) == 1
    assert states[0].telemetry.tag_id == "tag-001"
    assert states[0].telemetry.sequence_number == 1
    assert states[0].status is AssetStatus.ONLINE


@pytest.mark.asyncio
async def test_telemetry_history_is_persisted(
    tmp_path: Path,
) -> None:
    storage = SQLiteStorage(
        tmp_path / "vectorpulse.db"
    )
    await storage.initialize()

    await storage.save_accepted_telemetry(
        build_state(sequence_number=1)
    )

    await storage.save_accepted_telemetry(
        build_state(sequence_number=2)
    )

    assert await storage.telemetry_count() == 2

    states = await storage.load_asset_states()

    assert len(states) == 1
    assert states[0].telemetry.sequence_number == 2


@pytest.mark.asyncio
async def test_offline_status_is_persisted(
    tmp_path: Path,
) -> None:
    storage = SQLiteStorage(
        tmp_path / "vectorpulse.db"
    )
    await storage.initialize()

    state = build_state(sequence_number=1)

    await storage.save_accepted_telemetry(state)

    state.status = AssetStatus.OFFLINE

    await storage.update_asset_status(state)

    states = await storage.load_asset_states()

    assert len(states) == 1
    assert states[0].status is AssetStatus.OFFLINE