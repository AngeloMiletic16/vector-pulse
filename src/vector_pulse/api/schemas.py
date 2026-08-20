from datetime import datetime

from pydantic import BaseModel

from vector_pulse.application.asset_registry import (
    AssetStatus,
)
from vector_pulse.ingestion.schemas import TelemetryMessage


class HealthResponse(BaseModel):
    status: str


class AssetStateResponse(BaseModel):
    status: AssetStatus
    last_seen: datetime
    telemetry: TelemetryMessage


class TelemetryHistoryResponse(BaseModel):
    received_at: datetime
    telemetry: TelemetryMessage