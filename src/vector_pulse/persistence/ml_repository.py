from pathlib import Path

import aiosqlite

from vector_pulse.ingestion.schemas import (
    TelemetryMessage,
)


class MLTrainingRepository:
    def __init__(
        self,
        database_path: str | Path,
    ) -> None:
        self._database_path = Path(
            database_path
        )

    async def load_recent_telemetry(
        self,
        *,
        limit: int,
    ) -> list[TelemetryMessage]:
        if limit < 1:
            raise ValueError(
                "limit must be at least 1"
            )

        async with (
            aiosqlite.connect(
                self._database_path
            ) as database,
            database.execute(
                """
                SELECT payload_json
                FROM telemetry
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ) as cursor,
        ):
            rows = await cursor.fetchall()

        telemetry_messages = [
            TelemetryMessage.model_validate_json(
                payload_json
            )
            for (payload_json,) in rows
        ]

        telemetry_messages.reverse()

        return telemetry_messages