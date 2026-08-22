import asyncio
from datetime import UTC, datetime

from vector_pulse.application.asset_registry import (
    AssetRegistry,
)
from vector_pulse.application.event_broadcaster import (
    EventBroadcaster,
)
from vector_pulse.application.events import AssetEvent
from vector_pulse.application.rules import (
    DwellRuleEngine,
    RuleAlert,
)
from vector_pulse.persistence.sqlite_storage import (
    SQLiteStorage,
)


DWELL_CHECK_INTERVAL_SECONDS = 2.0


async def check_dwell_alerts(
    registry: AssetRegistry,
    storage: SQLiteStorage,
    broadcaster: EventBroadcaster,
    rules: DwellRuleEngine,
    *,
    now: datetime | None = None,
) -> list[RuleAlert]:
    if now is None:
        now = datetime.now(UTC)

    generated_alerts: list[RuleAlert] = []

    for state in registry.all_states():
        alert = rules.evaluate(
            state,
            now,
        )

        if alert is None:
            continue

        await storage.save_rule_alert(
            alert
        )

        updated_state = (
            registry.mark_dwell_alerted(
                state.telemetry.tag_id
            )
        )

        await storage.update_asset_runtime_state(
            updated_state
        )

        await broadcaster.publish(
            AssetEvent.from_rule_alert(
                alert,
                updated_state,
            )
        )

        generated_alerts.append(alert)

        print(
            f"Dwell threshold exceeded "
            f"tag={alert.tag_id} "
            f"zone={alert.zone.value if alert.zone else 'outside'} "
            f"dwell="
            f"{alert.details['dwell_seconds']}s"
        )

    return generated_alerts


async def monitor_dwell_time(
    registry: AssetRegistry,
    storage: SQLiteStorage,
    broadcaster: EventBroadcaster,
    rules: DwellRuleEngine,
    *,
    check_interval_seconds: float = (
        DWELL_CHECK_INTERVAL_SECONDS
    ),
) -> None:
    while True:
        await asyncio.sleep(
            check_interval_seconds
        )

        await check_dwell_alerts(
            registry,
            storage,
            broadcaster,
            rules,
        )