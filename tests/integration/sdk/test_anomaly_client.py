from datetime import UTC, datetime
from pathlib import Path

import pytest
from httpx import ASGITransport

from vector_pulse.api.app import create_app
from vector_pulse.ml import (
    AnomalyServiceStatus,
)
from vector_pulse.persistence.sqlite_storage import (
    SQLiteStorage,
)
from vector_pulse.sdk import (
    VectorPulseClient,
)


class FakeAnomalyService:
    def __init__(
        self,
        model_path: Path,
    ) -> None:
        self._model_path = model_path

    def status(
        self,
    ) -> AnomalyServiceStatus:
        return AnomalyServiceStatus(
            ready=False,
            training=False,
            model_path=self._model_path,
        )

    async def train(
        self,
        *,
        limit: int = 2000,
        nu: float = 0.03,
    ) -> AnomalyServiceStatus:
        return AnomalyServiceStatus(
            ready=True,
            training=False,
            model_path=self._model_path,
            trained_at=datetime(
                2026,
                8,
                27,
                12,
                0,
                tzinfo=UTC,
            ),
            sample_count=limit,
            nu=nu,
            feature_names=(
                "temperature_c",
                "vibration_rms",
                "speed_mps",
                "battery_percent",
                "position_quality",
            ),
        )


def build_client(
    tmp_path: Path,
) -> VectorPulseClient:
    storage = SQLiteStorage(
        tmp_path / "test.db"
    )

    service = FakeAnomalyService(
        tmp_path / "model.joblib"
    )

    app = create_app(
        storage,
        anomaly_service=service,
    )

    return VectorPulseClient(
        base_url="http://test",
        transport=ASGITransport(
            app=app
        ),
    )


@pytest.mark.asyncio
async def test_sdk_reads_anomaly_model_status(
    tmp_path: Path,
) -> None:
    client = build_client(
        tmp_path
    )

    async with client:
        status = (
            await client.anomaly_status()
        )

    assert status.ready is False
    assert status.training is False
    assert status.sample_count is None
    assert status.nu is None


@pytest.mark.asyncio
async def test_sdk_trains_anomaly_model(
    tmp_path: Path,
) -> None:
    client = build_client(
        tmp_path
    )

    async with client:
        status = (
            await client.train_anomaly_model(
                limit=500,
                nu=0.04,
            )
        )

    assert status.ready is True
    assert status.sample_count == 500
    assert status.nu == 0.04

    assert status.feature_names == [
        "temperature_c",
        "vibration_rms",
        "speed_mps",
        "battery_percent",
        "position_quality",
    ]