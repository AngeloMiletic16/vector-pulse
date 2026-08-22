from datetime import UTC, datetime
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from vector_pulse.api.app import create_app
from vector_pulse.application.asset_registry import (
    AssetState,
    AssetStatus,
)
from vector_pulse.application.geofencing import ZoneName
from vector_pulse.application.rules import (
    AlertSeverity,
    RuleAlert,
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


def build_state() -> AssetState:
    now = datetime(
        2026,
        8,
        22,
        12,
        0,
        tzinfo=UTC,
    )

    return AssetState(
        telemetry=TelemetryMessage(
            tag_id="tag-001",
            sequence_number=1,
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
        ),
        last_seen=now,
        status=AssetStatus.ONLINE,
        current_zone=ZoneName.RECEIVING,
        zone_entered_at=now,
    )


@pytest.mark.asyncio
async def test_monitoring_rules_endpoint(
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
            "/monitoring-rules"
        )

    assert response.status_code == 200

    payload = response.json()

    assert len(
        payload["dwell_policies"]
    ) == 4

    assert (
        payload["movement"]
        ["max_reported_speed_mps"]
        == 6.0
    )


@pytest.mark.asyncio
async def test_global_alert_endpoint(
    tmp_path: Path,
) -> None:
    storage = SQLiteStorage(
        tmp_path / "test.db"
    )
    await storage.initialize()

    alert = RuleAlert(
        type=RuleAlertType.EXCESSIVE_SPEED,
        severity=AlertSeverity.WARNING,
        tag_id="tag-001",
        occurred_at=datetime(
            2026,
            8,
            22,
            12,
            0,
            tzinfo=UTC,
        ),
        sequence_number=1,
        zone=ZoneName.RECEIVING,
        message="Speed too high",
        details={
            "reported_speed_mps": 10.0
        },
    )

    await storage.save_rule_alert(
        alert
    )

    app = create_app(storage)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/alerts"
        )

    assert response.status_code == 200

    payload = response.json()

    assert len(payload) == 1
    assert (
        payload[0]["type"]
        == "excessive_speed"
    )


@pytest.mark.asyncio
async def test_asset_alert_endpoint(
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

    await storage.save_rule_alert(
        RuleAlert(
            type=(
                RuleAlertType.DWELL_TIME_EXCEEDED
            ),
            severity=AlertSeverity.WARNING,
            tag_id="tag-001",
            occurred_at=state.last_seen,
            sequence_number=1,
            zone=ZoneName.RECEIVING,
            message="Dwell exceeded",
            details={
                "dwell_seconds": 31.0,
                "threshold_seconds": 30.0,
            },
        )
    )

    app = create_app(storage)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/assets/tag-001/alerts"
        )

    assert response.status_code == 200

    payload = response.json()

    assert len(payload) == 1
    assert (
        payload[0]["type"]
        == "dwell_time_exceeded"
    )