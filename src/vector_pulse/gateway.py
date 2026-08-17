import asyncio
from pathlib import Path

from vector_pulse.application.asset_registry import (
    AssetRegistry,
)
from vector_pulse.application.offline_monitor import (
    monitor_offline_assets,
)
from vector_pulse.application.processor import (
    process_telemetry,
)
from vector_pulse.ingestion.mqtt_consumer import (
    consume_telemetry,
)
from vector_pulse.ingestion.schemas import TelemetryMessage
from vector_pulse.persistence.sqlite_storage import (
    SQLiteStorage,
)


TELEMETRY_QUEUE_MAX_SIZE = 1000
DATABASE_PATH = Path("data/vectorpulse.db")


async def main() -> None:
    storage = SQLiteStorage(DATABASE_PATH)
    await storage.initialize()

    registry = AssetRegistry()

    persisted_states = await storage.load_asset_states()

    for state in persisted_states:
        registry.restore(
            state,
            force_offline=True,
        )

        restored_state = registry.get_state(
            state.telemetry.tag_id
        )

        if restored_state is not None:
            await storage.update_asset_status(
                restored_state
            )

    print(
        f"Restored {registry.asset_count()} "
        f"persisted asset states"
    )

    telemetry_queue: asyncio.Queue[TelemetryMessage] = (
        asyncio.Queue(
            maxsize=TELEMETRY_QUEUE_MAX_SIZE
        )
    )

    async with asyncio.TaskGroup() as task_group:
        task_group.create_task(
            consume_telemetry(telemetry_queue),
            name="mqtt-consumer",
        )

        task_group.create_task(
            process_telemetry(
                telemetry_queue,
                registry,
                storage,
            ),
            name="telemetry-processor",
        )

        task_group.create_task(
            monitor_offline_assets(
                registry,
                storage,
            ),
            name="offline-monitor",
        )


if __name__ == "__main__":
    asyncio.run(main())