from collections.abc import AsyncIterator
from typing import Self
from urllib.parse import urlsplit, urlunsplit

import httpx
import websockets
from pydantic import TypeAdapter
from websockets.exceptions import WebSocketException

from vector_pulse.sdk.exceptions import (
    VectorPulseAPIError,
    VectorPulseConnectionError,
)
from vector_pulse.sdk.models import (
    Alert,
    AnomalyModelStatus,
    AssetState,
    GeofenceConfiguration,
    HealthStatus,
    LiveEvent,
    MonitoringRules,
    TelemetryHistoryItem,
    ZoneTransition,
)


def build_websocket_url(
    base_url: str,
    path: str = "/ws/assets",
) -> str:
    parsed = urlsplit(
        base_url.rstrip("/")
    )

    if parsed.scheme == "http":
        websocket_scheme = "ws"

    elif parsed.scheme == "https":
        websocket_scheme = "wss"

    else:
        raise ValueError(
            "Base URL must use http or https"
        )

    base_path = parsed.path.rstrip("/")

    websocket_path = (
        f"{base_path}/{path.lstrip('/')}"
    )

    return urlunsplit(
        (
            websocket_scheme,
            parsed.netloc,
            websocket_path,
            "",
            "",
        )
    )


class VectorPulseClient:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000",
        *,
        timeout: float = 10.0,
        transport: (
            httpx.AsyncBaseTransport | None
        ) = None,
    ) -> None:
        self._base_url = (
            base_url.rstrip("/")
        )

        self._timeout = timeout

        self._http = httpx.AsyncClient(
            base_url=f"{self._base_url}/",
            timeout=timeout,
            transport=transport,
        )

    @property
    def base_url(self) -> str:
        return self._base_url

    async def __aenter__(
        self,
    ) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: object,
        exc_value: object,
        traceback: object,
    ) -> None:
        await self.close()

    async def close(self) -> None:
        await self._http.aclose()

    async def health(
        self,
    ) -> HealthStatus:
        payload = await self._get_json(
            "health"
        )

        return HealthStatus.model_validate(
            payload
        )

    async def anomaly_status(
        self,
    ) -> AnomalyModelStatus:
        payload = await self._get_json(
            "ml/anomaly/status"
        )

        return (
            AnomalyModelStatus.model_validate(
                payload
            )
        )

    async def train_anomaly_model(
        self,
        *,
        limit: int = 2000,
        nu: float = 0.03,
    ) -> AnomalyModelStatus:
        self._validate_training_parameters(
            limit=limit,
            nu=nu,
        )

        payload = await self._post_json(
            "ml/anomaly/train",
            json_payload={
                "limit": limit,
                "nu": nu,
            },
        )

        return (
            AnomalyModelStatus.model_validate(
                payload
            )
        )

    async def list_assets(
        self,
    ) -> list[AssetState]:
        payload = await self._get_json(
            "assets"
        )

        return TypeAdapter(
            list[AssetState]
        ).validate_python(payload)

    async def get_asset(
        self,
        tag_id: str,
    ) -> AssetState:
        payload = await self._get_json(
            f"assets/{tag_id}"
        )

        return AssetState.model_validate(
            payload
        )

    async def telemetry_history(
        self,
        tag_id: str,
        *,
        limit: int = 20,
    ) -> list[TelemetryHistoryItem]:
        self._validate_limit(limit)

        payload = await self._get_json(
            f"assets/{tag_id}/telemetry",
            params={
                "limit": limit,
            },
        )

        return TypeAdapter(
            list[TelemetryHistoryItem]
        ).validate_python(payload)

    async def zone_transitions(
        self,
        tag_id: str,
        *,
        limit: int = 20,
    ) -> list[ZoneTransition]:
        self._validate_limit(limit)

        payload = await self._get_json(
            f"assets/{tag_id}/zone-transitions",
            params={
                "limit": limit,
            },
        )

        return TypeAdapter(
            list[ZoneTransition]
        ).validate_python(payload)

    async def zones(
        self,
    ) -> GeofenceConfiguration:
        payload = await self._get_json(
            "zones"
        )

        return (
            GeofenceConfiguration.model_validate(
                payload
            )
        )

    async def monitoring_rules(
        self,
    ) -> MonitoringRules:
        payload = await self._get_json(
            "monitoring-rules"
        )

        return MonitoringRules.model_validate(
            payload
        )

    async def list_alerts(
        self,
        *,
        limit: int = 50,
    ) -> list[Alert]:
        self._validate_limit(limit)

        payload = await self._get_json(
            "alerts",
            params={
                "limit": limit,
            },
        )

        return TypeAdapter(
            list[Alert]
        ).validate_python(payload)

    async def asset_alerts(
        self,
        tag_id: str,
        *,
        limit: int = 50,
    ) -> list[Alert]:
        self._validate_limit(limit)

        payload = await self._get_json(
            f"assets/{tag_id}/alerts",
            params={
                "limit": limit,
            },
        )

        return TypeAdapter(
            list[Alert]
        ).validate_python(payload)

    async def watch_events(
        self,
    ) -> AsyncIterator[LiveEvent]:
        websocket_url = build_websocket_url(
            self._base_url
        )

        try:
            async with websockets.connect(
                websocket_url,
                open_timeout=self._timeout,
            ) as websocket:
                async for raw_message in websocket:
                    if isinstance(
                        raw_message,
                        bytes,
                    ):
                        raw_message = (
                            raw_message.decode(
                                "utf-8"
                            )
                        )

                    yield (
                        LiveEvent.model_validate_json(
                            raw_message
                        )
                    )

        except (
            OSError,
            WebSocketException,
        ) as exc:
            raise VectorPulseConnectionError(
                "WebSocket connection to "
                f"{websocket_url} failed: {exc}"
            ) from exc

    async def _get_json(
        self,
        path: str,
        *,
        params: (
            dict[str, object] | None
        ) = None,
    ) -> object:
        try:
            response = await self._http.get(
                path.lstrip("/"),
                params=params,
            )

        except httpx.RequestError as exc:
            raise VectorPulseConnectionError(
                "Could not connect to "
                f"{self._base_url}: {exc}"
            ) from exc

        return self._response_json(
            response
        )

    async def _post_json(
        self,
        path: str,
        *,
        json_payload: dict[str, object],
    ) -> object:
        try:
            response = await self._http.post(
                path.lstrip("/"),
                json=json_payload,
            )

        except httpx.RequestError as exc:
            raise VectorPulseConnectionError(
                "Could not connect to "
                f"{self._base_url}: {exc}"
            ) from exc

        return self._response_json(
            response
        )

    def _response_json(
        self,
        response: httpx.Response,
    ) -> object:
        if response.is_error:
            detail = self._extract_error_detail(
                response
            )

            raise VectorPulseAPIError(
                status_code=response.status_code,
                detail=detail,
            )

        return response.json()

    @staticmethod
    def _extract_error_detail(
        response: httpx.Response,
    ) -> str:
        try:
            payload = response.json()

        except ValueError:
            return (
                response.text
                or "Unknown API error"
            )

        if isinstance(
            payload,
            dict,
        ):
            detail = payload.get(
                "detail"
            )

            if detail is not None:
                return str(detail)

        return (
            response.text
            or "Unknown API error"
        )

    @staticmethod
    def _validate_limit(
        limit: int,
    ) -> None:
        if not 1 <= limit <= 200:
            raise ValueError(
                "limit must be between 1 and 200"
            )

    @staticmethod
    def _validate_training_parameters(
        *,
        limit: int,
        nu: float,
    ) -> None:
        if not 100 <= limit <= 10_000:
            raise ValueError(
                "training limit must be "
                "between 100 and 10000"
            )

        if not 0.001 <= nu <= 0.25:
            raise ValueError(
                "nu must be between "
                "0.001 and 0.25"
            )