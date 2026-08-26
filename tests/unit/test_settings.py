from pathlib import Path

import pytest

from vector_pulse.settings import (
    VectorPulseSettings,
)

ENVIRONMENT_VARIABLES = (
    "VECTORPULSE_MQTT_HOST",
    "VECTORPULSE_MQTT_PORT",
    "VECTORPULSE_DATABASE_PATH",
    "VECTORPULSE_API_HOST",
    "VECTORPULSE_API_PORT",
    (
        "VECTORPULSE_"
        "TELEMETRY_QUEUE_MAX_SIZE"
    ),
)


def clear_vectorpulse_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for variable in ENVIRONMENT_VARIABLES:
        monkeypatch.delenv(
            variable,
            raising=False,
        )


def test_settings_use_local_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_vectorpulse_environment(
        monkeypatch
    )

    settings = (
        VectorPulseSettings.from_env()
    )

    assert settings.mqtt_host == "localhost"
    assert settings.mqtt_port == 1883

    assert settings.database_path == Path(
        "data/vectorpulse.db"
    )

    assert settings.api_host == "127.0.0.1"
    assert settings.api_port == 8000

    assert (
        settings.telemetry_queue_max_size
        == 1000
    )


def test_settings_read_environment_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_vectorpulse_environment(
        monkeypatch
    )

    monkeypatch.setenv(
        "VECTORPULSE_MQTT_HOST",
        "mosquitto",
    )

    monkeypatch.setenv(
        "VECTORPULSE_MQTT_PORT",
        "1884",
    )

    monkeypatch.setenv(
        "VECTORPULSE_DATABASE_PATH",
        "/app/data/vectorpulse.db",
    )

    monkeypatch.setenv(
        "VECTORPULSE_API_HOST",
        "0.0.0.0",
    )

    monkeypatch.setenv(
        "VECTORPULSE_API_PORT",
        "9000",
    )

    monkeypatch.setenv(
        (
            "VECTORPULSE_"
            "TELEMETRY_QUEUE_MAX_SIZE"
        ),
        "250",
    )

    settings = (
        VectorPulseSettings.from_env()
    )

    assert settings.mqtt_host == "mosquitto"
    assert settings.mqtt_port == 1884

    assert settings.database_path == Path(
        "/app/data/vectorpulse.db"
    )

    assert settings.api_host == "0.0.0.0"
    assert settings.api_port == 9000

    assert (
        settings.telemetry_queue_max_size
        == 250
    )


def test_non_integer_environment_value_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_vectorpulse_environment(
        monkeypatch
    )

    monkeypatch.setenv(
        "VECTORPULSE_MQTT_PORT",
        "banana",
    )

    with pytest.raises(
        ValueError,
        match=(
            "VECTORPULSE_MQTT_PORT "
            "must be an integer"
        ),
    ):
        VectorPulseSettings.from_env()


def test_invalid_port_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_vectorpulse_environment(
        monkeypatch
    )

    monkeypatch.setenv(
        "VECTORPULSE_API_PORT",
        "70000",
    )

    with pytest.raises(
        ValueError,
        match="API port",
    ):
        VectorPulseSettings.from_env()


def test_invalid_queue_size_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_vectorpulse_environment(
        monkeypatch
    )

    monkeypatch.setenv(
        (
            "VECTORPULSE_"
            "TELEMETRY_QUEUE_MAX_SIZE"
        ),
        "0",
    )

    with pytest.raises(
        ValueError,
        match="Telemetry queue",
    ):
        VectorPulseSettings.from_env()