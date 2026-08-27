from datetime import datetime

from pydantic import BaseModel, Field

from vector_pulse.application.asset_registry import (
    AssetStatus,
)
from vector_pulse.application.events import (
    AssetEventType,
)
from vector_pulse.application.geofencing import ZoneName
from vector_pulse.application.rules import (
    AlertDetailValue,
    AlertSeverity,
    RuleAlertType,
)
from vector_pulse.ingestion.schemas import TelemetryMessage


class HealthResponse(BaseModel):
    status: str


class AnomalyTrainingRequest(BaseModel):
    limit: int = Field(
        default=2000,
        ge=100,
        le=10_000,
    )

    nu: float = Field(
        default=0.03,
        ge=0.001,
        le=0.25,
    )


class AnomalyModelStatusResponse(BaseModel):
    ready: bool
    training: bool

    model_path: str

    trained_at: datetime | None
    sample_count: int | None
    nu: float | None

    feature_names: list[str] | None


class AssetStateResponse(BaseModel):
    status: AssetStatus
    last_seen: datetime
    current_zone: ZoneName | None
    zone_entered_at: datetime | None
    dwell_alerted: bool
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


class AlertResponse(BaseModel):
    type: RuleAlertType
    severity: AlertSeverity
    tag_id: str
    occurred_at: datetime
    sequence_number: int
    zone: ZoneName | None
    message: str
    details: dict[str, AlertDetailValue]


class DwellPolicyResponse(BaseModel):
    zone: ZoneName
    threshold_seconds: float
    severity: AlertSeverity


class MovementRulesResponse(BaseModel):
    max_reported_speed_mps: float
    max_calculated_speed_mps: float
    minimum_time_delta_seconds: float


class MonitoringRulesResponse(BaseModel):
    dwell_policies: list[DwellPolicyResponse]
    movement: MovementRulesResponse