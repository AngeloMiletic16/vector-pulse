from datetime import UTC, datetime

from vector_pulse.ingestion.schemas import (
    Condition,
    Motion,
    Position,
    TelemetryMessage,
)
from vector_pulse.ml.features import (
    FEATURE_NAMES,
    TelemetryFeatures,
)


def test_telemetry_is_converted_to_stable_feature_vector(
) -> None:
    telemetry = TelemetryMessage(
        tag_id="tag-001",
        sequence_number=1,
        timestamp=datetime.now(UTC),
        position=Position(
            x=5.0,
            y=5.0,
            quality=0.91,
        ),
        motion=Motion(
            speed_mps=1.2,
        ),
        condition=Condition(
            temperature_c=27.5,
            vibration_rms=0.18,
            battery_percent=83.0,
        ),
    )

    features = (
        TelemetryFeatures.from_telemetry(
            telemetry
        )
    )

    assert FEATURE_NAMES == (
        "temperature_c",
        "vibration_rms",
        "speed_mps",
        "battery_percent",
        "position_quality",
    )

    assert features.as_vector() == [
        27.5,
        0.18,
        1.2,
        83.0,
        0.91,
    ]