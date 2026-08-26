from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict

type AlertDetailValue = str | int | float | bool


class SDKModel(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
    )


class AssetStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"


class ZoneName(str, Enum):
    RECEIVING = "receiving"
    STORAGE = "storage"
    ASSEMBLY = "assembly"
    SHIPPING = "shipping"


class AlertSeverity(str, Enum):
    WARNING = "warning"
    CRITICAL = "critical"


class AlertType(str, Enum):
    DWELL_TIME_EXCEEDED = "dwell_time_exceeded"
    EXCESSIVE_SPEED = "excessive_speed"
    IMPOSSIBLE_MOVEMENT = "impossible_movement"


class Position(SDKModel):
    x: float
    y: float
    quality: float


class Motion(SDKModel):
    speed_mps: float


class Condition(SDKModel):
    temperature_c: float
    vibration_rms: float
    battery_percent: float


class TelemetryMessage(SDKModel):
    tag_id: str
    sequence_number: int
    timestamp: datetime
    position: Position
    motion: Motion
    condition: Condition


class HealthStatus(SDKModel):
    status: str


class AssetState(SDKModel):
    status: AssetStatus
    last_seen: datetime
    current_zone: ZoneName | None
    zone_entered_at: datetime | None
    dwell_alerted: bool
    telemetry: TelemetryMessage


class TelemetryHistoryItem(SDKModel):
    received_at: datetime
    resolved_zone: ZoneName | None
    telemetry: TelemetryMessage


class Zone(SDKModel):
    name: ZoneName
    min_x: float
    max_x: float
    min_y: float
    max_y: float


class GeofenceConfiguration(SDKModel):
    minimum_position_quality: float
    boundary_policy: str
    zones: list[Zone]


class ZoneTransition(SDKModel):
    type: str
    zone: ZoneName
    previous_zone: ZoneName | None
    current_zone: ZoneName | None
    occurred_at: datetime
    sequence_number: int


class Alert(SDKModel):
    type: AlertType
    severity: AlertSeverity
    tag_id: str
    occurred_at: datetime
    sequence_number: int
    zone: ZoneName | None
    message: str
    details: dict[str, AlertDetailValue]


class DwellPolicy(SDKModel):
    zone: ZoneName
    threshold_seconds: float
    severity: AlertSeverity


class MovementRules(SDKModel):
    max_reported_speed_mps: float
    max_calculated_speed_mps: float
    minimum_time_delta_seconds: float


class MonitoringRules(SDKModel):
    dwell_policies: list[DwellPolicy]
    movement: MovementRules


class LiveEvent(SDKModel):
    type: str

    tag_id: str | None = None
    status: AssetStatus | None = None

    occurred_at: datetime | None = None
    last_seen: datetime | None = None

    telemetry: TelemetryMessage | None = None

    zone: ZoneName | None = None
    previous_zone: ZoneName | None = None
    current_zone: ZoneName | None = None

    severity: AlertSeverity | None = None
    message: str | None = None

    details: (
        dict[str, AlertDetailValue] | None
    ) = None