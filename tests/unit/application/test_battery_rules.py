from datetime import UTC, datetime

import pytest

from vector_pulse.application.asset_registry import (
    AssetState,
    AssetStatus,
)
from vector_pulse.application.geofencing import ZoneName
from vector_pulse.application.rules import (
    BatteryRuleConfig,
    BatteryRuleEngine,
    RuleAlertType,
)
from vector_pulse.ingestion.schemas import (
    Condition,
    Motion,
    Position,
    TelemetryMessage,
)

NOW = datetime(
    2026,
    9,
    2,
    12,
    0,
    tzinfo=UTC,
)


def build_state(
    *,
    sequence_number: int,
    battery_percent: float,
) -> AssetState:
    return AssetState(
        telemetry=TelemetryMessage(
            tag_id="battery-tag",
            sequence_number=sequence_number,
            timestamp=NOW,
            position=Position(
                x=5.0,
                y=5.0,
                quality=0.95,
            ),
            motion=Motion(
                speed_mps=0.5,
            ),
            condition=Condition(
                temperature_c=25.0,
                vibration_rms=0.1,
                battery_percent=battery_percent,
            ),
        ),
        last_seen=NOW,
        status=AssetStatus.ONLINE,
        current_zone=ZoneName.RECEIVING,
        zone_entered_at=NOW,
        dwell_alerted=False,
    )


def test_first_low_battery_reading_generates_alert(
) -> None:
    engine = BatteryRuleEngine(
        BatteryRuleConfig()
    )

    current = build_state(
        sequence_number=1,
        battery_percent=12.0,
    )

    alert = engine.evaluate(
        None,
        current,
    )

    assert alert is not None

    assert (
        alert.type
        is RuleAlertType.LOW_BATTERY
    )

    assert alert.details[
        "battery_percent"
    ] == 12.0

    assert alert.details[
        "threshold_percent"
    ] == 20.0


def test_crossing_low_battery_threshold_generates_alert(
) -> None:
    engine = BatteryRuleEngine(
        BatteryRuleConfig()
    )

    previous = build_state(
        sequence_number=1,
        battery_percent=21.0,
    )

    current = build_state(
        sequence_number=2,
        battery_percent=20.0,
    )

    alert = engine.evaluate(
        previous,
        current,
    )

    assert alert is not None

    assert (
        alert.type
        is RuleAlertType.LOW_BATTERY
    )

    assert alert.details[
        "previous_battery_percent"
    ] == 21.0


def test_remaining_below_threshold_does_not_repeat_alert(
) -> None:
    engine = BatteryRuleEngine(
        BatteryRuleConfig()
    )

    previous = build_state(
        sequence_number=1,
        battery_percent=20.0,
    )

    current = build_state(
        sequence_number=2,
        battery_percent=15.0,
    )

    assert engine.evaluate(
        previous,
        current,
    ) is None


def test_battery_above_threshold_generates_no_alert(
) -> None:
    engine = BatteryRuleEngine(
        BatteryRuleConfig()
    )

    current = build_state(
        sequence_number=1,
        battery_percent=75.0,
    )

    assert engine.evaluate(
        None,
        current,
    ) is None


def test_recovered_asset_can_generate_new_low_battery_alert(
) -> None:
    engine = BatteryRuleEngine(
        BatteryRuleConfig()
    )

    low = build_state(
        sequence_number=1,
        battery_percent=10.0,
    )

    recovered = build_state(
        sequence_number=2,
        battery_percent=60.0,
    )

    low_again = build_state(
        sequence_number=3,
        battery_percent=19.0,
    )

    assert engine.evaluate(
        None,
        low,
    ) is not None

    assert engine.evaluate(
        low,
        recovered,
    ) is None

    assert engine.evaluate(
        recovered,
        low_again,
    ) is not None


def test_invalid_low_battery_threshold_is_rejected(
) -> None:
    with pytest.raises(
        ValueError,
        match="Low battery threshold",
    ):
        BatteryRuleConfig(
            low_battery_threshold_percent=0.0
        )