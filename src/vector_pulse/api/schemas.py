from datetime import datetime

from pydantic import BaseModel

from vector_pulse.application.asset_registry import (
    AssetStatus,
)
from vector_pulse.application.events import (
    AssetEventType,
)
from vector_pulse.application.geofencing import (
    ZoneName,
)
from vector_pulse.ingestion.schemas import TelemetryMessage


class HealthResponse(BaseModel):
    status: str


class AssetStateResponse(BaseModel):
    status: AssetStatus
    last_seen: datetime
    current_zone: ZoneName | None
    zone_entered_at: datetime | None
    telemetry: TelemetryMessage


class TelemetryHistoryResponse(BaseModel):
    received_at: datetime
    resolved_zone: ZoneName | None
    telemetry: TelemetryMessage


class ZoneResponse(BaseModel):
    name: ZoneName
    min_x: float
    max_x: float
    min_y: float
    max_y: float


class GeofenceResponse(BaseModel):
    minimum_position_quality: float
    boundary_policy: str
    zones: list[ZoneResponse]


class ZoneTransitionResponse(BaseModel):
    type: AssetEventType
    zone: ZoneName
    previous_zone: ZoneName | None
    current_zone: ZoneName | None
    occurred_at: datetime
    sequence_number: int