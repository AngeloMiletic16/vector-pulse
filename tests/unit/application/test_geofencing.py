import pytest

from vector_pulse.application.geofencing import (
    GeofenceService,
    Zone,
    ZoneName,
    create_default_geofence,
)
from vector_pulse.ingestion.schemas import Position


def position(
    x: float,
    y: float,
    quality: float = 0.95,
) -> Position:
    return Position(
        x=x,
        y=y,
        quality=quality,
    )


def test_position_resolves_to_receiving() -> None:
    geofence = create_default_geofence()

    zone = geofence.resolve_zone(
        position(
            x=5.0,
            y=5.0,
        )
    )

    assert zone is ZoneName.RECEIVING


def test_shared_boundary_resolves_to_next_zone() -> None:
    geofence = create_default_geofence()

    zone = geofence.resolve_zone(
        position(
            x=10.0,
            y=5.0,
        )
    )

    assert zone is ZoneName.STORAGE


def test_position_outside_factory_has_no_zone() -> None:
    geofence = create_default_geofence()

    zone = geofence.resolve_zone(
        position(
            x=70.0,
            y=5.0,
        )
    )

    assert zone is None


def test_low_quality_position_does_not_change_zone() -> None:
    geofence = create_default_geofence()

    transition = geofence.evaluate(
        previous_zone=ZoneName.RECEIVING,
        position=position(
            x=15.0,
            y=5.0,
            quality=0.2,
        ),
    )

    assert transition.position_accepted is False
    assert transition.changed is False
    assert (
        transition.current_zone
        is ZoneName.RECEIVING
    )


def test_transition_between_zones_is_detected() -> None:
    geofence = create_default_geofence()

    transition = geofence.evaluate(
        previous_zone=ZoneName.RECEIVING,
        position=position(
            x=15.0,
            y=5.0,
        ),
    )

    assert transition.changed is True
    assert (
        transition.exited_zone
        is ZoneName.RECEIVING
    )
    assert (
        transition.entered_zone
        is ZoneName.STORAGE
    )


def test_leaving_factory_is_detected() -> None:
    geofence = create_default_geofence()

    transition = geofence.evaluate(
        previous_zone=ZoneName.SHIPPING,
        position=position(
            x=60.0,
            y=5.0,
        ),
    )

    assert transition.changed is True
    assert (
        transition.exited_zone
        is ZoneName.SHIPPING
    )
    assert transition.entered_zone is None


def test_overlapping_zones_are_rejected() -> None:
    first = Zone(
        name=ZoneName.RECEIVING,
        min_x=0.0,
        max_x=10.0,
        min_y=0.0,
        max_y=10.0,
    )

    second = Zone(
        name=ZoneName.STORAGE,
        min_x=5.0,
        max_x=15.0,
        min_y=0.0,
        max_y=10.0,
    )

    with pytest.raises(ValueError):
        GeofenceService(
            zones=(
                first,
                second,
            )
        )