from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class Position(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float
    y: float
    quality: float = Field(ge=0.0, le=1.0)


class Motion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    speed_mps: float = Field(ge=0.0)


class Condition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    temperature_c: float
    vibration_rms: float = Field(ge=0.0)
    battery_percent: float = Field(ge=0.0, le=100.0)


class TelemetryMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tag_id: str = Field(min_length=1)
    sequence_number: int = Field(ge=0)
    timestamp: datetime
    position: Position
    motion: Motion
    condition: Condition