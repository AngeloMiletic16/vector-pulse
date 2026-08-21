from datetime import UTC, datetime
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from vector_pulse.api.app import create_app
from vector_pulse.application.asset_registry import (
    AssetState,
    AssetStatus,
)
from vector_pulse.application.events import (
    AssetEvent,
    AssetEventType,
)
from vector_pulse.application.geofencing import (
    ZoneName,
    create_default_geofence,
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


def build_state() -> AssetState:
    now = datetime(
        2026,
        8,
        21,
        12,
        0,
        tzinfo=UTC,
    )

    telemetry = TelemetryMessage(
        tag_id="tag-001",
        sequence_number=5,
        timestamp=now,
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

    return AssetState(
        telemetry=telemetry,
        last_seen=now,
        status=AssetStatus.ONLINE,
        current_zone=ZoneName.RECEIVING,
        zone_entered_at=now,
    )


@pytest.mark.asyncio
async def test_zones_endpoint_returns_factory_layout(
    tmp_path: Path,
) -> None:
    storage = SQLiteStorage(
        tmp_path / "test.db"
    )
    await storage.initialize()

    geofence = create_default_geofence()

    app = create_app(
        storage,
        geofence=geofence,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/zones"
        )

    assert response.status_code == 200

    payload = response.json()

    assert (
        payload["minimum_position_quality"]
        == 0.6
    )

    assert (
        payload["boundary_policy"]
        == "min_inclusive_max_exclusive"
    )

    assert len(payload["zones"]) == 4

    assert (
        payload["zones"][0]["name"]
        == "receiving"
    )


@pytest.mark.asyncio
async def test_asset_response_contains_current_zone(
    tmp_path: Path,
) -> None:
    storage = SQLiteStorage(
        tmp_path / "test.db"
    )
    await storage.initialize()

    await storage.save_accepted_telemetry(
        build_state()
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

    assert (
        payload["current_zone"]
        == "receiving"
    )

    assert (
        payload["zone_entered_at"]
        is not None
    )


@pytest.mark.asyncio
async def test_zone_transition_history_endpoint(
    tmp_path: Path,
) -> None:
    storage = SQLiteStorage(
        tmp_path / "test.db"
    )
    await storage.initialize()

    state = build_state()

    await storage.save_accepted_telemetry(
        state
    )

    event = AssetEvent.from_state(
        AssetEventType.ZONE_ENTERED,
        state,
        occurred_at=state.last_seen,
        zone=ZoneName.RECEIVING,
        previous_zone=None,
    )

    await storage.save_zone_transition(
        event
    )

    app = create_app(storage)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/assets/tag-001/zone-transitions"
        )

    assert response.status_code == 200

    payload = response.json()

    assert len(payload) == 1
    assert (
        payload[0]["type"]
        == "zone_entered"
    )
    assert (
        payload[0]["zone"]
        == "receiving"
    )