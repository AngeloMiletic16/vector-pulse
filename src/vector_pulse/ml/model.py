from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import joblib
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import RobustScaler
from sklearn.svm import OneClassSVM

from vector_pulse.ingestion.schemas import TelemetryMessage
from vector_pulse.ml.features import FEATURE_NAMES, TelemetryFeatures

MODEL_FORMAT_VERSION = 2

MODEL_TYPE = "robust_scaled_one_class_svm"


@dataclass(frozen=True)
class AnomalyModelMetadata:
    format_version: int
    model_type: str

    trained_at: datetime
    sample_count: int

    nu: float

    feature_names: tuple[str, ...]


@dataclass
class AnomalyModelBundle:
    estimator: Pipeline
    metadata: AnomalyModelMetadata


@dataclass(frozen=True)
class AnomalyPrediction:
    is_anomaly: bool

    decision_function: float
    anomaly_score: float

    features: TelemetryFeatures


def train_anomaly_model(
    telemetry_messages: Sequence[
        TelemetryMessage
    ],
    *,
    nu: float,
) -> AnomalyModelBundle:
    if not 0.001 <= nu <= 0.25:
        raise ValueError(
            "nu must be between "
            "0.001 and 0.25"
        )

    feature_rows = [
        TelemetryFeatures.from_telemetry(
            telemetry
        ).as_vector()
        for telemetry in telemetry_messages
    ]

    if not feature_rows:
        raise ValueError(
            "Training data cannot be empty"
        )

    estimator = Pipeline(
        steps=[
            (
                "scaler",
                RobustScaler(),
            ),
            (
                "detector",
                OneClassSVM(
                    kernel="rbf",
                    gamma="scale",
                    nu=nu,
                ),
            ),
        ]
    )

    estimator.fit(
        feature_rows
    )

    metadata = AnomalyModelMetadata(
        format_version=(
            MODEL_FORMAT_VERSION
        ),
        model_type=MODEL_TYPE,
        trained_at=datetime.now(UTC),
        sample_count=len(
            feature_rows
        ),
        nu=nu,
        feature_names=FEATURE_NAMES,
    )

    return AnomalyModelBundle(
        estimator=estimator,
        metadata=metadata,
    )


def predict_telemetry(
    bundle: AnomalyModelBundle,
    telemetry: TelemetryMessage,
) -> AnomalyPrediction:
    features = (
        TelemetryFeatures.from_telemetry(
            telemetry
        )
    )

    feature_vector = [
        features.as_vector()
    ]

    prediction = int(
        bundle.estimator.predict(
            feature_vector
        )[0]
    )

    decision_function = float(
        bundle.estimator.decision_function(
            feature_vector
        )[0]
    )

    return AnomalyPrediction(
        is_anomaly=prediction == -1,
        decision_function=(
            decision_function
        ),
        anomaly_score=(
            -decision_function
        ),
        features=features,
    )


def save_anomaly_model(
    bundle: AnomalyModelBundle,
    path: Path,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = path.with_suffix(
        f"{path.suffix}.tmp"
    )

    joblib.dump(
        bundle,
        temporary_path,
    )

    temporary_path.replace(
        path
    )


def load_anomaly_model(
    path: Path,
) -> AnomalyModelBundle:
    bundle = joblib.load(
        path
    )

    if not isinstance(
        bundle,
        AnomalyModelBundle,
    ):
        raise TypeError(
            "Invalid anomaly model artifact"
        )

    metadata = bundle.metadata

    if (
        metadata.format_version
        != MODEL_FORMAT_VERSION
    ):
        raise ValueError(
            "Unsupported anomaly model "
            "format version"
        )

    if metadata.model_type != MODEL_TYPE:
        raise ValueError(
            "Unsupported anomaly model type"
        )

    if (
        metadata.feature_names
        != FEATURE_NAMES
    ):
        raise ValueError(
            "Anomaly model feature schema "
            "does not match application"
        )

    return bundle