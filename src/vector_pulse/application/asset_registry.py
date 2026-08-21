from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum

from vector_pulse.application.geofencing import (
    ZoneName,
)
from vector_pulse.ingestion.schemas import TelemetryMessage


class AssetStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"


class UpdateStatus(str, Enum):
    ACCEPTED = "accepted"
    GAP_DETECTED = "gap_detected"
    DUPLICATE = "duplicate"
    OUT_OF_ORDER = "out_of_order"


@dataclass
class AssetState:
    telemetry: TelemetryMessage
    last_seen: datetime
    status: AssetStatus
    current_zone: ZoneName | None = None
    zone_entered_at: datetime | None = None


@dataclass(frozen=True)
class UpdateResult:
    status: UpdateStatus
    missing_messages: int = 0
    came_online: bool = False


class AssetRegistry:
    def __init__(self) -> None:
        self._assets: dict[str, AssetState] = {}

    def update(
        self,
        telemetry: TelemetryMessage,
        received_at: datetime | None = None,
    ) -> UpdateResult:
        if received_at is None:
            received_at = datetime.now(UTC)

        previous = self._assets.get(
            telemetry.tag_id
        )

        if previous is None:
            self._assets[telemetry.tag_id] = (
                AssetState(
                    telemetry=telemetry,
                    last_seen=received_at,
                    status=AssetStatus.ONLINE,
                )
            )

            return UpdateResult(
                status=UpdateStatus.ACCEPTED,
            )

        came_online = (
            previous.status
            is AssetStatus.OFFLINE
        )

        if (
            came_online
            and telemetry.sequence_number
            <= previous.telemetry.sequence_number
        ):
            self._store_updated_state(
                previous=previous,
                telemetry=telemetry,
                received_at=received_at,
            )

            return UpdateResult(
                status=UpdateStatus.ACCEPTED,
                came_online=True,
            )

        if (
            telemetry.sequence_number
            == previous.telemetry.sequence_number
        ):
            return UpdateResult(
                status=UpdateStatus.DUPLICATE,
            )

        if (
            telemetry.sequence_number
            < previous.telemetry.sequence_number
        ):
            return UpdateResult(
                status=UpdateStatus.OUT_OF_ORDER,
            )

        expected_sequence = (
            previous.telemetry.sequence_number + 1
        )

        if (
            telemetry.sequence_number
            > expected_sequence
        ):
            missing_messages = (
                telemetry.sequence_number
                - expected_sequence
            )

            self._store_updated_state(
                previous=previous,
                telemetry=telemetry,
                received_at=received_at,
            )

            return UpdateResult(
                status=UpdateStatus.GAP_DETECTED,
                missing_messages=missing_messages,
                came_online=came_online,
            )

        self._store_updated_state(
            previous=previous,
            telemetry=telemetry,
            received_at=received_at,
        )

        return UpdateResult(
            status=UpdateStatus.ACCEPTED,
            came_online=came_online,
        )

    def apply_zone(
        self,
        tag_id: str,
        zone: ZoneName | None,
        changed_at: datetime,
    ) -> AssetState:
        state = self._assets.get(tag_id)

        if state is None:
            raise KeyError(
                f"Unknown asset: {tag_id}"
            )

        if state.current_zone == zone:
            return state

        state.current_zone = zone

        if zone is None:
            state.zone_entered_at = None
        else:
            state.zone_entered_at = changed_at

        return state

    def mark_offline(
        self,
        now: datetime,
        offline_after: timedelta,
    ) -> list[AssetState]:
        newly_offline: list[AssetState] = []

        for state in self._assets.values():
            if state.status is AssetStatus.OFFLINE:
                continue

            time_since_last_seen = (
                now - state.last_seen
            )

            if (
                time_since_last_seen
                >= offline_after
            ):
                state.status = AssetStatus.OFFLINE
                newly_offline.append(state)

        return newly_offline

    def restore(
        self,
        state: AssetState,
        force_offline: bool = False,
    ) -> None:
        if force_offline:
            state = AssetState(
                telemetry=state.telemetry,
                last_seen=state.last_seen,
                status=AssetStatus.OFFLINE,
                current_zone=state.current_zone,
                zone_entered_at=(
                    state.zone_entered_at
                ),
            )

        self._assets[
            state.telemetry.tag_id
        ] = state

    def get_state(
        self,
        tag_id: str,
    ) -> AssetState | None:
        return self._assets.get(tag_id)

    def get_latest(
        self,
        tag_id: str,
    ) -> TelemetryMessage | None:
        state = self.get_state(tag_id)

        if state is None:
            return None

        return state.telemetry

    def asset_count(self) -> int:
        return len(self._assets)

    def all_states(self) -> list[AssetState]:
        return list(self._assets.values())

    def _store_updated_state(
        self,
        previous: AssetState,
        telemetry: TelemetryMessage,
        received_at: datetime,
    ) -> None:
        self._assets[telemetry.tag_id] = AssetState(
            telemetry=telemetry,
            last_seen=received_at,
            status=AssetStatus.ONLINE,
            current_zone=previous.current_zone,
            zone_entered_at=(
                previous.zone_entered_at
            ),
        )