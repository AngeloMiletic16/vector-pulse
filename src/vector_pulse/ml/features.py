from dataclasses import dataclass

from vector_pulse.ingestion.schemas import (
    TelemetryMessage,
)

FEATURE_NAMES = (
    "temperature_c",
    "vibration_rms",
    "speed_mps",
    "battery_percent",
    "position_quality",
)


@dataclass(frozen=True)
class TelemetryFeatures:
    temperature_c: float
    vibration_rms: float
    speed_mps: float
    battery_percent: float
    position_quality: float

    @classmethod
    def from_telemetry(
        cls,
        telemetry: TelemetryMessage,
    ) -> "TelemetryFeatures":
        return cls(
            temperature_c=(
                telemetry.condition.temperature_c
            ),
            vibration_rms=(
                telemetry.condition.vibration_rms
            ),
            speed_mps=(
                telemetry.motion.speed_mps
            ),
            battery_percent=(
                telemetry.condition.battery_percent
            ),
            position_quality=(
                telemetry.position.quality
            ),
        )

    def as_vector(
        self,
    ) -> list[float]:
        return [
            self.temperature_c,
            self.vibration_rms,
            self.speed_mps,
            self.battery_percent,
            self.position_quality,
        ]

    def as_dict(
        self,
    ) -> dict[str, float]:
        return {
            "temperature_c": self.temperature_c,
            "vibration_rms": self.vibration_rms,
            "speed_mps": self.speed_mps,
            "battery_percent": (
                self.battery_percent
            ),
            "position_quality": (
                self.position_quality
            ),
        }