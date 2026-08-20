from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query

from vector_pulse.api.schemas import (
    AssetStateResponse,
    HealthResponse,
    TelemetryHistoryResponse,
)
from vector_pulse.persistence.sqlite_storage import (
    SQLiteStorage,
)


DATABASE_PATH = Path("data/vectorpulse.db")


def create_app(
    storage: SQLiteStorage,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(
        _: FastAPI,
    ) -> AsyncIterator[None]:
        await storage.initialize()
        yield

    app = FastAPI(
        title="VectorPulse API",
        description=(
            "HTTP API for industrial asset state "
            "and telemetry history."
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
        state = await storage.get_asset_state(tag_id)

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
        response_model=list[TelemetryHistoryResponse],
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
        state = await storage.get_asset_state(tag_id)

        if state is None:
            raise HTTPException(
                status_code=404,
                detail="Asset not found",
            )

        history = await storage.load_telemetry_history(
            tag_id=tag_id,
            limit=limit,
        )

        return [
            TelemetryHistoryResponse(
                received_at=item.received_at,
                telemetry=item.telemetry,
            )
            for item in history
        ]

    return app


storage = SQLiteStorage(DATABASE_PATH)
app = create_app(storage)