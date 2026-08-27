import asyncio
import json
from collections.abc import Coroutine
from dataclasses import dataclass
from typing import Any, TypeVar, cast

import typer
from rich.console import Console
from rich.table import Table

from vector_pulse.cli.ml import ml_app
from vector_pulse.sdk import (
    Alert,
    AlertType,
    AssetState,
    GeofenceConfiguration,
    LiveEvent,
    MonitoringRules,
    TelemetryHistoryItem,
    VectorPulseAPIError,
    VectorPulseClient,
    VectorPulseConnectionError,
)

T = TypeVar("T")

console = Console()

app = typer.Typer(
    name="vectorpulse",
    help=(
        "Operator CLI for the VectorPulse "
        "industrial monitoring platform."
    ),
    no_args_is_help=True,
)

assets_app = typer.Typer(
    help="Inspect tracked industrial assets.",
    no_args_is_help=True,
)

events_app = typer.Typer(
    help="Watch live VectorPulse events.",
    no_args_is_help=True,
)

app.add_typer(
    assets_app,
    name="assets",
)

app.add_typer(
    events_app,
    name="events",
)

app.add_typer(
    ml_app,
    name="ml",
)


@dataclass(frozen=True)
class CLISettings:
    base_url: str


@app.callback()
def configure(
    ctx: typer.Context,
    base_url: str = typer.Option(
        "http://127.0.0.1:8000",
        "--base-url",
        envvar="VECTORPULSE_URL",
        help="VectorPulse backend base URL.",
    ),
) -> None:
    ctx.obj = CLISettings(
        base_url=base_url,
    )


def _settings(
    ctx: typer.Context,
) -> CLISettings:
    return cast(
        CLISettings,
        ctx.obj,
    )


def _run[T](
    coroutine: Coroutine[Any, Any, T],
) -> T:
    try:
        return asyncio.run(coroutine)

    except (
        VectorPulseAPIError,
        VectorPulseConnectionError,
    ) as exc:
        console.print(
            f"[bold red]Error:[/bold red] {exc}"
        )

        raise typer.Exit(
            code=1
        ) from exc


def _print_json(
    payload: object,
) -> None:
    console.print_json(
        json=json.dumps(
            payload,
            indent=2,
            default=str,
        )
    )


async def _health(
    settings: CLISettings,
) -> str:
    async with VectorPulseClient(
        settings.base_url
    ) as client:
        health = await client.health()

    return health.status


@app.command("health")
def health_command(
    ctx: typer.Context,
) -> None:
    status = _run(
        _health(
            _settings(ctx)
        )
    )

    console.print(
        "[bold green]VectorPulse backend:"
        f"[/bold green] {status}"
    )


async def _list_assets(
    settings: CLISettings,
) -> list[AssetState]:
    async with VectorPulseClient(
        settings.base_url
    ) as client:
        return await client.list_assets()


@assets_app.command("list")
def list_assets_command(
    ctx: typer.Context,
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output machine-readable JSON.",
    ),
) -> None:
    asset_states = _run(
        _list_assets(
            _settings(ctx)
        )
    )

    if json_output:
        _print_json(
            [
                asset_state.model_dump(
                    mode="json"
                )
                for asset_state in asset_states
            ]
        )
        return

    asset_table = Table(
        title="VectorPulse Assets"
    )

    asset_table.add_column("Tag")
    asset_table.add_column("Status")
    asset_table.add_column("Zone")
    asset_table.add_column(
        "Sequence",
        justify="right",
    )
    asset_table.add_column(
        "Battery",
        justify="right",
    )
    asset_table.add_column("Last seen")

    for asset_state in asset_states:
        current_zone = (
            asset_state.current_zone.value
            if asset_state.current_zone is not None
            else "outside"
        )

        battery_percent = (
            asset_state
            .telemetry
            .condition
            .battery_percent
        )

        asset_table.add_row(
            asset_state.telemetry.tag_id,
            asset_state.status.value,
            current_zone,
            str(
                asset_state
                .telemetry
                .sequence_number
            ),
            f"{battery_percent:.1f}%",
            asset_state.last_seen.isoformat(),
        )

    console.print(asset_table)


async def _get_asset(
    settings: CLISettings,
    tag_id: str,
) -> AssetState:
    async with VectorPulseClient(
        settings.base_url
    ) as client:
        return await client.get_asset(
            tag_id
        )


@assets_app.command("show")
def show_asset_command(
    ctx: typer.Context,
    tag_id: str = typer.Argument(
        ...,
        help="Asset tag identifier.",
    ),
) -> None:
    asset_state = _run(
        _get_asset(
            _settings(ctx),
            tag_id,
        )
    )

    _print_json(
        asset_state.model_dump(
            mode="json"
        )
    )


