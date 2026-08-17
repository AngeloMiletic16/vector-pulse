from datetime import datetime
from pathlib import Path

import aiosqlite

from vector_pulse.application.asset_registry import (
    AssetState,
    AssetStatus,
)
from vector_pulse.ingestion.schemas import TelemetryMessage


class SQLiteStorage:
    def __init__(
        self,
        database_path: str | Path,
    ) -> None:
        self._database_path = Path(database_path)

    async def initialize(self) -> None:
        self._database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        async with aiosqlite.connect(
            self._database_path
        ) as database:
            await database.execute(
                """
                CREATE TABLE IF NOT EXISTS telemetry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tag_id TEXT NOT NULL,
                    sequence_number INTEGER NOT NULL,
                    device_timestamp TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )

            await database.execute(
                """
                CREATE TABLE IF NOT EXISTS asset_state (
                    tag_id TEXT PRIMARY KEY,
                    sequence_number INTEGER NOT NULL,
                    last_seen TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )

            await database.commit()

    async def save_accepted_telemetry(
        self,
        state: AssetState,
    ) -> None:
        telemetry = state.telemetry
        payload_json = telemetry.model_dump_json()

        async with aiosqlite.connect(
            self._database_path
        ) as database:
            await database.execute(
                """
                INSERT INTO telemetry (
                    tag_id,
                    sequence_number,
                    device_timestamp,
                    received_at,
                    payload_json
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    telemetry.tag_id,
                    telemetry.sequence_number,
                    telemetry.timestamp.isoformat(),
                    state.last_seen.isoformat(),
                    payload_json,
                ),
            )

            await database.execute(
                """
                INSERT INTO asset_state (
                    tag_id,
                    sequence_number,
                    last_seen,
                    status,
                    payload_json
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(tag_id) DO UPDATE SET
                    sequence_number = excluded.sequence_number,
                    last_seen = excluded.last_seen,
                    status = excluded.status,
                    payload_json = excluded.payload_json
                """,
                (
                    telemetry.tag_id,
                    telemetry.sequence_number,
                    state.last_seen.isoformat(),
                    state.status.value,
                    payload_json,
                ),
            )

            await database.commit()

    async def update_asset_status(
        self,
        state: AssetState,
    ) -> None:
        async with aiosqlite.connect(
            self._database_path
        ) as database:
            await database.execute(
                """
                UPDATE asset_state
                SET status = ?
                WHERE tag_id = ?
                """,
                (
                    state.status.value,
                    state.telemetry.tag_id,
                ),
            )

            await database.commit()

    async def load_asset_states(
        self,
    ) -> list[AssetState]:
        async with aiosqlite.connect(
            self._database_path
        ) as database:
            async with database.execute(
                """
                SELECT
                    payload_json,
                    last_seen,
                    status
                FROM asset_state
                ORDER BY tag_id
                """
            ) as cursor:
                rows = await cursor.fetchall()

        states: list[AssetState] = []

        for payload_json, last_seen, status in rows:
            telemetry = TelemetryMessage.model_validate_json(
                payload_json
            )

            states.append(
                AssetState(
                    telemetry=telemetry,
                    last_seen=datetime.fromisoformat(last_seen),
                    status=AssetStatus(status),
                )
            )

        return states

    async def telemetry_count(self) -> int:
        async with aiosqlite.connect(
            self._database_path
        ) as database:
            async with database.execute(
                "SELECT COUNT(*) FROM telemetry"
            ) as cursor:
                row = await cursor.fetchone()

        if row is None:
            return 0

        return int(row[0])