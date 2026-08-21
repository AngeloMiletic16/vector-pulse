import asyncio
from typing import Annotated

from fastapi import (
    FastAPI,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
)
from starlette.types import Lifespan

from vector_pulse.api.schemas import (
    AssetStateResponse,
    GeofenceResponse,
    HealthResponse,
    TelemetryHistoryResponse,
    ZoneResponse,
    ZoneTransitionResponse,
)
from vector_pulse.application.event_broadcaster import (
    EventBroadcaster,
)
from vector_pulse.application.geofencing import (
    GeofenceService,
    create_default_geofence,
)
from vector_pulse.persistence.sqlite_storage import (
    SQLiteStorage,
)


def create_app(
    storage: SQLiteStorage,
    broadcaster: EventBroadcaster | None = None,
    geofence: GeofenceService | None = None,
    *,
    lifespan: Lifespan[FastAPI] | None = None,
) -> FastAPI:
    if broadcaster is None:
        broadcaster = EventBroadcaster()

    if geofence is None:
        geofence = create_default_geofence()

    app = FastAPI(
        title="VectorPulse API",
        description=(
            "HTTP and WebSocket API for industrial "
            "asset tracking and predictive monitoring."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.get(
        "/health",
        response_model=HealthResponse,
    )
    async def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
        )

    @app.get(
        "/zones",
        response_model=GeofenceResponse,
    )
    async def list_zones() -> GeofenceResponse:
        return GeofenceResponse(
            minimum_position_quality=(
                geofence.minimum_position_quality
            ),
            boundary_policy=(
                "min_inclusive_max_exclusive"
            ),
            zones=[
                ZoneResponse(
                    name=zone.name,
                    min_x=zone.min_x,
                    max_x=zone.max_x,
                    min_y=zone.min_y,
                    max_y=zone.max_y,
                )
                for zone in geofence.zones
            ],
        )

    @app.get(
        "/assets",
        response_model=list[AssetStateResponse],
    )
    async def list_assets() -> list[AssetStateResponse]:
        states = await storage.load_asset_states()

        return [
            AssetStateResponse(
                status=state.status,
                last_seen=state.last_seen,
                current_zone=state.current_zone,
                zone_entered_at=(
                    state.zone_entered_at
                ),
                telemetry=state.telemetry,
            )
            for state in states
        ]

    @app.get(
        "/assets/{tag_id}",
        response_model=AssetStateResponse,
    )
    async def get_asset(
        tag_id: str,
    ) -> AssetStateResponse:
        state = await storage.get_asset_state(
            tag_id
        )

        if state is None:
            raise HTTPException(
                status_code=404,
                detail="Asset not found",
            )

        return AssetStateResponse(
            status=state.status,
            last_seen=state.last_seen,
            current_zone=state.current_zone,
            zone_entered_at=(
                state.zone_entered_at
            ),
            telemetry=state.telemetry,
        )

    @app.get(
        "/assets/{tag_id}/telemetry",
        response_model=list[
            TelemetryHistoryResponse
        ],
    )
    async def get_telemetry_history(
        tag_id: str,
        limit: Annotated[
            int,
            Query(
                ge=1,
                le=200,
            ),
        ] = 20,
    ) -> list[TelemetryHistoryResponse]:
        state = await storage.get_asset_state(
            tag_id
        )

        if state is None:
            raise HTTPException(
                status_code=404,
                detail="Asset not found",
            )

        history = (
            await storage.load_telemetry_history(
                tag_id=tag_id,
                limit=limit,
            )
        )

        return [
            TelemetryHistoryResponse(
                received_at=item.received_at,
                resolved_zone=item.resolved_zone,
                telemetry=item.telemetry,
            )
            for item in history
        ]

    @app.get(
        "/assets/{tag_id}/zone-transitions",
        response_model=list[
            ZoneTransitionResponse
        ],
    )
    async def get_zone_transitions(
        tag_id: str,
        limit: Annotated[
            int,
            Query(
                ge=1,
                le=200,
            ),
        ] = 20,
    ) -> list[ZoneTransitionResponse]:
        state = await storage.get_asset_state(
            tag_id
        )

        if state is None:
            raise HTTPException(
                status_code=404,
                detail="Asset not found",
            )

        transitions = (
            await storage.load_zone_transitions(
                tag_id=tag_id,
                limit=limit,
            )
        )

        return [
            ZoneTransitionResponse(
                type=item.event_type,
                zone=item.zone,
                previous_zone=item.previous_zone,
                current_zone=item.current_zone,
                occurred_at=item.occurred_at,
                sequence_number=(
                    item.sequence_number
                ),
            )
            for item in transitions
        ]

    @app.websocket("/ws/assets")
    async def asset_events(
        websocket: WebSocket,
    ) -> None:
        await websocket.accept()

        event_queue = broadcaster.subscribe()

        await websocket.send_json(
            {
                "type": "connected",
                "message": (
                    "Subscribed to live asset events"
                ),
            }
        )

        async def send_events() -> None:
            while True:
                event = await event_queue.get()

                try:
                    await websocket.send_json(
                        event.model_dump(
                            mode="json"
                        )
                    )
                finally:
                    event_queue.task_done()

        async def wait_for_disconnect() -> None:
            while True:
                message = await websocket.receive()

                if (
                    message["type"]
                    == "websocket.disconnect"
                ):
                    return

        sender = asyncio.create_task(
            send_events(),
            name="websocket-event-sender",
        )

        receiver = asyncio.create_task(
            wait_for_disconnect(),
            name="websocket-disconnect-listener",
        )

        try:
            done, _ = await asyncio.wait(
                {
                    sender,
                    receiver,
                },
                return_when=asyncio.FIRST_COMPLETED,
            )

            for task in done:
                task.result()

        except (
            WebSocketDisconnect,
            RuntimeError,
        ):
            pass

        finally:
            for task in (
                sender,
                receiver,
            ):
                if not task.done():
                    task.cancel()

            await asyncio.gather(
                sender,
                receiver,
                return_exceptions=True,
            )

            broadcaster.unsubscribe(
                event_queue
            )

    return app