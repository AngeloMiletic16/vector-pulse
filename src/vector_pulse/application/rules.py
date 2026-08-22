from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from math import hypot
from typing import TypeAlias

from vector_pulse.application.asset_registry import (
    AssetState,
    AssetStatus,
)
from vector_pulse.application.geofencing import ZoneName


AlertDetailValue: TypeAlias = str | int | float | bool


class AlertSeverity(str, Enum):
    WARNING = "warning"
    CRITICAL = "critical"


class RuleAlertType(str, Enum):
    DWELL_TIME_EXCEEDED = "dwell_time_exceeded"
    EXCESSIVE_SPEED = "excessive_speed"
    IMPOSSIBLE_MOVEMENT = "impossible_movement"


@dataclass(frozen=True)
class RuleAlert:
    type: RuleAlertType
    severity: AlertSeverity
    tag_id: str
    occurred_at: datetime
    sequence_number: int
    zone: ZoneName | None
    message: str
    details: dict[str, AlertDetailValue]


@dataclass(frozen=True)
class DwellPolicy:
    zone: ZoneName
    threshold_seconds: float
    severity: AlertSeverity = AlertSeverity.WARNING

    def __post_init__(self) -> None:
        if self.threshold_seconds <= 0:
            raise ValueError(
                "Dwell threshold must be greater than zero"
            )


class DwellRuleEngine:
    def __init__(
        self,
        policies: tuple[DwellPolicy, ...],
    ) -> None:
        zones = [policy.zone for policy in policies]

        if len(zones) != len(set(zones)):
            raise ValueError(
                "Each zone can have only one dwell policy"
            )

        self._policies = {
            policy.zone: policy
            for policy in policies
        }

    @property
    def policies(self) -> tuple[DwellPolicy, ...]:
        return tuple(self._policies.values())

    def evaluate(
        self,
        state: AssetState,
        now: datetime,
    ) -> RuleAlert | None:
        if state.status is AssetStatus.OFFLINE:
            return None

        if state.current_zone is None:
            return None

        if state.zone_entered_at is None:
            return None

        if state.dwell_alerted:
            return None

        policy = self._policies.get(
            state.current_zone
        )

        if policy is None:
            return None

        dwell_seconds = (
            now - state.zone_entered_at
        ).total_seconds()

        if dwell_seconds < 0:
            return None

        if dwell_seconds < policy.threshold_seconds:
            return None

        return RuleAlert(
            type=RuleAlertType.DWELL_TIME_EXCEEDED,
            severity=policy.severity,
            tag_id=state.telemetry.tag_id,
            occurred_at=now,
            sequence_number=(
                state.telemetry.sequence_number
            ),
            zone=state.current_zone,
            message=(
                f"Asset exceeded dwell threshold "
                f"in {state.current_zone.value}"
            ),
            details={
                "dwell_seconds": round(
                    dwell_seconds,
                    2,
                ),
                "threshold_seconds": (
                    policy.threshold_seconds
                ),
            },
        )


@dataclass(frozen=True)
class MovementRuleConfig:
    max_reported_speed_mps: float = 6.0
    max_calculated_speed_mps: float = 12.0
    minimum_time_delta_seconds: float = 0.25

    def __post_init__(self) -> None:
        if self.max_reported_speed_mps <= 0:
            raise ValueError(
                "Maximum reported speed "
                "must be greater than zero"
            )

        if self.max_calculated_speed_mps <= 0:
            raise ValueError(
                "Maximum calculated speed "
                "must be greater than zero"
            )

        if self.minimum_time_delta_seconds <= 0:
            raise ValueError(
                "Minimum time delta "
                "must be greater than zero"
            )


class MovementRuleEngine:
    def __init__(
        self,
        config: MovementRuleConfig,
    ) -> None:
        self._config = config

    @property
    def config(self) -> MovementRuleConfig:
        return self._config

    def evaluate(
        self,
        previous_state: AssetState | None,
        current_state: AssetState,
    ) -> list[RuleAlert]:
        alerts: list[RuleAlert] = []

        telemetry = current_state.telemetry

        if (
            telemetry.motion.speed_mps
            > self._config.max_reported_speed_mps
        ):
            alerts.append(
                RuleAlert(
                    type=RuleAlertType.EXCESSIVE_SPEED,
                    severity=AlertSeverity.WARNING,
                    tag_id=telemetry.tag_id,
                    occurred_at=current_state.last_seen,
                    sequence_number=(
                        telemetry.sequence_number
                    ),
                    zone=current_state.current_zone,
                    message=(
                        "Reported asset speed "
                        "exceeded configured limit"
                    ),
                    details={
                        "reported_speed_mps": (
                            telemetry.motion.speed_mps
                        ),
                        "threshold_mps": (
                            self._config
                            .max_reported_speed_mps
                        ),
                    },
                )
            )

        if previous_state is None:
            return alerts

        previous_telemetry = (
            previous_state.telemetry
        )

        elapsed_seconds = (
            telemetry.timestamp
            - previous_telemetry.timestamp
        ).total_seconds()

        if (
            elapsed_seconds
            < self._config.minimum_time_delta_seconds
        ):
            return alerts

        delta_x = (
            telemetry.position.x
            - previous_telemetry.position.x
        )

        delta_y = (
            telemetry.position.y
            - previous_telemetry.position.y
        )

        distance_m = hypot(
            delta_x,
            delta_y,
        )

        calculated_speed_mps = (
            distance_m / elapsed_seconds
        )

        if (
            calculated_speed_mps
            > self._config.max_calculated_speed_mps
        ):
            alerts.append(
                RuleAlert(
                    type=(
                        RuleAlertType.IMPOSSIBLE_MOVEMENT
                    ),
                    severity=AlertSeverity.CRITICAL,
                    tag_id=telemetry.tag_id,
                    occurred_at=current_state.last_seen,
                    sequence_number=(
                        telemetry.sequence_number
                    ),
                    zone=current_state.current_zone,
                    message=(
                        "Calculated movement speed "
                        "exceeded physical limit"
                    ),
                    details={
                        "distance_m": round(
                            distance_m,
                            2,
                        ),
                        "elapsed_seconds": round(
                            elapsed_seconds,
                            2,
                        ),
                        "calculated_speed_mps": round(
                            calculated_speed_mps,
                            2,
                        ),
                        "threshold_mps": (
                            self._config
                            .max_calculated_speed_mps
                        ),
                    },
                )
            )

        return alerts


DEFAULT_DWELL_POLICIES = (
    DwellPolicy(
        zone=ZoneName.RECEIVING,
        threshold_seconds=30.0,
    ),
    DwellPolicy(
        zone=ZoneName.STORAGE,
        threshold_seconds=60.0,
    ),
    DwellPolicy(
        zone=ZoneName.ASSEMBLY,
        threshold_seconds=45.0,
    ),
    DwellPolicy(
        zone=ZoneName.SHIPPING,
        threshold_seconds=30.0,
    ),
)


def create_default_dwell_rules() -> DwellRuleEngine:
    return DwellRuleEngine(
        DEFAULT_DWELL_POLICIES
    )


def create_default_movement_rules() -> MovementRuleEngine:
    return MovementRuleEngine(
        MovementRuleConfig()
    )