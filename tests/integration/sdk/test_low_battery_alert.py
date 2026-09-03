from datetime import UTC, datetime
from pathlib import Path

import pytest
from httpx import ASGITransport

from vector_pulse.api.app import create_app
from vector_pulse.application.geofencing import (
    ZoneName,
)
from vector_pulse.application.rules import (
    AlertSeverity,
    RuleAlert,
    RuleAlertType,
)
from vector_pulse.persistence.sqlite_storage import (
    SQLiteStorage,
)
from vector_pulse.sdk import (
    AlertType,
    VectorPulseClient,
)


@pytest.mark.asyncio
async def test_sdk_parses_low_battery_alert(
    tmp_path: Path,
) -> None:
    storage = SQLiteStorage(
        tmp_path / "test.db"
    )

    await storage.initialize()

    await storage.save_rule_alert(
        RuleAlert(
            type=RuleAlertType.LOW_BATTERY,
            severity=AlertSeverity.WARNING,
            tag_id="battery-sdk-tag",
            occurred_at=datetime(
                2026,
                9,
                2,
                12,
                0,
                tzinfo=UTC,
            ),
            sequence_number=2,
            zone=ZoneName.RECEIVING,
            message=(
                "Asset battery reached configured "
                "low-battery threshold"
            ),
            details={
                "battery_percent": 20.0,
                "threshold_percent": 20.0,
                "previous_battery_percent": 21.0,
            },
        )
    )

    app = create_app(
        storage
    )

    client = VectorPulseClient(
        base_url="http://test",
        transport=ASGITransport(
            app=app
        ),
    )

    async with client:
        alerts = await client.list_alerts()

    assert len(alerts) == 1

    assert (
        alerts[0].type
        is AlertType.LOW_BATTERY
    )

    assert alerts[0].details[
        "battery_percent"
    ] == 20.0