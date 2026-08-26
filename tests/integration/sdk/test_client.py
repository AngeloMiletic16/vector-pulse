from datetime import UTC, datetime
from pathlib import Path

import pytest
from httpx import ASGITransport

from vector_pulse.api.app import create_app
from vector_pulse.application.asset_registry import (
    AssetState as BackendAssetState,
)
from vector_pulse.application.asset_registry import (
    AssetStatus as BackendAssetStatus,
)
from vector_pulse.application.geofencing import (
    ZoneName as BackendZoneName,
)
from vector_pulse.application.rules import (
    AlertSeverity as BackendAlertSeverity,
)
from vector_pulse.application.rules import (
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
from vector_pulse.sdk import (
    AlertSeverity,
    AlertType,
    AssetStatus,
    VectorPulseAPIError,
    VectorPulseClient,
    ZoneName,
)


def build_backend_state() -> BackendAssetState:
    now = datetime(
        2026,
        8,
        25,
        12,
        0,
        tzinfo=UTC,
    )

    return BackendAssetState(
        telemetry=TelemetryMessage(
            tag_id="tag-001",
            sequence_number=7,
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
                battery_percent=88.0,
            ),
        ),
        last_seen=now,
        status=BackendAssetStatus.ONLINE,
        current_zone=BackendZoneName.RECEIVING,
        zone_entered_at=now,
        dwell_alerted=False,
    )


async def build_sdk_client(
    tmp_path: Path,
) -> tuple[
    SQLiteStorage,
    VectorPulseClient,
]:
    storage = SQLiteStorage(
        tmp_path / "test.db"
    )

    await storage.initialize()

    app = create_app(storage)

    transport = ASGITransport(
        app=app
    )

    client = VectorPulseClient(
        base_url="http://test",
        transport=transport,
    )

    return storage, client


@pytest.mark.asyncio
async def test_sdk_health(
    tmp_path: Path,
) -> None:
    _, client = await build_sdk_client(
        tmp_path
    )

    async with client:
        health = await client.health()

    assert health.status == "ok"


@pytest.mark.asyncio
async def test_sdk_lists_and_gets_assets(
    tmp_path: Path,
) -> None:
    storage, client = (
        await build_sdk_client(
            tmp_path
        )
    )

    await storage.save_accepted_telemetry(
        build_backend_state()
    )

    async with client:
        assets = await client.list_assets()

        asset = await client.get_asset(
            "tag-001"
        )

    assert len(assets) == 1

    assert (
        asset.status
        is AssetStatus.ONLINE
    )

    assert (
        asset.current_zone
        is ZoneName.RECEIVING
    )

    assert (
        asset.telemetry.sequence_number
        == 7
    )


@pytest.mark.asyncio
async def test_sdk_missing_asset_raises_api_error(
    tmp_path: Path,
) -> None:
    _, client = await build_sdk_client(
        tmp_path
    )

    async with client:
        with pytest.raises(
            VectorPulseAPIError
        ) as exc_info:
            await client.get_asset(
                "missing"
            )

    assert (
        exc_info.value.status_code
        == 404
    )

    assert (
        exc_info.value.detail
        == "Asset not found"
    )


@pytest.mark.asyncio
async def test_sdk_reads_telemetry_history(
    tmp_path: Path,
) -> None:
    storage, client = (
        await build_sdk_client(
            tmp_path
        )
    )

    await storage.save_accepted_telemetry(
        build_backend_state()
    )

    async with client:
        history = (
            await client.telemetry_history(
                "tag-001"
            )
        )

    assert len(history) == 1

    assert (
        history[0].resolved_zone
        is ZoneName.RECEIVING
    )

    assert (
        history[0]
        .telemetry.sequence_number
        == 7
    )


@pytest.mark.asyncio
async def test_sdk_reads_alerts(
    tmp_path: Path,
) -> None:
    storage, client = (
        await build_sdk_client(
            tmp_path
        )
    )

    await storage.save_rule_alert(
        RuleAlert(
            type=(
                RuleAlertType
                .IMPOSSIBLE_MOVEMENT
            ),
            severity=(
                BackendAlertSeverity.CRITICAL
            ),
            tag_id="tag-001",
            occurred_at=datetime(
                2026,
                8,
                25,
                12,
                0,
                tzinfo=UTC,
            ),
            sequence_number=7,
            zone=BackendZoneName.RECEIVING,
            message=(
                "Calculated movement speed "
                "exceeded physical limit"
            ),
            details={
                "calculated_speed_mps": 45.0,
                "threshold_mps": 12.0,
            },
        )
    )

    async with client:
        alerts = await client.list_alerts()

    assert len(alerts) == 1

    assert (
        alerts[0].type
        is AlertType.IMPOSSIBLE_MOVEMENT
    )

    assert (
        alerts[0].severity
        is AlertSeverity.CRITICAL
    )


@pytest.mark.asyncio
async def test_sdk_reads_zones(
    tmp_path: Path,
) -> None:
    _, client = await build_sdk_client(
        tmp_path
    )

    async with client:
        configuration = await client.zones()

    assert len(configuration.zones) == 4

    assert (
        configuration.zones[0].name
        is ZoneName.RECEIVING
    )

    assert (
        configuration.minimum_position_quality
        == 0.6
    )


@pytest.mark.asyncio
async def test_sdk_reads_monitoring_rules(
    tmp_path: Path,
) -> None:
    _, client = await build_sdk_client(
        tmp_path
    )

    async with client:
        rules = (
            await client.monitoring_rules()
        )

    assert len(
        rules.dwell_policies
    ) == 4

    assert (
        rules.movement
        .max_reported_speed_mps
        == 6.0
    )

    assert (
        rules.movement
        .max_calculated_speed_mps
        == 12.0
    )