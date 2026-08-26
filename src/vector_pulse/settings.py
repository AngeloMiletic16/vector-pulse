import os
from dataclasses import dataclass
from pathlib import Path


def _read_int(
    environment_variable: str,
    default: int,
) -> int:
    raw_value = os.getenv(
        environment_variable
    )

    if raw_value is None:
        return default

    try:
        return int(raw_value)

    except ValueError as exc:
        raise ValueError(
            f"{environment_variable} "
            "must be an integer"
        ) from exc


@dataclass(frozen=True)
class VectorPulseSettings:
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883

    database_path: Path = Path(
        "data/vectorpulse.db"
    )

    api_host: str = "127.0.0.1"
    api_port: int = 8000

    telemetry_queue_max_size: int = 1000

    def __post_init__(self) -> None:
        if not self.mqtt_host.strip():
            raise ValueError(
                "MQTT host cannot be empty"
            )

        if not 1 <= self.mqtt_port <= 65535:
            raise ValueError(
                "MQTT port must be between "
                "1 and 65535"
            )

        if not self.api_host.strip():
            raise ValueError(
                "API host cannot be empty"
            )

        if not 1 <= self.api_port <= 65535:
            raise ValueError(
                "API port must be between "
                "1 and 65535"
            )

        if self.telemetry_queue_max_size < 1:
            raise ValueError(
                "Telemetry queue max size "
                "must be at least 1"
            )

    @classmethod
    def from_env(
        cls,
    ) -> "VectorPulseSettings":
        database_path = os.getenv(
            "VECTORPULSE_DATABASE_PATH",
            "data/vectorpulse.db",
        )

        return cls(
            mqtt_host=os.getenv(
                "VECTORPULSE_MQTT_HOST",
                "localhost",
            ),
            mqtt_port=_read_int(
                "VECTORPULSE_MQTT_PORT",
                1883,
            ),
            database_path=Path(
                database_path
            ),
            api_host=os.getenv(
                "VECTORPULSE_API_HOST",
                "127.0.0.1",
            ),
            api_port=_read_int(
                "VECTORPULSE_API_PORT",
                8000,
            ),
            telemetry_queue_max_size=(
                _read_int(
                    (
                        "VECTORPULSE_"
                        "TELEMETRY_QUEUE_MAX_SIZE"
                    ),
                    1000,
                )
            ),
        )