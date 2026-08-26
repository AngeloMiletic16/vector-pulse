import asyncio

import aiomqtt

from vector_pulse.settings import (
    VectorPulseSettings,
)
from vector_pulse.simulator.tag import (
    SimulatedTag,
)

TAG_COUNT = 5
PUBLISH_INTERVAL_SECONDS = 1.0


def create_tags(
    count: int,
) -> list[SimulatedTag]:
    if count < 1:
        raise ValueError(
            "Tag count must be at least 1"
        )

    return [
        SimulatedTag(
            tag_id=f"tag-{index:03d}"
        )
        for index in range(
            1,
            count + 1,
        )
    ]


async def run_tag(
    tag: SimulatedTag,
    *,
    mqtt_host: str,
    mqtt_port: int,
) -> None:
    async with aiomqtt.Client(
        hostname=mqtt_host,
        port=mqtt_port,
    ) as client:
        while True:
            telemetry = tag.next_telemetry()

            topic = (
                "vectorpulse/assets/"
                f"{tag.tag_id}/telemetry"
            )

            await client.publish(
                topic,
                telemetry.model_dump_json(),
            )

            print(
                f"Published tag={tag.tag_id} "
                f"sequence="
                f"{telemetry.sequence_number} "
                f"mqtt="
                f"{mqtt_host}:{mqtt_port}"
            )

            await asyncio.sleep(
                PUBLISH_INTERVAL_SECONDS
            )


async def main() -> None:
    settings = (
        VectorPulseSettings.from_env()
    )

    tags = create_tags(
        TAG_COUNT
    )

    print(
        f"Starting {len(tags)} simulated "
        "VectorPulse tags"
    )

    async with asyncio.TaskGroup() as task_group:
        for tag in tags:
            task_group.create_task(
                run_tag(
                    tag,
                    mqtt_host=(
                        settings.mqtt_host
                    ),
                    mqtt_port=(
                        settings.mqtt_port
                    ),
                ),
                name=(
                    f"simulator-{tag.tag_id}"
                ),
            )


if __name__ == "__main__":
    asyncio.run(
        main()
    )