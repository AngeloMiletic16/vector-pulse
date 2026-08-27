import asyncio
import json
from collections.abc import Coroutine
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from vector_pulse.sdk import (
    AnomalyModelStatus,
    VectorPulseAPIError,
    VectorPulseClient,
    VectorPulseConnectionError,
)

console = Console()

ml_app = typer.Typer(
    help=(
        "Train and inspect the VectorPulse "
        "ML anomaly detector."
    ),
    no_args_is_help=True,
)


def _base_url(
    ctx: typer.Context,
) -> str:
    root_context = ctx.find_root()

    settings = root_context.obj

    base_url = getattr(
        settings,
        "base_url",
        None,
    )

    if not isinstance(
            base_url,
            str,
    ):
        raise TypeError(
            "CLI base URL is not configured"
        )

    return base_url


def _run[T](
    coroutine: Coroutine[Any, Any, T],
) -> T:
    try:
        return asyncio.run(
            coroutine
        )

    except (
        VectorPulseAPIError,
        VectorPulseConnectionError,
    ) as exc:
        console.print(
            "[bold red]Error:[/bold red] "
            f"{exc}"
        )

        raise typer.Exit(
            code=1
        ) from exc


def _print_json(
    status: AnomalyModelStatus,
) -> None:
    console.print_json(
        json=json.dumps(
            status.model_dump(
                mode="json"
            ),
            indent=2,
            default=str,
        )
    )


async def _status(
    base_url: str,
) -> AnomalyModelStatus:
    async with VectorPulseClient(
        base_url
    ) as client:
        return (
            await client.anomaly_status()
        )


async def _train(
    base_url: str,
    *,
    limit: int,
    nu: float,
) -> AnomalyModelStatus:
    async with VectorPulseClient(
        base_url
    ) as client:
        return (
            await client.train_anomaly_model(
                limit=limit,
                nu=nu,
            )
        )


def _render_status(
    status: AnomalyModelStatus,
) -> None:
    table = Table(
        title="ML Anomaly Detector"
    )

    table.add_column("Property")
    table.add_column("Value")

    table.add_row(
        "Ready",
        "yes" if status.ready else "no",
    )

    table.add_row(
        "Training",
        "yes" if status.training else "no",
    )

    table.add_row(
        "Samples",
        (
            str(status.sample_count)
            if status.sample_count is not None
            else "-"
        ),
    )

    table.add_row(
        "nu",
        (
            f"{status.nu:.4f}"
            if status.nu is not None
            else "-"
        ),
    )

    table.add_row(
        "Trained at",
        (
            status.trained_at.isoformat()
            if status.trained_at is not None
            else "-"
        ),
    )

    table.add_row(
        "Model path",
        status.model_path,
    )

    features = (
        ", ".join(
            status.feature_names
        )
        if status.feature_names
        else "-"
    )

    table.add_row(
        "Features",
        features,
    )

    console.print(
        table
    )


@ml_app.command("status")
def status_command(
    ctx: typer.Context,
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output machine-readable JSON.",
    ),
) -> None:
    status = _run(
        _status(
            _base_url(ctx)
        )
    )

    if json_output:
        _print_json(
            status
        )

        return

    _render_status(
        status
    )


@ml_app.command("train")
def train_command(
    ctx: typer.Context,
    limit: int = typer.Option(
        2000,
        "--limit",
        min=100,
        max=10_000,
        help=(
            "Maximum number of recent "
            "telemetry samples to train on."
        ),
    ),
    nu: float = typer.Option(
        0.03,
        "--nu",
        min=0.001,
        max=0.25,
        help=(
            "One-Class SVM nu parameter."
        ),
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output machine-readable JSON.",
    ),
) -> None:
    console.print(
        "[dim]Training anomaly model...[/dim]"
    )

    status = _run(
        _train(
            _base_url(ctx),
            limit=limit,
            nu=nu,
        )
    )

    if json_output:
        _print_json(
            status
        )

        return

    console.print(
        "[bold green]"
        "Anomaly model trained successfully."
        "[/bold green]"
    )

    _render_status(
        status
    )