from datetime import UTC, datetime
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from vector_pulse.api.app import create_app
from vector_pulse.ml import (
    AnomalyServiceStatus,
    InsufficientTrainingDataError,
)
from vector_pulse.persistence.sqlite_storage import (
    SQLiteStorage,
)


class FakeAnomalyService:
    def __init__(
        self,
        model_path: Path,
    ) -> None:
        self._model_path = model_path

        self.last_training_request: (
            tuple[int, float] | None
        ) = None

        self._status = AnomalyServiceStatus(
            ready=False,
            training=False,
            model_path=model_path,
        )

    def status(
        self,
    ) -> AnomalyServiceStatus:
        return self._status

    async def train(
        self,
        *,
        limit: int = 2000,
        nu: float = 0.03,
    ) -> AnomalyServiceStatus:
        self.last_training_request = (
            limit,
            nu,
        )

        self._status = AnomalyServiceStatus(
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

        return self._status


class InsufficientDataAnomalyService(
    FakeAnomalyService
):
    async def train(
        self,
        *,
        limit: int = 2000,
        nu: float = 0.03,
    ) -> AnomalyServiceStatus:
        raise InsufficientTrainingDataError(
            "Not enough telemetry samples"
        )


@pytest.mark.asyncio
async def test_anomaly_status_endpoint_reports_untrained_model(
    tmp_path: Path,
) -> None:
    storage = SQLiteStorage(
        tmp_path / "api.db"
    )

    service = FakeAnomalyService(
        tmp_path / "model.joblib"
    )

    app = create_app(
        storage,
        anomaly_service=service,
    )

    transport = ASGITransport(
        app=app
    )

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/ml/anomaly/status"
        )

    assert response.status_code == 200

    payload = response.json()

    assert payload["ready"] is False
    assert payload["training"] is False
    assert payload["sample_count"] is None
    assert payload["nu"] is None
    assert payload["feature_names"] is None


@pytest.mark.asyncio
async def test_anomaly_training_endpoint_trains_model(
    tmp_path: Path,
) -> None:
    storage = SQLiteStorage(
        tmp_path / "api.db"
    )

    service = FakeAnomalyService(
        tmp_path / "model.joblib"
    )

    app = create_app(
        storage,
        anomaly_service=service,
    )

    transport = ASGITransport(
        app=app
    )

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/ml/anomaly/train",
            json={
                "limit": 500,
                "nu": 0.03,
            },
        )

    assert response.status_code == 200

    assert (
        service.last_training_request
        == (
            500,
            0.03,
        )
    )

    payload = response.json()

    assert payload["ready"] is True
    assert payload["sample_count"] == 500
    assert payload["nu"] == 0.03

    assert payload["feature_names"] == [
        "temperature_c",
        "vibration_rms",
        "speed_mps",
        "battery_percent",
        "position_quality",
    ]


@pytest.mark.asyncio
async def test_training_returns_conflict_when_data_is_insufficient(
    tmp_path: Path,
) -> None:
    storage = SQLiteStorage(
        tmp_path / "api.db"
    )

    service = (
        InsufficientDataAnomalyService(
            tmp_path / "model.joblib"
        )
    )

    app = create_app(
        storage,
        anomaly_service=service,
    )

    transport = ASGITransport(
        app=app
    )

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/ml/anomaly/train",
            json={
                "limit": 500,
                "nu": 0.03,
            },
        )

    assert response.status_code == 409

    assert response.json() == {
        "detail": (
            "Not enough telemetry samples"
        )
    }