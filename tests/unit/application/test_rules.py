from datetime import UTC, datetime, timedelta

from vector_pulse.application.asset_registry import (
    AssetState,
    AssetStatus,
)
from vector_pulse.application.geofencing import ZoneName
from vector_pulse.application.rules import (
    DwellPolicy,
    DwellRuleEngine,
    MovementRuleConfig,
    MovementRuleEngine,
    RuleAlertType,
)
from vector_pulse.ingestion.schemas import (
    Condition,
    Motion,
    Position,
    TelemetryMessage,
)


def build_state(
    *,
    sequence_number: int = 1,
    timestamp: datetime,
    x: float = 5.0,
    speed_mps: float = 1.0,
    zone: ZoneName | None = ZoneName.RECEIVING,
    status: AssetStatus = AssetStatus.ONLINE,
    dwell_alerted: bool = False,
) -> AssetState:
    telemetry = TelemetryMessage(
        tag_id="tag-001",
        sequence_number=sequence_number,
        timestamp=timestamp,
        position=Position(
            x=x,
            y=5.0,
            quality=0.95,
        ),
        motion=Motion(
            speed_mps=speed_mps,
        ),
        condition=Condition(
            temperature_c=25.0,
            vibration_rms=0.1,
            battery_percent=90.0,
        ),
    )

    return AssetState(
        telemetry=telemetry,
        last_seen=timestamp,
        status=status,
        current_zone=zone,
        zone_entered_at=timestamp,
        dwell_alerted=dwell_alerted,
    )


def test_excessive_reported_speed_is_detected() -> None:
    now = datetime(
        2026,
        8,
        22,
        12,
        0,
        tzinfo=UTC,
    )

    engine = MovementRuleEngine(
        MovementRuleConfig(
            max_reported_speed_mps=6.0,
            max_calculated_speed_mps=12.0,
        )
    )

    current = build_state(
        timestamp=now,
        speed_mps=10.0,
    )

    alerts = engine.evaluate(
        None,
        current,
    )

    assert len(alerts) == 1
    assert (
        alerts[0].type
        is RuleAlertType.EXCESSIVE_SPEED
    )


def test_impossible_movement_is_detected() -> None:
    start = datetime(
        2026,
        8,
        22,
        12,
        0,
        tzinfo=UTC,
    )

    engine = MovementRuleEngine(
        MovementRuleConfig()
    )

    previous = build_state(
        sequence_number=1,
        timestamp=start,
        x=5.0,
    )

    current = build_state(
        sequence_number=2,
        timestamp=start + timedelta(seconds=1),
        x=50.0,
    )

    alerts = engine.evaluate(
        previous,
        current,
    )

    assert len(alerts) == 1
    assert (
        alerts[0].type
        is RuleAlertType.IMPOSSIBLE_MOVEMENT
    )


def test_normal_movement_generates_no_alert() -> None:
    start = datetime(
        2026,
        8,
        22,
        12,
        0,
        tzinfo=UTC,
    )

    engine = MovementRuleEngine(
        MovementRuleConfig()
    )

    previous = build_state(
        sequence_number=1,
        timestamp=start,
        x=5.0,
    )

    current = build_state(
        sequence_number=2,
        timestamp=start + timedelta(seconds=2),
        x=6.0,
    )

    assert engine.evaluate(
        previous,
        current,
    ) == []


def test_dwell_threshold_generates_alert() -> None:
    entered_at = datetime(
        2026,
        8,
        22,
        12,
        0,
        tzinfo=UTC,
    )

    state = build_state(
        timestamp=entered_at,
    )

    engine = DwellRuleEngine(
        (
            DwellPolicy(
                zone=ZoneName.RECEIVING,
                threshold_seconds=30.0,
            ),
        )
    )

    alert = engine.evaluate(
        state,
        entered_at + timedelta(seconds=31),
    )

    assert alert is not None

    assert (
        alert.type
        is RuleAlertType.DWELL_TIME_EXCEEDED
    )


def test_dwell_alert_is_not_repeated() -> None:
    entered_at = datetime(
        2026,
        8,
        22,
        12,
        0,
        tzinfo=UTC,
    )

    state = build_state(
        timestamp=entered_at,
        dwell_alerted=True,
    )

    engine = DwellRuleEngine(
        (
            DwellPolicy(
                zone=ZoneName.RECEIVING,
                threshold_seconds=30.0,
            ),
        )
    )

    alert = engine.evaluate(
        state,
        entered_at + timedelta(seconds=60),
    )

    assert alert is None


def test_offline_asset_does_not_generate_dwell_alert() -> None:
    entered_at = datetime(
        2026,
        8,
        22,
        12,
        0,
        tzinfo=UTC,
    )

    state = build_state(
        timestamp=entered_at,
        status=AssetStatus.OFFLINE,
    )

    engine = DwellRuleEngine(
        (
            DwellPolicy(
                zone=ZoneName.RECEIVING,
                threshold_seconds=30.0,
            ),
        )
    )

    alert = engine.evaluate(
        state,
        entered_at + timedelta(seconds=60),
    )

    assert alert is None