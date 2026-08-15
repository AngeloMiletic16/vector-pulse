from dataclasses import dataclass
from enum import Enum

from vector_pulse.ingestion.schemas import TelemetryMessage


class UpdateStatus(str, Enum):
    ACCEPTED = "accepted"
    GAP_DETECTED = "gap_detected"
    DUPLICATE = "duplicate"
    OUT_OF_ORDER = "out_of_order"


@dataclass(frozen=True)
class UpdateResult:
    status: UpdateStatus
    missing_messages: int = 0


class AssetRegistry:
    def __init__(self) -> None:
        self._latest: dict[str, TelemetryMessage] = {}

    def update(self, telemetry: TelemetryMessage) -> UpdateResult:
        previous = self._latest.get(telemetry.tag_id)

        if previous is None:
            self._latest[telemetry.tag_id] = telemetry
            return UpdateResult(UpdateStatus.ACCEPTED)

        if telemetry.sequence_number == previous.sequence_number:
            return UpdateResult(UpdateStatus.DUPLICATE)

        if telemetry.sequence_number < previous.sequence_number:
            return UpdateResult(UpdateStatus.OUT_OF_ORDER)

        expected_sequence = previous.sequence_number + 1

        if telemetry.sequence_number > expected_sequence:
            missing_messages = (
                telemetry.sequence_number - expected_sequence
            )

            self._latest[telemetry.tag_id] = telemetry

            return UpdateResult(
                status=UpdateStatus.GAP_DETECTED,
                missing_messages=missing_messages,
            )

        self._latest[telemetry.tag_id] = telemetry
        return UpdateResult(UpdateStatus.ACCEPTED)

    def get_latest(self, tag_id: str) -> TelemetryMessage | None:
        return self._latest.get(tag_id)

    def asset_count(self) -> int:
        return len(self._latest)