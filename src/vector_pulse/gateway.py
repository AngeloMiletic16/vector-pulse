import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI

from vector_pulse.api.app import create_app
from vector_pulse.application.asset_registry import (
    AssetRegistry,
)
from vector_pulse.application.event_broadcaster import (
    EventBroadcaster,
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

API_HOST = "127.0.0.1"
API_PORT = 8000


async def run_gateway_tasks(
    telemetry_queue: asyncio.Queue[TelemetryMessage],
    registry: AssetRegistry,
    storage: SQLiteStorage,
    broadcaster: EventBroadcaster,
) -> None:
    async with asyncio.TaskGroup() as task_group:
        task_group.create_task(
            consume_telemetry(
                telemetry_queue
            ),
            name="mqtt-consumer",
        )

        task_group.create_task(
            process_telemetry(
                telemetry_queue,
                registry,
                storage,
                broadcaster,
            ),
            name="telemetry-processor",
        )

        task_group.create_task(
            monitor_offline_assets(
                registry,
                storage,
                broadcaster,
            ),
            name="offline-monitor",
        )


def create_gateway_app() -> FastAPI:
    storage = SQLiteStorage(
        DATABASE_PATH
    )

    registry = AssetRegistry()
    broadcaster = EventBroadcaster()

    telemetry_queue: asyncio.Queue[
        TelemetryMessage
    ] = asyncio.Queue(
        maxsize=TELEMETRY_QUEUE_MAX_SIZE
    )

    @asynccontextmanager
    async def lifespan(
        _: FastAPI,
    ) -> AsyncIterator[None]:
        await storage.initialize()

        persisted_states = (
            await storage.load_asset_states()
        )

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

        gateway_task = asyncio.create_task(
            run_gateway_tasks(
                telemetry_queue,
                registry,
                storage,
                broadcaster,
            ),
            name="gateway-runtime",
        )

        try:
            yield

        finally:
            gateway_task.cancel()

            await asyncio.gather(
                gateway_task,
                return_exceptions=True,
            )

    return create_app(
        storage,
        broadcaster,
        lifespan=lifespan,
    )


app = create_gateway_app()


if __name__ == "__main__":
    uvicorn.run(
        app,
        host=API_HOST,
        port=API_PORT,
        log_level="info",
    )