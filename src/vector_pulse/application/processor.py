import asyncio

from vector_pulse.ingestion.schemas import TelemetryMessage


async def process_telemetry(
    queue: asyncio.Queue[TelemetryMessage],
) -> None:
    while True:
        telemetry = await queue.get()

        try:
            print(
                f"Processed tag={telemetry.tag_id} "
                f"sequence={telemetry.sequence_number} "
                f"x={telemetry.position.x:.2f} "
                f"y={telemetry.position.y:.2f} "
                f"battery={telemetry.condition.battery_percent:.1f}%"
            )
        finally:
            queue.task_done()