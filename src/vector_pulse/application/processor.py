import asyncio

from vector_pulse.application.asset_registry import (
    AssetRegistry,
    UpdateStatus,
)
from vector_pulse.application.event_broadcaster import (
    EventBroadcaster,
)
from vector_pulse.application.events import (
    AssetEvent,
    AssetEventType,
)
from vector_pulse.ingestion.schemas import TelemetryMessage
from vector_pulse.persistence.sqlite_storage import (
    SQLiteStorage,
)


async def process_telemetry(
    queue: asyncio.Queue[TelemetryMessage],
    registry: AssetRegistry,
    storage: SQLiteStorage,
    broadcaster: EventBroadcaster,
) -> None:
    while True:
        telemetry = await queue.get()

        try:
            result = registry.update(telemetry)

            if result.status is UpdateStatus.DUPLICATE:
                print(
                    f"Dropped duplicate "
                    f"tag={telemetry.tag_id} "
                    f"sequence={telemetry.sequence_number}"
                )
                continue

            if result.status is UpdateStatus.OUT_OF_ORDER:
                print(
                    f"Dropped out-of-order telemetry "
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

            await storage.save_accepted_telemetry(
                state
            )

            if result.came_online:
                print(
                    f"Asset back online "
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
                    f"Sequence gap detected "
                    f"tag={telemetry.tag_id} "
                    f"missing={result.missing_messages}"
                )

            await broadcaster.publish(
                AssetEvent.from_state(
                    AssetEventType.TELEMETRY_UPDATED,
                    state,
                    occurred_at=state.last_seen,
                )
            )

            print(
                f"Processed tag={telemetry.tag_id} "
                f"sequence={telemetry.sequence_number} "
                f"x={telemetry.position.x:.2f} "
                f"y={telemetry.position.y:.2f} "
                f"battery="
                f"{telemetry.condition.battery_percent:.1f}%"
            )

        finally:
            queue.task_done()