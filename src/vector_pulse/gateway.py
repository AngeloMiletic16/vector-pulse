import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from vector_pulse.api.app import create_app
from vector_pulse.application.asset_registry import (
    AssetRegistry,
)
from vector_pulse.application.dwell_monitor import (
    monitor_dwell_time,
)
from vector_pulse.application.event_broadcaster import (
    EventBroadcaster,
)
from vector_pulse.application.geofencing import (
    GeofenceService,
    create_default_geofence,
)
from vector_pulse.application.offline_monitor import (
    monitor_offline_assets,
)
from vector_pulse.application.processor import (
    process_telemetry,
)
from vector_pulse.application.rules import (
    DwellRuleEngine,
    MovementRuleEngine,
    create_default_dwell_rules,
    create_default_movement_rules,
)
from vector_pulse.ingestion.mqtt_consumer import (
    consume_telemetry,
)
from vector_pulse.ingestion.schemas import (
    TelemetryMessage,
)
from vector_pulse.persistence.sqlite_storage import (
    SQLiteStorage,
)
from vector_pulse.settings import (
    VectorPulseSettings,
)


async def run_gateway_tasks(
    telemetry_queue: asyncio.Queue[
        TelemetryMessage
    ],
    registry: AssetRegistry,
    storage: SQLiteStorage,
    broadcaster: EventBroadcaster,
    geofence: GeofenceService,
    dwell_rules: DwellRuleEngine,
    movement_rules: MovementRuleEngine,
    *,
    mqtt_host: str,
    mqtt_port: int,
) -> None:
    async with asyncio.TaskGroup() as task_group:
        task_group.create_task(
            consume_telemetry(
                telemetry_queue,
                mqtt_host=mqtt_host,
                mqtt_port=mqtt_port,
            ),
            name="mqtt-consumer",
        )

        task_group.create_task(
            process_telemetry(
                telemetry_queue,
                registry,
                storage,
                broadcaster,
                geofence,
                movement_rules,
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

        task_group.create_task(
            monitor_dwell_time(
                registry,
                storage,
                broadcaster,
                dwell_rules,
            ),
            name="dwell-monitor",
        )


def create_gateway_app(
    settings: VectorPulseSettings | None = None,
) -> FastAPI:
    runtime_settings = (
        settings
        if settings is not None
        else VectorPulseSettings.from_env()
    )

    storage = SQLiteStorage(
        runtime_settings.database_path
    )

    registry = AssetRegistry()
    broadcaster = EventBroadcaster()

    geofence = create_default_geofence()

    dwell_rules = (
        create_default_dwell_rules()
    )

    movement_rules = (
        create_default_movement_rules()
    )

    telemetry_queue: asyncio.Queue[
        TelemetryMessage
    ] = asyncio.Queue(
        maxsize=(
            runtime_settings
            .telemetry_queue_max_size
        )
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

            restored_state = (
                registry.get_state(
                    state.telemetry.tag_id
                )
            )

            if restored_state is not None:
                await (
                    storage
                    .update_asset_status(
                        restored_state
                    )
                )

        print(
            f"Restored "
            f"{registry.asset_count()} "
            "persisted asset states"
        )

        print(
            "VectorPulse runtime "
            f"mqtt="
            f"{runtime_settings.mqtt_host}:"
            f"{runtime_settings.mqtt_port} "
            f"database="
            f"{runtime_settings.database_path}"
        )

        gateway_task = asyncio.create_task(
            run_gateway_tasks(
                telemetry_queue,
                registry,
                storage,
                broadcaster,
                geofence,
                dwell_rules,
                movement_rules,
                mqtt_host=(
                    runtime_settings.mqtt_host
                ),
                mqtt_port=(
                    runtime_settings.mqtt_port
                ),
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
        geofence,
        dwell_rules,
        movement_rules,
        lifespan=lifespan,
    )


SETTINGS = (
    VectorPulseSettings.from_env()
)

app = create_gateway_app(
    SETTINGS
)


if __name__ == "__main__":
    uvicorn.run(
        app,
        host=SETTINGS.api_host,
        port=SETTINGS.api_port,
        log_level="info",
    )