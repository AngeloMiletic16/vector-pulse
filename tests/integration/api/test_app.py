from datetime import UTC, datetime
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from vector_pulse.api.app import create_app
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
    tag_id: str = "tag-001",
    sequence_number: int = 1,
) -> AssetState:
    telemetry = TelemetryMessage(
        tag_id=tag_id,
        sequence_number=sequence_number,
        timestamp=datetime(
            2026,
            8,
            19,
            20,
            0,
            tzinfo=UTC,
        ),
        position=Position(
            x=10.0,
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

    return AssetState(
        telemetry=telemetry,
        last_seen=datetime(
            2026,
            8,
            19,
            20,
            0,
            tzinfo=UTC,
        ),
        status=AssetStatus.ONLINE,
    )


@pytest.mark.asyncio
async def test_health_endpoint(
    tmp_path: Path,
) -> None:
    storage = SQLiteStorage(
        tmp_path / "test.db"
    )
    await storage.initialize()

    app = create_app(storage)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
    }


@pytest.mark.asyncio
async def test_list_assets(
    tmp_path: Path,
) -> None:
    storage = SQLiteStorage(
        tmp_path / "test.db"
    )
    await storage.initialize()

    await storage.save_accepted_telemetry(
        build_state(
            tag_id="tag-001",
            sequence_number=1,
        )
    )

    await storage.save_accepted_telemetry(
        build_state(
            tag_id="tag-002",
            sequence_number=5,
        )
    )

    app = create_app(storage)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/assets")

    assert response.status_code == 200

    payload = response.json()

    assert len(payload) == 2
    assert (
        payload[0]["telemetry"]["tag_id"]
        == "tag-001"
    )
    assert (
        payload[1]["telemetry"]["tag_id"]
        == "tag-002"
    )


@pytest.mark.asyncio
async def test_get_asset(
    tmp_path: Path,
) -> None:
    storage = SQLiteStorage(
        tmp_path / "test.db"
    )
    await storage.initialize()

    await storage.save_accepted_telemetry(
        build_state(
            tag_id="tag-001",
            sequence_number=7,
        )
    )

    app = create_app(storage)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/assets/tag-001"
        )

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "online"
    assert (
        payload["telemetry"]["tag_id"]
        == "tag-001"
    )
    assert (
        payload["telemetry"]["sequence_number"]
        == 7
    )


@pytest.mark.asyncio
async def test_missing_asset_returns_404(
    tmp_path: Path,
) -> None:
    storage = SQLiteStorage(
        tmp_path / "test.db"
    )
    await storage.initialize()

    app = create_app(storage)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/assets/does-not-exist"
        )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Asset not found",
    }


@pytest.mark.asyncio
async def test_get_telemetry_history(
    tmp_path: Path,
) -> None:
    storage = SQLiteStorage(
        tmp_path / "test.db"
    )
    await storage.initialize()

    await storage.save_accepted_telemetry(
        build_state(
            sequence_number=1,
        )
    )

    await storage.save_accepted_telemetry(
        build_state(
            sequence_number=2,
        )
    )

    app = create_app(storage)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/assets/tag-001/telemetry?limit=1"
        )

    assert response.status_code == 200

    payload = response.json()

    assert len(payload) == 1
    assert (
        payload[0]["telemetry"]["sequence_number"]
        == 2
    )