async def _telemetry_history(
    settings: CLISettings,
    tag_id: str,
    limit: int,
) -> list[TelemetryHistoryItem]:
    async with VectorPulseClient(
        settings.base_url
    ) as client:
        return await client.telemetry_history(
            tag_id,
            limit=limit,
        )


@assets_app.command("telemetry")
def telemetry_command(
    ctx: typer.Context,
    tag_id: str = typer.Argument(
        ...,
        help="Asset tag identifier.",
    ),
    limit: int = typer.Option(
        10,
        "--limit",
        "-n",
        min=1,
        max=200,
    ),
) -> None:
    history_items = _run(
        _telemetry_history(
            _settings(ctx),
            tag_id,
            limit,
        )
    )

    telemetry_table = Table(
        title=f"Telemetry: {tag_id}"
    )

    telemetry_table.add_column(
        "Seq",
        justify="right",
    )
    telemetry_table.add_column("Device time")
    telemetry_table.add_column("Zone")
    telemetry_table.add_column(
        "X",
        justify="right",
    )
    telemetry_table.add_column(
        "Y",
        justify="right",
    )
    telemetry_table.add_column(
        "Battery",
        justify="right",
    )

    for history_item in history_items:
        resolved_zone = (
            history_item.resolved_zone.value
            if history_item.resolved_zone is not None
            else "outside"
        )

        telemetry = history_item.telemetry

        battery_percent = (
            telemetry.condition.battery_percent
        )

        telemetry_table.add_row(
            str(
                telemetry.sequence_number
            ),
            telemetry.timestamp.isoformat(),
            resolved_zone,
            f"{telemetry.position.x:.2f}",
            f"{telemetry.position.y:.2f}",
            f"{battery_percent:.1f}%",
        )

    console.print(telemetry_table)


async def _asset_alerts(
    settings: CLISettings,
    tag_id: str,
    limit: int,
) -> list[Alert]:
    async with VectorPulseClient(
        settings.base_url
    ) as client:
        return await client.asset_alerts(
            tag_id,
            limit=limit,
        )


@assets_app.command("alerts")
def asset_alerts_command(
    ctx: typer.Context,
    tag_id: str = typer.Argument(
        ...,
        help="Asset tag identifier.",
    ),
    limit: int = typer.Option(
        20,
        "--limit",
        "-n",
        min=1,
        max=200,
    ),
) -> None:
    asset_alerts = _run(
        _asset_alerts(
            _settings(ctx),
            tag_id,
            limit,
        )
    )

    _render_alert_table(
        asset_alerts,
        title=f"Alerts: {tag_id}",
    )


async def _zones(
    settings: CLISettings,
) -> GeofenceConfiguration:
    async with VectorPulseClient(
        settings.base_url
    ) as client:
        return await client.zones()


@app.command("zones")
def zones_command(
    ctx: typer.Context,
) -> None:
    configuration = _run(
        _zones(
            _settings(ctx)
        )
    )

    zone_table = Table(
        title="Factory Zones"
    )

    zone_table.add_column("Zone")
    zone_table.add_column("X range")
    zone_table.add_column("Y range")

    for configured_zone in configuration.zones:
        x_range = (
            f"[{configured_zone.min_x}, "
            f"{configured_zone.max_x})"
        )

        y_range = (
            f"[{configured_zone.min_y}, "
            f"{configured_zone.max_y})"
        )

        zone_table.add_row(
            configured_zone.name.value,
            x_range,
            y_range,
        )

    console.print(zone_table)

    console.print(
        "Minimum position quality: "
        f"{configuration.minimum_position_quality}"
    )

    console.print(
        "Boundary policy: "
        f"{configuration.boundary_policy}"
    )


async def _rules(
    settings: CLISettings,
) -> MonitoringRules:
    async with VectorPulseClient(
        settings.base_url
    ) as client:
        return await client.monitoring_rules()


