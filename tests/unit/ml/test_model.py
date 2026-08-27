from datetime import UTC, datetime
from pathlib import Path

from vector_pulse.ingestion.schemas import (
    Condition,
    Motion,
    Position,
    TelemetryMessage,
)
from vector_pulse.ml.model import (
    MODEL_TYPE,
    load_anomaly_model,
    predict_telemetry,
    save_anomaly_model,
    train_anomaly_model,
)


def build_baseline_telemetry(
    count: int,
) -> list[TelemetryMessage]:
    messages = []

    for index in range(count):
        messages.append(
            TelemetryMessage(
                tag_id=(
                    f"tag-{index % 5:03d}"
                ),
                sequence_number=index + 1,
                timestamp=datetime.now(UTC),
                position=Position(
                    x=5.0,
                    y=5.0,
                    quality=(
                        0.94
                        + (index % 4) * 0.01
                    ),
                ),
                motion=Motion(
                    speed_mps=(
                        0.8
                        + (index % 6) * 0.04
                    ),
                ),
                condition=Condition(
                    temperature_c=(
                        24.0
                        + (index % 5) * 0.1
                    ),
                    vibration_rms=(
                        0.10
                        + (index % 7) * 0.003
                    ),
                    battery_percent=(
                        88.0
                        + (index % 8) * 0.2
                    ),
                ),
            )
        )

    return messages


def build_typical_telemetry(
) -> TelemetryMessage:
    return TelemetryMessage(
        tag_id="tag-normal",
        sequence_number=1,
        timestamp=datetime.now(UTC),
        position=Position(
            x=5.0,
            y=5.0,
            quality=0.95,
        ),
        motion=Motion(
            speed_mps=0.90,
        ),
        condition=Condition(
            temperature_c=24.2,
            vibration_rms=0.109,
            battery_percent=88.6,
        ),
    )


def build_extreme_telemetry(
) -> TelemetryMessage:
    return TelemetryMessage(
        tag_id="tag-anomaly",
        sequence_number=1,
        timestamp=datetime.now(UTC),
        position=Position(
            x=5.0,
            y=5.0,
            quality=0.95,
        ),
        motion=Motion(
            speed_mps=1.0,
        ),
        condition=Condition(
            temperature_c=95.0,
            vibration_rms=8.0,
            battery_percent=89.0,
        ),
    )


def test_model_detects_extreme_telemetry_as_anomaly(
) -> None:
    bundle = train_anomaly_model(
        build_baseline_telemetry(
            200
        ),
        nu=0.02,
    )

    normal_prediction = (
        predict_telemetry(
            bundle,
            build_typical_telemetry(),
        )
    )

    anomaly_prediction = (
        predict_telemetry(
            bundle,
            build_extreme_telemetry(),
        )
    )

    assert (
        normal_prediction.is_anomaly
        is False
    )

    assert (
        normal_prediction
        .decision_function
        > 0
    )

    assert (
        anomaly_prediction.is_anomaly
        is True
    )

    assert (
        anomaly_prediction
        .decision_function
        < 0
    )

    assert (
        anomaly_prediction
        .anomaly_score
        > 0
    )


def test_model_artifact_can_be_saved_and_loaded(
    tmp_path: Path,
) -> None:
    bundle = train_anomaly_model(
        build_baseline_telemetry(
            150
        ),
        nu=0.03,
    )

    path = (
        tmp_path
        / "anomaly_detector.joblib"
    )

    save_anomaly_model(
        bundle,
        path,
    )

    loaded = load_anomaly_model(
        path
    )

    assert path.exists()

    assert (
        loaded.metadata.sample_count
        == 150
    )

    assert loaded.metadata.nu == 0.03

    assert (
        loaded.metadata.model_type
        == MODEL_TYPE
    )

    prediction = predict_telemetry(
        loaded,
        build_extreme_telemetry(),
    )

    assert prediction.is_anomaly is True

    assert (
        prediction.decision_function
        < 0
    )