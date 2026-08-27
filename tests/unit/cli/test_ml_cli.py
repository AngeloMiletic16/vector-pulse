from datetime import UTC, datetime
from typing import Self

import pytest
from typer.testing import CliRunner

import vector_pulse.cli.ml as ml_module
from vector_pulse.cli.app import app
from vector_pulse.sdk import (
    AnomalyModelStatus,
)

runner = CliRunner()


def build_status(
    *,
    ready: bool,
    sample_count: int | None,
    nu: float | None,
) -> AnomalyModelStatus:
    return AnomalyModelStatus(
        ready=ready,
        training=False,
        model_path=(
            "/app/data/"
            "anomaly_detector.joblib"
        ),
        trained_at=(
            datetime(
                2026,
                8,
                27,
                12,
                0,
                tzinfo=UTC,
            )
            if ready
            else None
        ),
        sample_count=sample_count,
        nu=nu,
        feature_names=(
            [
                "temperature_c",
                "vibration_rms",
                "speed_mps",
                "battery_percent",
                "position_quality",
            ]
            if ready
            else None
        ),
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
    async def anomaly_status(
    ) -> AnomalyModelStatus:
        return build_status(
            ready=False,
            sample_count=None,
            nu=None,
        )

    @staticmethod
    async def train_anomaly_model(
        *,
        limit: int = 2000,
        nu: float = 0.03,
    ) -> AnomalyModelStatus:
        return build_status(
            ready=True,
            sample_count=limit,
            nu=nu,
        )


def test_cli_ml_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ml_module,
        "VectorPulseClient",
        FakeClient,
    )

    result = runner.invoke(
        app,
        [
            "ml",
            "status",
            "--json",
        ],
    )

    assert result.exit_code == 0
    assert '"ready": false' in result.stdout
    assert '"training": false' in result.stdout


def test_cli_ml_train(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ml_module,
        "VectorPulseClient",
        FakeClient,
    )

    result = runner.invoke(
        app,
        [
            "ml",
            "train",
            "--limit",
            "500",
            "--nu",
            "0.04",
            "--json",
        ],
    )

    assert result.exit_code == 0
    assert '"ready": true' in result.stdout
    assert '"sample_count": 500' in result.stdout
    assert '"nu": 0.04' in result.stdout