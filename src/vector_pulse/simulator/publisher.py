import asyncio

import aiomqtt

from vector_pulse.simulator.tag import SimulatedTag


MQTT_HOST = "localhost"
MQTT_PORT = 1883
PUBLISH_INTERVAL_SECONDS = 1.0
TAG_COUNT = 5

async def run_tag(tag: SimulatedTag) -> None:
    async with aiomqtt.Client(
        hostname=MQTT_HOST,
        port=MQTT_PORT,
    ) as client:
        while True:
            telemetry = tag.next_telemetry()

            topic = f"vectorpulse/assets/{tag.tag_id}/telemetry"
            payload = telemetry.model_dump_json()

            await client.publish(topic, payload=payload)

            print(
                f"Published tag={tag.tag_id} "
                f"sequence={telemetry.sequence_number} "
                f"x={telemetry.position.x:.2f} "
                f"y={telemetry.position.y:.2f}"
            )

            await asyncio.sleep(PUBLISH_INTERVAL_SECONDS)

def create_tags(count: int) -> list[SimulatedTag]:
    if count < 1:
        raise ValueError("Tag count must be at least 1")

    return [
        SimulatedTag(tag_id=f"tag-{index:03d}")
        for index in range(1, count + 1)
    ]

async def main() -> None:
    tags = create_tags(TAG_COUNT)

    async with asyncio.TaskGroup() as task_group:
        for tag in tags:
            task_group.create_task(
                run_tag(tag),
                name=f"simulator-{tag.tag_id}",
            )


if __name__ == "__main__":
    asyncio.run(main())