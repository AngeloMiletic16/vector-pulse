import asyncio

from vector_pulse.application.processor import process_telemetry
from vector_pulse.ingestion.mqtt_consumer import consume_telemetry
from vector_pulse.ingestion.schemas import TelemetryMessage


TELEMETRY_QUEUE_MAX_SIZE = 1000


async def main() -> None:
    telemetry_queue: asyncio.Queue[TelemetryMessage] = asyncio.Queue(
        maxsize=TELEMETRY_QUEUE_MAX_SIZE
    )

    async with asyncio.TaskGroup() as task_group:
        task_group.create_task(
            consume_telemetry(telemetry_queue),
            name="mqtt-consumer",
        )

        task_group.create_task(
            process_telemetry(telemetry_queue),
            name="telemetry-processor",
        )


if __name__ == "__main__":
    asyncio.run(main())