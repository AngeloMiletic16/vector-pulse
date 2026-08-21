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
    HealthResponse,
    TelemetryHistoryResponse,
)
from vector_pulse.application.event_broadcaster import (
    EventBroadcaster,
)
from vector_pulse.persistence.sqlite_storage import (
    SQLiteStorage,
)


def create_app(
    storage: SQLiteStorage,
    broadcaster: EventBroadcaster | None = None,
    *,
    lifespan: Lifespan[FastAPI] | None = None,
) -> FastAPI:
    if broadcaster is None:
        broadcaster = EventBroadcaster()

    app = FastAPI(
        title="VectorPulse API",
        description=(
            "HTTP and WebSocket API for industrial "
            "asset state and telemetry history."
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
        "/assets",
        response_model=list[AssetStateResponse],
    )
    async def list_assets() -> list[AssetStateResponse]:
        states = await storage.load_asset_states()

        return [
            AssetStateResponse(
                status=state.status,
                last_seen=state.last_seen,
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
                telemetry=item.telemetry,
            )
            for item in history
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
            done, pending = await asyncio.wait(
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