@app.command("rules")
def rules_command(
    ctx: typer.Context,
) -> None:
    monitoring_rules = _run(
        _rules(
            _settings(ctx)
        )
    )

    dwell_table = Table(
        title="Dwell Policies"
    )

    dwell_table.add_column("Zone")
    dwell_table.add_column(
        "Threshold",
        justify="right",
    )
    dwell_table.add_column("Severity")

    for policy in monitoring_rules.dwell_policies:
        dwell_table.add_row(
            policy.zone.value,
            f"{policy.threshold_seconds:.1f}s",
            policy.severity.value,
        )

    console.print(dwell_table)

    movement_rules = monitoring_rules.movement

    movement_table = Table(
        title="Movement Rules"
    )

    movement_table.add_column("Rule")
    movement_table.add_column(
        "Value",
        justify="right",
    )

    movement_table.add_row(
        "Max reported speed",
        (
            f"{movement_rules.max_reported_speed_mps:.1f} "
            "m/s"
        ),
    )

    movement_table.add_row(
        "Max calculated speed",
        (
            f"{movement_rules.max_calculated_speed_mps:.1f} "
            "m/s"
        ),
    )

    movement_table.add_row(
        "Minimum time delta",
        (
            f"{movement_rules.minimum_time_delta_seconds:.2f}"
            "s"
        ),
    )

    console.print(movement_table)


async def _alerts(
    settings: CLISettings,
    limit: int,
) -> list[Alert]:
    async with VectorPulseClient(
        settings.base_url
    ) as client:
        return await client.list_alerts(
            limit=limit
        )


@app.command("alerts")
def alerts_command(
    ctx: typer.Context,
    limit: int = typer.Option(
        20,
        "--limit",
        "-n",
        min=1,
        max=200,
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output machine-readable JSON.",
    ),
) -> None:
    recent_alerts = _run(
        _alerts(
            _settings(ctx),
            limit,
        )
    )

    if json_output:
        _print_json(
            [
                alert.model_dump(
                    mode="json"
                )
                for alert in recent_alerts
            ]
        )
        return

    _render_alert_table(
        recent_alerts,
        title="Recent Alerts",
    )


def _render_alert_table(
    alerts: list[Alert],
    *,
    title: str,
) -> None:
    alert_table = Table(
        title=title
    )

    alert_table.add_column("Time")
    alert_table.add_column("Tag")
    alert_table.add_column("Type")
    alert_table.add_column("Severity")
    alert_table.add_column("Zone")
    alert_table.add_column("Message")

    for alert in alerts:
        alert_zone = (
            alert.zone.value
            if alert.zone is not None
            else "-"
        )

        alert_table.add_row(
            alert.occurred_at.isoformat(),
            alert.tag_id,
            alert.type.value,
            alert.severity.value,
            alert_zone,
            alert.message,
        )

    console.print(alert_table)


ALERT_EVENT_TYPES = {
    alert_type.value
    for alert_type in AlertType
}


def _render_live_event(
    event: LiveEvent,
) -> None:
    if event.type == "connected":
        console.print(
            "[bold green]"
            "Connected to live VectorPulse event stream"
            "[/bold green]"
        )
        return

    event_tag_id = event.tag_id or "-"

    if event.zone is not None:
        event_zone = event.zone.value
    elif event.current_zone is not None:
        event_zone = event.current_zone.value
    else:
        event_zone = "-"

    event_severity = (
        event.severity.value
        if event.severity is not None
        else "-"
    )

    event_time = (
        event.occurred_at.isoformat()
        if event.occurred_at is not None
        else "-"
    )

    console.print(
        f"{event_time} "
        f"[bold]{event.type}[/bold] "
        f"tag={event_tag_id} "
        f"zone={event_zone} "
        f"severity={event_severity}"
    )

    if event.message:
        console.print(
            f"  {event.message}"
        )


async def _watch_events(
    settings: CLISettings,
    *,
    event_type: str | None,
    alerts_only: bool,
) -> None:
    async with VectorPulseClient(
        settings.base_url
    ) as client:
        async for event in client.watch_events():
            if (
                alerts_only
                and event.type not in ALERT_EVENT_TYPES
            ):
                continue

            if (
                event_type is not None
                and event.type != event_type
            ):
                continue

            _render_live_event(event)


@events_app.command("watch")
def watch_events_command(
    ctx: typer.Context,
    event_type: str | None = typer.Option(
        None,
        "--event-type",
        "-e",
        help=(
            "Show only one event type, for "
            "example impossible_movement."
        ),
    ),
    alerts_only: bool = typer.Option(
        False,
        "--alerts-only",
        help="Show only monitoring alerts.",
    ),
) -> None:
    console.print(
        "[dim]Press Ctrl+C to stop.[/dim]"
    )

    try:
        _run(
            _watch_events(
                _settings(ctx),
                event_type=event_type,
                alerts_only=alerts_only,
            )
        )

    except KeyboardInterrupt:
        console.print(
            "\n[dim]Event watch stopped.[/dim]"
        )


def main() -> None:
    app()


if __name__ == "__main__":
    main()