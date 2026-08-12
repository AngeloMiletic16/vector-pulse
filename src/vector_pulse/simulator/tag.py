from dataclasses import dataclass
from datetime import UTC, datetime
import random

from vector_pulse.ingestion.schemas import (
    Condition,
    Motion,
    Position,
    TelemetryMessage,
)


@dataclass
class SimulatedTag:
    tag_id: str
    x: float = 0.0
    y: float = 0.0
    sequence_number: int = 0

    def next_telemetry(self) -> TelemetryMessage:
        self.sequence_number += 1

        self.x += random.uniform(-0.5, 0.5)
        self.y += random.uniform(-0.5, 0.5)

        return TelemetryMessage(
            tag_id=self.tag_id,
            sequence_number=self.sequence_number,
            timestamp=datetime.now(UTC),
            position=Position(
                x=self.x,
                y=self.y,
                quality=random.uniform(0.85, 1.0),
            ),
            motion=Motion(
                speed_mps=random.uniform(0.0, 2.0),
            ),
            condition=Condition(
                temperature_c=random.uniform(20.0, 35.0),
                vibration_rms=random.uniform(0.0, 0.5),
                battery_percent=random.uniform(70.0, 100.0),
            ),
        )