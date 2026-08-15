import asyncio

from vector_pulse.ingestion.schemas import TelemetryMessage
from vector_pulse.application.asset_registry import (
    AssetRegistry,
    UpdateStatus,
)

async def process_telemetry(
    queue: asyncio.Queue[TelemetryMessage],
    registry: AssetRegistry,
) -> None:
    while True:
        telemetry = await queue.get()

        try:
            result = registry.update(telemetry)

            if result.status is UpdateStatus.DUPLICATE:
                print(
                    f"Dropped duplicate "
                    f"tag={telemetry.tag_id} "
                    f"sequence={telemetry.sequence_number}"
                )
                continue

            if result.status is UpdateStatus.OUT_OF_ORDER:
                print(
                    f"Dropped out-of-order telemetry "
                    f"tag={telemetry.tag_id} "
                    f"sequence={telemetry.sequence_number}"
                )
                continue

            if result.status is UpdateStatus.GAP_DETECTED:
                print(
                    f"Sequence gap detected "
                    f"tag={telemetry.tag_id} "
                    f"missing={result.missing_messages}"
                )

            print(
                f"Processed tag={telemetry.tag_id} "
                f"sequence={telemetry.sequence_number} "
                f"x={telemetry.position.x:.2f} "
                f"y={telemetry.position.y:.2f} "
                f"battery={telemetry.condition.battery_percent:.1f}%"
            )

        finally:
            queue.task_done()