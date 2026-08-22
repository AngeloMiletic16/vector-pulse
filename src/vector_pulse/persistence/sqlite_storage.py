import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import aiosqlite

from vector_pulse.application.asset_registry import (
    AssetState,
    AssetStatus,
)
from vector_pulse.application.events import (
    AssetEvent,
    AssetEventType,
)
from vector_pulse.application.geofencing import ZoneName
from vector_pulse.application.rules import (
    AlertSeverity,
    RuleAlert,
    RuleAlertType,
)
from vector_pulse.ingestion.schemas import TelemetryMessage


@dataclass(frozen=True)
class StoredTelemetry:
    telemetry: TelemetryMessage
    received_at: datetime
    resolved_zone: ZoneName | None


@dataclass(frozen=True)
class StoredZoneTransition:
    event_type: AssetEventType
    zone: ZoneName
    previous_zone: ZoneName | None
    current_zone: ZoneName | None
    occurred_at: datetime
    sequence_number: int


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
                    payload_json TEXT NOT NULL,
                    resolved_zone TEXT
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
                    payload_json TEXT NOT NULL,
                    current_zone TEXT,
                    zone_entered_at TEXT,
                    dwell_alerted INTEGER NOT NULL DEFAULT 0
                )
                """
            )

            await database.execute(
                """
                CREATE TABLE IF NOT EXISTS zone_transitions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tag_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    zone TEXT NOT NULL,
                    previous_zone TEXT,
                    current_zone TEXT,
                    occurred_at TEXT NOT NULL,
                    sequence_number INTEGER NOT NULL
                )
                """
            )

            await database.execute(
                """
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tag_id TEXT NOT NULL,
                    alert_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    sequence_number INTEGER NOT NULL,
                    zone TEXT,
                    message TEXT NOT NULL,
                    details_json TEXT NOT NULL
                )
                """
            )

            await self._ensure_column(
                database,
                table_name="telemetry",
                column_name="resolved_zone",
                column_definition="TEXT",
            )

            await self._ensure_column(
                database,
                table_name="asset_state",
                column_name="current_zone",
                column_definition="TEXT",
            )

            await self._ensure_column(
                database,
                table_name="asset_state",
                column_name="zone_entered_at",
                column_definition="TEXT",
            )

            await self._ensure_column(
                database,
                table_name="asset_state",
                column_name="dwell_alerted",
                column_definition=(
                    "INTEGER NOT NULL DEFAULT 0"
                ),
            )

            await database.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_telemetry_tag_id_id
                ON telemetry(tag_id, id DESC)
                """
            )

            await database.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_zone_transitions_tag_id_id
                ON zone_transitions(tag_id, id DESC)
                """
            )

            await database.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_alerts_tag_id_id
                ON alerts(tag_id, id DESC)
                """
            )

            await database.commit()

    async def save_accepted_telemetry(
        self,
        state: AssetState,
    ) -> None:
        telemetry = state.telemetry

        current_zone = (
            state.current_zone.value
            if state.current_zone is not None
            else None
        )

        zone_entered_at = (
            state.zone_entered_at.isoformat()
            if state.zone_entered_at is not None
            else None
        )

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
                    payload_json,
                    resolved_zone
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    telemetry.tag_id,
                    telemetry.sequence_number,
                    telemetry.timestamp.isoformat(),
                    state.last_seen.isoformat(),
                    telemetry.model_dump_json(),
                    current_zone,
                ),
            )

            await database.execute(
                """
                INSERT INTO asset_state (
                    tag_id,
                    sequence_number,
                    last_seen,
                    status,
                    payload_json,
                    current_zone,
                    zone_entered_at,
                    dwell_alerted
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tag_id) DO UPDATE SET
                    sequence_number = excluded.sequence_number,
                    last_seen = excluded.last_seen,
                    status = excluded.status,
                    payload_json = excluded.payload_json,
                    current_zone = excluded.current_zone,
                    zone_entered_at = excluded.zone_entered_at,
                    dwell_alerted = excluded.dwell_alerted
                """,
                (
                    telemetry.tag_id,
                    telemetry.sequence_number,
                    state.last_seen.isoformat(),
                    state.status.value,
                    telemetry.model_dump_json(),
                    current_zone,
                    zone_entered_at,
                    int(state.dwell_alerted),
                ),
            )

            await database.commit()

    async def update_asset_runtime_state(
        self,
        state: AssetState,
    ) -> None:
        current_zone = (
            state.current_zone.value
            if state.current_zone is not None
            else None
        )

        zone_entered_at = (
            state.zone_entered_at.isoformat()
            if state.zone_entered_at is not None
            else None
        )

        async with aiosqlite.connect(
            self._database_path
        ) as database:
            await database.execute(
                """
                UPDATE asset_state
                SET
                    status = ?,
                    current_zone = ?,
                    zone_entered_at = ?,
                    dwell_alerted = ?
                WHERE tag_id = ?
                """,
                (
                    state.status.value,
                    current_zone,
                    zone_entered_at,
                    int(state.dwell_alerted),
                    state.telemetry.tag_id,
                ),
            )

            await database.commit()

    async def update_asset_status(
        self,
        state: AssetState,
    ) -> None:
        await self.update_asset_runtime_state(
            state
        )

    async def save_zone_transition(
        self,
        event: AssetEvent,
    ) -> None:
        if event.type not in {
            AssetEventType.ZONE_ENTERED,
            AssetEventType.ZONE_EXITED,
        }:
            raise ValueError(
                "Only zone transition events "
                "can be persisted here"
            )

        if event.zone is None:
            raise ValueError(
                "Zone transition event requires a zone"
            )

        previous_zone = (
            event.previous_zone.value
            if event.previous_zone is not None
            else None
        )

        current_zone = (
            event.current_zone.value
            if event.current_zone is not None
            else None
        )

        async with aiosqlite.connect(
            self._database_path
        ) as database:
            await database.execute(
                """
                INSERT INTO zone_transitions (
                    tag_id,
                    event_type,
                    zone,
                    previous_zone,
                    current_zone,
                    occurred_at,
                    sequence_number
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.tag_id,
                    event.type.value,
                    event.zone.value,
                    previous_zone,
                    current_zone,
                    event.occurred_at.isoformat(),
                    event.telemetry.sequence_number,
                ),
            )

            await database.commit()

    async def save_rule_alert(
        self,
        alert: RuleAlert,
    ) -> None:
        zone = (
            alert.zone.value
            if alert.zone is not None
            else None
        )

        async with aiosqlite.connect(
            self._database_path
        ) as database:
            await database.execute(
                """
                INSERT INTO alerts (
                    tag_id,
                    alert_type,
                    severity,
                    occurred_at,
                    sequence_number,
                    zone,
                    message,
                    details_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    alert.tag_id,
                    alert.type.value,
                    alert.severity.value,
                    alert.occurred_at.isoformat(),
                    alert.sequence_number,
                    zone,
                    alert.message,
                    json.dumps(
                        alert.details,
                        sort_keys=True,
                    ),
                ),
            )

            await database.commit()

    async def load_alerts(
        self,
        *,
        tag_id: str | None = None,
        limit: int = 50,
    ) -> list[RuleAlert]:
        if tag_id is None:
            query = """
                SELECT
                    alert_type,
                    severity,
                    tag_id,
                    occurred_at,
                    sequence_number,
                    zone,
                    message,
                    details_json
                FROM alerts
                ORDER BY id DESC
                LIMIT ?
            """

            parameters = (limit,)
        else:
            query = """
                SELECT
                    alert_type,
                    severity,
                    tag_id,
                    occurred_at,
                    sequence_number,
                    zone,
                    message,
                    details_json
                FROM alerts
                WHERE tag_id = ?
                ORDER BY id DESC
                LIMIT ?
            """

            parameters = (
                tag_id,
                limit,
            )

        async with aiosqlite.connect(
            self._database_path
        ) as database:
            async with database.execute(
                query,
                parameters,
            ) as cursor:
                rows = await cursor.fetchall()

        return [
            RuleAlert(
                type=RuleAlertType(alert_type),
                severity=AlertSeverity(severity),
                tag_id=row_tag_id,
                occurred_at=datetime.fromisoformat(
                    occurred_at
                ),
                sequence_number=sequence_number,
                zone=(
                    ZoneName(zone)
                    if zone is not None
                    else None
                ),
                message=message,
                details=json.loads(
                    details_json
                ),
            )
            for (
                alert_type,
                severity,
                row_tag_id,
                occurred_at,
                sequence_number,
                zone,
                message,
                details_json,
            ) in rows
        ]

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
                    status,
                    current_zone,
                    zone_entered_at,
                    dwell_alerted
                FROM asset_state
                ORDER BY tag_id
                """
            ) as cursor:
                rows = await cursor.fetchall()

        return [
            self._build_asset_state(
                payload_json=payload_json,
                last_seen=last_seen,
                status=status,
                current_zone=current_zone,
                zone_entered_at=zone_entered_at,
                dwell_alerted=dwell_alerted,
            )
            for (
                payload_json,
                last_seen,
                status,
                current_zone,
                zone_entered_at,
                dwell_alerted,
            ) in rows
        ]

    async def get_asset_state(
        self,
        tag_id: str,
    ) -> AssetState | None:
        async with aiosqlite.connect(
            self._database_path
        ) as database:
            async with database.execute(
                """
                SELECT
                    payload_json,
                    last_seen,
                    status,
                    current_zone,
                    zone_entered_at,
                    dwell_alerted
                FROM asset_state
                WHERE tag_id = ?
                """,
                (tag_id,),
            ) as cursor:
                row = await cursor.fetchone()

        if row is None:
            return None

        (
            payload_json,
            last_seen,
            status,
            current_zone,
            zone_entered_at,
            dwell_alerted,
        ) = row

        return self._build_asset_state(
            payload_json=payload_json,
            last_seen=last_seen,
            status=status,
            current_zone=current_zone,
            zone_entered_at=zone_entered_at,
            dwell_alerted=dwell_alerted,
        )

    async def load_telemetry_history(
        self,
        tag_id: str,
        limit: int = 20,
    ) -> list[StoredTelemetry]:
        async with aiosqlite.connect(
            self._database_path
        ) as database:
            async with database.execute(
                """
                SELECT
                    payload_json,
                    received_at,
                    resolved_zone
                FROM telemetry
                WHERE tag_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (
                    tag_id,
                    limit,
                ),
            ) as cursor:
                rows = await cursor.fetchall()

        return [
            StoredTelemetry(
                telemetry=(
                    TelemetryMessage.model_validate_json(
                        payload_json
                    )
                ),
                received_at=datetime.fromisoformat(
                    received_at
                ),
                resolved_zone=(
                    ZoneName(resolved_zone)
                    if resolved_zone is not None
                    else None
                ),
            )
            for (
                payload_json,
                received_at,
                resolved_zone,
            ) in rows
        ]

    async def load_zone_transitions(
        self,
        tag_id: str,
        limit: int = 20,
    ) -> list[StoredZoneTransition]:
        async with aiosqlite.connect(
            self._database_path
        ) as database:
            async with database.execute(
                """
                SELECT
                    event_type,
                    zone,
                    previous_zone,
                    current_zone,
                    occurred_at,
                    sequence_number
                FROM zone_transitions
                WHERE tag_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (
                    tag_id,
                    limit,
                ),
            ) as cursor:
                rows = await cursor.fetchall()

        return [
            StoredZoneTransition(
                event_type=AssetEventType(
                    event_type
                ),
                zone=ZoneName(zone),
                previous_zone=(
                    ZoneName(previous_zone)
                    if previous_zone is not None
                    else None
                ),
                current_zone=(
                    ZoneName(current_zone)
                    if current_zone is not None
                    else None
                ),
                occurred_at=datetime.fromisoformat(
                    occurred_at
                ),
                sequence_number=sequence_number,
            )
            for (
                event_type,
                zone,
                previous_zone,
                current_zone,
                occurred_at,
                sequence_number,
            ) in rows
        ]

    async def telemetry_count(self) -> int:
        return await self._count_rows(
            "telemetry"
        )

    async def zone_transition_count(self) -> int:
        return await self._count_rows(
            "zone_transitions"
        )

    async def alert_count(self) -> int:
        return await self._count_rows(
            "alerts"
        )

    async def _count_rows(
        self,
        table_name: str,
    ) -> int:
        allowed_tables = {
            "telemetry",
            "zone_transitions",
            "alerts",
        }

        if table_name not in allowed_tables:
            raise ValueError(
                "Unsupported table"
            )

        async with aiosqlite.connect(
            self._database_path
        ) as database:
            async with database.execute(
                f"SELECT COUNT(*) FROM {table_name}"
            ) as cursor:
                row = await cursor.fetchone()

        if row is None:
            return 0

        return int(row[0])

    @staticmethod
    async def _ensure_column(
        database: aiosqlite.Connection,
        *,
        table_name: str,
        column_name: str,
        column_definition: str,
    ) -> None:
        async with database.execute(
            f"PRAGMA table_info({table_name})"
        ) as cursor:
            rows = await cursor.fetchall()

        existing_columns = {
            row[1]
            for row in rows
        }

        if column_name in existing_columns:
            return

        await database.execute(
            f"ALTER TABLE {table_name} "
            f"ADD COLUMN {column_name} "
            f"{column_definition}"
        )

    @staticmethod
    def _build_asset_state(
        payload_json: str,
        last_seen: str,
        status: str,
        current_zone: str | None,
        zone_entered_at: str | None,
        dwell_alerted: int,
    ) -> AssetState:
        telemetry = (
            TelemetryMessage.model_validate_json(
                payload_json
            )
        )

        return AssetState(
            telemetry=telemetry,
            last_seen=datetime.fromisoformat(
                last_seen
            ),
            status=AssetStatus(status),
            current_zone=(
                ZoneName(current_zone)
                if current_zone is not None
                else None
            ),
            zone_entered_at=(
                datetime.fromisoformat(
                    zone_entered_at
                )
                if zone_entered_at is not None
                else None
            ),
            dwell_alerted=bool(
                dwell_alerted
            ),
        )