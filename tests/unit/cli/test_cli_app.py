from datetime import UTC, datetime
from typing import Self

import pytest
from typer.testing import CliRunner

import vector_pulse.cli.app as cli_module
from vector_pulse.cli.app import app
from vector_pulse.sdk import (
    Alert,
    AlertSeverity,
    AlertType,
    AssetState,
    AssetStatus,
    HealthStatus,
    ZoneName,
)
from vector_pulse.sdk.exceptions import (
    VectorPulseConnectionError,
)
from vector_pulse.sdk.models import (
    Condition,
    Motion,
    Position,
    TelemetryMessage,
)

runner = CliRunner()


def build_asset() -> AssetState:
    now = datetime(
        2026,
        8,
        25,
        12,
        0,
        tzinfo=UTC,
    )

    return AssetState(
        status=AssetStatus.ONLINE,
        last_seen=now,
        current_zone=ZoneName.RECEIVING,
        zone_entered_at=now,
        dwell_alerted=False,
        telemetry=TelemetryMessage(
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
        ),
    )


def build_alert() -> Alert:
    return Alert(
        type=AlertType.IMPOSSIBLE_MOVEMENT,
        severity=AlertSeverity.CRITICAL,
        tag_id="tag-001",
        occurred_at=datetime(
            2026,
            8,
            25,
            12,
            0,
            tzinfo=UTC,
        ),
        sequence_number=5,
        zone=ZoneName.RECEIVING,
        message="Impossible movement detected",
        details={
            "calculated_speed_mps": 45.0,
            "threshold_mps": 12.0,
        },
    )


class FakeClient:
    def __init__(
        self,
        base_url: str,
        **_: object,
    ) -> None:
        self.base_url = base_url

    async def __aenter__(
        self,
    ) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: object,
        exc_value: object,
        traceback: object,
    ) -> None:
        return None

    @staticmethod
    async def health() -> HealthStatus:
        return HealthStatus(
            status="ok"
        )

    @staticmethod
    async def list_assets() -> list[AssetState]:
        return [
            build_asset()
        ]

    @staticmethod
    async def list_alerts(
        *,
        limit: int = 50,
    ) -> list[Alert]:
        assert limit >= 1

        return [
            build_alert()
        ]


def test_cli_health(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        cli_module,
        "VectorPulseClient",
        FakeClient,
    )

    result = runner.invoke(
        app,
        [
            "health",
        ],
    )

    assert result.exit_code == 0
    assert "VectorPulse backend" in result.stdout
    assert "ok" in result.stdout


def test_cli_lists_assets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        cli_module,
        "VectorPulseClient",
        FakeClient,
    )

    result = runner.invoke(
        app,
        [
            "assets",
            "list",
        ],
    )

    assert result.exit_code == 0
    assert "tag-001" in result.stdout
    assert "receiving" in result.stdout
    assert "online" in result.stdout


def test_cli_lists_alerts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        cli_module,
        "VectorPulseClient",
        FakeClient,
    )

    result = runner.invoke(
        app,
        [
            "alerts",
            "--json",
        ],
    )

    assert result.exit_code == 0
    assert "impossible_movement" in result.stdout
    assert "critical" in result.stdout
    assert "receiving" in result.stdout
    assert "tag-001" in result.stdout
    assert "Impossible movement detected" in result.stdout


def test_cli_connection_error_has_clean_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenClient(FakeClient):
        @staticmethod
        async def health() -> HealthStatus:
            raise VectorPulseConnectionError(
                "backend unavailable"
            )

    monkeypatch.setattr(
        cli_module,
        "VectorPulseClient",
        BrokenClient,
    )

    result = runner.invoke(
        app,
        [
            "health",
        ],
    )

    assert result.exit_code == 1
    assert "Error" in result.stdout
    assert "backend unavailable" in result.stdout