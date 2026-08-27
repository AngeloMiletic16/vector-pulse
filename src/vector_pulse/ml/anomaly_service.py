import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Protocol

from vector_pulse.ingestion.schemas import (
    TelemetryMessage,
)
from vector_pulse.ml.model import (
    AnomalyModelBundle,
    AnomalyPrediction,
    load_anomaly_model,
    predict_telemetry,
    save_anomaly_model,
    train_anomaly_model,
)


class TrainingTelemetryRepository(
    Protocol
):
    async def load_recent_telemetry(
        self,
        *,
        limit: int,
    ) -> list[TelemetryMessage]:
        ...


class InsufficientTrainingDataError(
    ValueError
):
    pass


@dataclass(frozen=True)
class AnomalyServiceStatus:
    ready: bool
    training: bool

    model_path: Path

    trained_at: datetime | None = None
    sample_count: int | None = None

    nu: float | None = None

    feature_names: (
        tuple[str, ...] | None
    ) = None


@dataclass(frozen=True)
class AnomalyDetection:
    tag_id: str
    sequence_number: int
    occurred_at: datetime

    anomaly_score: float
    decision_function: float

    feature_values: dict[
        str,
        float,
    ]

    model_trained_at: datetime
    model_sample_count: int


class AnomalyService:
    def __init__(
        self,
        repository: (
            TrainingTelemetryRepository
        ),
        model_path: Path,
        *,
        minimum_training_samples: int = 100,
        required_consecutive_anomalies: int = 3,
        alert_cooldown_seconds: float = 30.0,
    ) -> None:
        if minimum_training_samples < 10:
            raise ValueError(
                "minimum_training_samples "
                "must be at least 10"
            )

        if (
            required_consecutive_anomalies
            < 1
        ):
            raise ValueError(
                "required_consecutive_anomalies "
                "must be at least 1"
            )

        if alert_cooldown_seconds < 0:
            raise ValueError(
                "alert_cooldown_seconds "
                "cannot be negative"
            )

        self._repository = repository
        self._model_path = model_path

        self._minimum_training_samples = (
            minimum_training_samples
        )

        self._required_consecutive_anomalies = (
            required_consecutive_anomalies
        )

        self._alert_cooldown = timedelta(
            seconds=alert_cooldown_seconds
        )

        self._bundle: (
            AnomalyModelBundle | None
        ) = None

        self._training = False

        self._training_lock = (
            asyncio.Lock()
        )

        self._anomaly_streaks: dict[
            str,
            int,
        ] = {}

        self._last_alert_at: dict[
            str,
            datetime,
        ] = {}

    async def initialize(
        self,
    ) -> None:
        if not self._model_path.exists():
            return

        self._bundle = (
            await asyncio.to_thread(
                load_anomaly_model,
                self._model_path,
            )
        )

    def status(
        self,
    ) -> AnomalyServiceStatus:
        bundle = self._bundle

        if bundle is None:
            return AnomalyServiceStatus(
                ready=False,
                training=self._training,
                model_path=self._model_path,
            )

        metadata = bundle.metadata

        return AnomalyServiceStatus(
            ready=True,
            training=self._training,
            model_path=self._model_path,
            trained_at=metadata.trained_at,
            sample_count=(
                metadata.sample_count
            ),
            nu=metadata.nu,
            feature_names=(
                metadata.feature_names
            ),
        )

    async def train(
        self,
        *,
        limit: int = 2000,
        nu: float = 0.03,
    ) -> AnomalyServiceStatus:
        if (
            limit
            < self._minimum_training_samples
        ):
            raise ValueError(
                "Training limit cannot be "
                "smaller than minimum "
                "training sample count"
            )

        async with self._training_lock:
            self._training = True

            try:
                telemetry_messages = (
                    await self._repository
                    .load_recent_telemetry(
                        limit=limit
                    )
                )

                sample_count = len(
                    telemetry_messages
                )

                if (
                    sample_count
                    < self._minimum_training_samples
                ):
                    raise (
                        InsufficientTrainingDataError(
                            "Anomaly model requires "
                            "at least "
                            f"{self._minimum_training_samples} "
                            "telemetry samples; "
                            f"found {sample_count}"
                        )
                    )

                bundle = (
                    await asyncio.to_thread(
                        train_anomaly_model,
                        telemetry_messages,
                        nu=nu,
                    )
                )

                await asyncio.to_thread(
                    save_anomaly_model,
                    bundle,
                    self._model_path,
                )

                self._bundle = bundle

                self._anomaly_streaks.clear()
                self._last_alert_at.clear()

            finally:
                self._training = False

        return self.status()

    def predict(
        self,
        telemetry: TelemetryMessage,
    ) -> AnomalyPrediction | None:
        bundle = self._bundle

        if bundle is None:
            return None

        return predict_telemetry(
            bundle,
            telemetry,
        )

    def evaluate(
        self,
        telemetry: TelemetryMessage,
        *,
        occurred_at: datetime,
    ) -> AnomalyDetection | None:
        bundle = self._bundle

        if bundle is None:
            return None

        prediction = predict_telemetry(
            bundle,
            telemetry,
        )

        tag_id = telemetry.tag_id

        if not prediction.is_anomaly:
            self._anomaly_streaks[
                tag_id
            ] = 0

            return None

        current_streak = (
            self._anomaly_streaks.get(
                tag_id,
                0,
            )
            + 1
        )

        self._anomaly_streaks[
            tag_id
        ] = current_streak

        if (
            current_streak
            < self._required_consecutive_anomalies
        ):
            return None

        last_alert_at = (
            self._last_alert_at.get(
                tag_id
            )
        )

        if last_alert_at is not None:
            elapsed = (
                occurred_at
                - last_alert_at
            )

            if (
                elapsed
                < self._alert_cooldown
            ):
                self._anomaly_streaks[
                    tag_id
                ] = 0

                return None

        self._anomaly_streaks[
            tag_id
        ] = 0

        self._last_alert_at[
            tag_id
        ] = occurred_at

        metadata = bundle.metadata

        return AnomalyDetection(
            tag_id=tag_id,
            sequence_number=(
                telemetry.sequence_number
            ),
            occurred_at=occurred_at,
            anomaly_score=(
                prediction.anomaly_score
            ),
            decision_function=(
                prediction.decision_function
            ),
            feature_values=(
                prediction.features.as_dict()
            ),
            model_trained_at=(
                metadata.trained_at
            ),
            model_sample_count=(
                metadata.sample_count
            ),
        )