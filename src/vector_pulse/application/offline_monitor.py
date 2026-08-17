import asyncio
from datetime import UTC, datetime, timedelta

from vector_pulse.application.asset_registry import (
    AssetRegistry,
    AssetState,
)
from vector_pulse.persistence.sqlite_storage import (
    SQLiteStorage,
)


OFFLINE_AFTER_SECONDS = 15.0
OFFLINE_CHECK_INTERVAL_SECONDS = 2.0


async def check_offline_assets(
    registry: AssetRegistry,
    storage: SQLiteStorage,
    *,
    now: datetime | None = None,
    offline_after_seconds: float = OFFLINE_AFTER_SECONDS,
) -> list[AssetState]:
    if now is None:
        now = datetime.now(UTC)

    newly_offline = registry.mark_offline(
        now=now,
        offline_after=timedelta(
            seconds=offline_after_seconds
        ),
    )

    for state in newly_offline:
        await storage.update_asset_status(state)

        print(
            f"Asset offline "
            f"tag={state.telemetry.tag_id} "
            f"last_seen={state.last_seen.isoformat()}"
        )

    return newly_offline


async def monitor_offline_assets(
    registry: AssetRegistry,
    storage: SQLiteStorage,
    *,
    check_interval_seconds: float = (
        OFFLINE_CHECK_INTERVAL_SECONDS
    ),
    offline_after_seconds: float = (
        OFFLINE_AFTER_SECONDS
    ),
) -> None:
    while True:
        await asyncio.sleep(check_interval_seconds)

        await check_offline_assets(
            registry,
            storage,
            offline_after_seconds=offline_after_seconds,
        )