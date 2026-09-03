import asyncio

from vector_pulse.application.asset_registry import (
    AssetRegistry,
    AssetState,
    UpdateStatus,
)
from vector_pulse.application.event_broadcaster import (
    EventBroadcaster,
)
from vector_pulse.application.events import (
    AssetEvent,
    AssetEventType,
)
from vector_pulse.application.geofencing import (
    GeofenceService,
)
from vector_pulse.application.rules import (
    AlertSeverity,
    BatteryRuleEngine,
    MovementRuleEngine,
    RuleAlert,
    RuleAlertType,
    create_default_battery_rules,
    create_default_movement_rules,
)
from vector_pulse.ingestion.schemas import TelemetryMessage
from vector_pulse.ml import (
    AnomalyDetection,
    AnomalyService,
)
from vector_pulse.persistence.sqlite_storage import (
    SQLiteStorage,
)


def _build_anomaly_alert(
    detection: AnomalyDetection,
    state: AssetState,
) -> RuleAlert:
    details = {
        "anomaly_score": round(
            detection.anomaly_score,
            6,
        ),
        "decision_function": round(
            detection.decision_function,
            6,
        ),
        "model_trained_at": (
            detection.model_trained_at.isoformat()
        ),
        "model_sample_count": (
            detection.model_sample_count
        ),
    }

    details.update(
        detection.feature_values
    )

    return RuleAlert(
        type=RuleAlertType.ANOMALY_DETECTED,
        severity=AlertSeverity.WARNING,
        tag_id=detection.tag_id,
        occurred_at=detection.occurred_at,
        sequence_number=(
            detection.sequence_number
        ),
        zone=state.current_zone,
        message=(
            "ML model detected anomalous "
            "asset telemetry"
        ),
        details=details,
    )


async def _publish_alert(
    alert: RuleAlert,
    state: AssetState,
    storage: SQLiteStorage,
    broadcaster: EventBroadcaster,
) -> None:
    await storage.save_rule_alert(
        alert
    )

    await broadcaster.publish(
        AssetEvent.from_rule_alert(
            alert,
            state,
        )
    )


