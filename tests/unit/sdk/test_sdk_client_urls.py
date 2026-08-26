import pytest

from vector_pulse.sdk.client import (
    build_websocket_url,
)


def test_http_url_becomes_websocket_url() -> None:
    result = build_websocket_url(
        "http://127.0.0.1:8000"
    )

    assert (
        result
        == "ws://127.0.0.1:8000/ws/assets"
    )


def test_https_url_becomes_secure_websocket_url() -> None:
    result = build_websocket_url(
        "https://vectorpulse.example.com"
    )

    assert (
        result
        == (
            "wss://vectorpulse.example.com/"
            "ws/assets"
        )
    )


def test_invalid_base_url_is_rejected() -> None:
    with pytest.raises(
        ValueError
    ):
        build_websocket_url(
            "ftp://example.com"
        )