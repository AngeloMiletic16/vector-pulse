from datetime import UTC, datetime
from pathlib import Path

import pytest

from vector_pulse.application.geofencing import ZoneName
from vector_pulse.application.rules import (
    AlertSeverity,
    RuleAlert,
    RuleAlertType,
)
from vector_pulse.persistence.sqlite_storage import (
    SQLiteStorage,
)


@pytest.mark.asyncio
async def test_rule_alert_is_persisted(
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
        sequence_number=10,
        zone=ZoneName.RECEIVING,
        message="Speed too high",
        details={
            "reported_speed_mps": 10.0,
            "threshold_mps": 6.0,
        },
    )

    await storage.save_rule_alert(
        alert
    )

    alerts = await storage.load_alerts()

    assert len(alerts) == 1
    assert alerts[0] == alert


@pytest.mark.asyncio
async def test_alerts_can_be_filtered_by_asset(
    tmp_path: Path,
) -> None:
    storage = SQLiteStorage(
        tmp_path / "test.db"
    )
    await storage.initialize()

    now = datetime(
        2026,
        8,
        22,
        12,
        0,
        tzinfo=UTC,
    )

    for tag_id in (
        "tag-001",
        "tag-002",
    ):
        await storage.save_rule_alert(
            RuleAlert(
                type=(
                    RuleAlertType.EXCESSIVE_SPEED
                ),
                severity=AlertSeverity.WARNING,
                tag_id=tag_id,
                occurred_at=now,
                sequence_number=1,
                zone=None,
                message="Speed too high",
                details={
                    "reported_speed_mps": 10.0
                },
            )
        )

    alerts = await storage.load_alerts(
        tag_id="tag-002"
    )

    assert len(alerts) == 1
    assert alerts[0].tag_id == "tag-002"