async def process_telemetry(
    queue: asyncio.Queue[TelemetryMessage],
    registry: AssetRegistry,
    storage: SQLiteStorage,
    broadcaster: EventBroadcaster,
    geofence: GeofenceService,
    movement_rules: MovementRuleEngine | None = None,
    anomaly_service: AnomalyService | None = None,
    battery_rules: BatteryRuleEngine | None = None,
) -> None:
    if movement_rules is None:
        movement_rules = (
            create_default_movement_rules()
        )

    if battery_rules is None:
        battery_rules = (
            create_default_battery_rules()
        )

    while True:
        telemetry = await queue.get()

        try:
            previous_state = registry.get_state(
                telemetry.tag_id
            )

            previous_zone = (
                previous_state.current_zone
                if previous_state is not None
                else None
            )

            result = registry.update(
                telemetry
            )

            if result.status is UpdateStatus.DUPLICATE:
                print(
                    f"Dropped duplicate "
                    f"tag={telemetry.tag_id} "
                    f"sequence={telemetry.sequence_number}"
                )
                continue

            if (
                result.status
                is UpdateStatus.OUT_OF_ORDER
            ):
                print(
                    "Dropped out-of-order telemetry "
                    f"tag={telemetry.tag_id} "
                    f"sequence={telemetry.sequence_number}"
                )
                continue

            state = registry.get_state(
                telemetry.tag_id
            )

            if state is None:
                raise RuntimeError(
                    "Accepted telemetry is missing "
                    "from the asset registry"
                )

            movement_alerts = (
                movement_rules.evaluate(
                    previous_state,
                    state,
                )
            )

            transition = geofence.evaluate(
                previous_zone=previous_zone,
                position=telemetry.position,
            )

            if transition.position_accepted:
                registry.apply_zone(
                    tag_id=telemetry.tag_id,
                    zone=transition.current_zone,
                    changed_at=state.last_seen,
                )
            else:
                print(
                    "Ignored low-quality position "
                    f"tag={telemetry.tag_id} "
                    "quality="
                    f"{telemetry.position.quality:.2f}"
                )

            state = registry.get_state(
                telemetry.tag_id
            )

            if state is None:
                raise RuntimeError(
                    "Asset disappeared from registry"
                )

            battery_alert = (
                battery_rules.evaluate(
                    previous_state,
                    state,
                )
            )

            await storage.save_accepted_telemetry(
                state
            )

            if result.came_online:
                print(
                    "Asset back online "
                    f"tag={telemetry.tag_id}"
                )

                await broadcaster.publish(
                    AssetEvent.from_state(
                        AssetEventType.ASSET_ONLINE,
                        state,
                        occurred_at=state.last_seen,
                    )
                )

            if (
                result.status
                is UpdateStatus.GAP_DETECTED
            ):
                print(
                    "Sequence gap detected "
                    f"tag={telemetry.tag_id} "
                    f"missing={result.missing_messages}"
                )

            for alert in movement_alerts:
                await _publish_alert(
                    alert,
                    state,
                    storage,
                    broadcaster,
                )

                print(
                    "Movement alert "
                    f"type={alert.type.value} "
                    f"tag={alert.tag_id} "
                    f"severity={alert.severity.value}"
                )

            if battery_alert is not None:
                await _publish_alert(
                    battery_alert,
                    state,
                    storage,
                    broadcaster,
                )

                print(
                    "Low battery alert "
                    f"tag={battery_alert.tag_id} "
                    "battery="
                    f"{telemetry.condition.battery_percent:.1f}%"
                )

            if anomaly_service is not None:
                detection = (
                    anomaly_service.evaluate(
                        telemetry,
                        occurred_at=state.last_seen,
                    )
                )

                if detection is not None:
                    anomaly_alert = (
                        _build_anomaly_alert(
                            detection,
                            state,
                        )
                    )

                    await _publish_alert(
                        anomaly_alert,
                        state,
                        storage,
                        broadcaster,
                    )

                    print(
                        "ML anomaly alert "
                        f"tag={anomaly_alert.tag_id} "
                        "sequence="
                        f"{anomaly_alert.sequence_number} "
                        "score="
                        f"{detection.anomaly_score:.6f}"
                    )

            if transition.changed:
                if (
                    transition.exited_zone
                    is not None
                ):
                    exit_event = (
                        AssetEvent.from_state(
                            AssetEventType.ZONE_EXITED,
                            state,
                            occurred_at=state.last_seen,
                            zone=(
                                transition.exited_zone
                            ),
                            previous_zone=(
                                transition.previous_zone
                            ),
                        )
                    )

                    await storage.save_zone_transition(
                        exit_event
                    )

                    await broadcaster.publish(
                        exit_event
                    )

                    print(
                        "Zone exited "
                        f"tag={telemetry.tag_id} "
                        "zone="
                        f"{transition.exited_zone.value}"
                    )

                if (
                    transition.entered_zone
                    is not None
                ):
                    enter_event = (
                        AssetEvent.from_state(
                            AssetEventType.ZONE_ENTERED,
                            state,
                            occurred_at=state.last_seen,
                            zone=(
                                transition.entered_zone
                            ),
                            previous_zone=(
                                transition.previous_zone
                            ),
                        )
                    )

                    await storage.save_zone_transition(
                        enter_event
                    )

                    await broadcaster.publish(
                        enter_event
                    )

                    print(
                        "Zone entered "
                        f"tag={telemetry.tag_id} "
                        "zone="
                        f"{transition.entered_zone.value}"
                    )

            await broadcaster.publish(
                AssetEvent.from_state(
                    AssetEventType.TELEMETRY_UPDATED,
                    state,
                    occurred_at=state.last_seen,
                )
            )

            current_zone = (
                state.current_zone.value
                if state.current_zone is not None
                else "outside"
            )

            print(
                f"Processed tag={telemetry.tag_id} "
                f"sequence={telemetry.sequence_number} "
                f"x={telemetry.position.x:.2f} "
                f"y={telemetry.position.y:.2f} "
                f"zone={current_zone} "
                "battery="
                f"{telemetry.condition.battery_percent:.1f}%"
            )

        finally:
            queue.task_done()