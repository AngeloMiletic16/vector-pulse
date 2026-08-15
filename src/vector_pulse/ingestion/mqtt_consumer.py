import asyncio

import aiomqtt
from pydantic import ValidationError

from vector_pulse.ingestion.schemas import TelemetryMessage


MQTT_HOST = "localhost"
MQTT_PORT = 1883
TELEMETRY_TOPIC = "vectorpulse/assets/+/telemetry"
RECONNECT_DELAY_SECONDS = 2.0


def parse_telemetry_payload(payload: bytes) -> TelemetryMessage:
    return TelemetryMessage.model_validate_json(payload)


async def consume_telemetry(
    queue: asyncio.Queue[TelemetryMessage],
) -> None:
    while True:
        try:
            async with aiomqtt.Client(
                hostname=MQTT_HOST,
                port=MQTT_PORT,
            ) as client:
                await client.subscribe(TELEMETRY_TOPIC)

                print(
                    f"MQTT consumer connected to "
                    f"{MQTT_HOST}:{MQTT_PORT}"
                )

                async for message in client.messages:
                    try:
                        telemetry = parse_telemetry_payload(
                            message.payload
                        )
                    except ValidationError as exc:
                        print(
                            f"Dropped invalid telemetry "
                            f"topic={message.topic.value} "
                            f"error={exc.errors()[0]['msg']}"
                        )
                        continue

                    await queue.put(telemetry)

        except aiomqtt.MqttError as exc:
            print(
                f"MQTT connection lost: {exc}. "
                f"Retrying in {RECONNECT_DELAY_SECONDS}s..."
            )

            await asyncio.sleep(RECONNECT_DELAY_SECONDS)