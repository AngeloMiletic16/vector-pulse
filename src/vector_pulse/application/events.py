from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel

from vector_pulse.application.asset_registry import (
    AssetState,
    AssetStatus,
)
from vector_pulse.application.geofencing import (
    ZoneName,
)
from vector_pulse.ingestion.schemas import TelemetryMessage


class AssetEventType(str, Enum):
    TELEMETRY_UPDATED = "telemetry_updated"
    ASSET_OFFLINE = "asset_offline"
    ASSET_ONLINE = "asset_online"
    ZONE_ENTERED = "zone_entered"
    ZONE_EXITED = "zone_exited"


class AssetEvent(BaseModel):
    type: AssetEventType
    tag_id: str
    status: AssetStatus
    occurred_at: datetime
    last_seen: datetime
    telemetry: TelemetryMessage

    zone: ZoneName | None = None
    previous_zone: ZoneName | None = None
    current_zone: ZoneName | None = None

    @classmethod
    def from_state(
        cls,
        event_type: AssetEventType,
        state: AssetState,
        *,
        occurred_at: datetime | None = None,
        zone: ZoneName | None = None,
        previous_zone: ZoneName | None = None,
    ) -> "AssetEvent":
        if occurred_at is None:
            occurred_at = datetime.now(UTC)

        return cls(
            type=event_type,
            tag_id=state.telemetry.tag_id,
            status=state.status,
            occurred_at=occurred_at,
            last_seen=state.last_seen,
            telemetry=state.telemetry,
            zone=zone,
            previous_zone=previous_zone,
            current_zone=state.current_zone,
        )