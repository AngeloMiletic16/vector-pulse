import asyncio

import aiomqtt
from pydantic import ValidationError

from vector_pulse.ingestion.schemas import (
    TelemetryMessage,
)

TELEMETRY_TOPIC = (
    "vectorpulse/assets/+/telemetry"
)

RECONNECT_DELAY_SECONDS = 2.0


def parse_telemetry_payload(
    payload: bytes,
) -> TelemetryMessage:
    return (
        TelemetryMessage.model_validate_json(
            payload
        )
    )


async def consume_telemetry(
    queue: asyncio.Queue[TelemetryMessage],
    *,
    mqtt_host: str = "localhost",
    mqtt_port: int = 1883,
) -> None:
    while True:
        try:
            async with aiomqtt.Client(
                hostname=mqtt_host,
                port=mqtt_port,
            ) as client:
                await client.subscribe(
                    TELEMETRY_TOPIC
                )

                print(
                    "MQTT consumer connected to "
                    f"{mqtt_host}:{mqtt_port} "
                    f"topic={TELEMETRY_TOPIC}"
                )

                async for message in client.messages:
                    try:
                        telemetry = (
                            parse_telemetry_payload(
                                message.payload
                            )
                        )

                    except ValidationError as exc:
                        print(
                            "Dropped invalid telemetry "
                            f"topic={message.topic}: "
                            f"{exc}"
                        )
                        continue

                    await queue.put(
                        telemetry
                    )

        except aiomqtt.MqttError as exc:
            print(
                "MQTT connection lost: "
                f"{exc}. Retrying in "
                f"{RECONNECT_DELAY_SECONDS}s..."
            )

            await asyncio.sleep(
                RECONNECT_DELAY_SECONDS
            )