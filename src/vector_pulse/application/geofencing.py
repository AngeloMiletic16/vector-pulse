from dataclasses import dataclass
from enum import Enum

from vector_pulse.ingestion.schemas import Position


class ZoneName(str, Enum):
    RECEIVING = "receiving"
    STORAGE = "storage"
    ASSEMBLY = "assembly"
    SHIPPING = "shipping"


@dataclass(frozen=True)
class Zone:
    name: ZoneName
    min_x: float
    max_x: float
    min_y: float
    max_y: float

    def __post_init__(self) -> None:
        if self.min_x >= self.max_x:
            raise ValueError(
                "Zone min_x must be smaller than max_x"
            )

        if self.min_y >= self.max_y:
            raise ValueError(
                "Zone min_y must be smaller than max_y"
            )

    def contains(
        self,
        position: Position,
    ) -> bool:
        return (
            self.min_x <= position.x < self.max_x
            and self.min_y <= position.y < self.max_y
        )

    def overlaps(
        self,
        other: "Zone",
    ) -> bool:
        return (
            self.min_x < other.max_x
            and self.max_x > other.min_x
            and self.min_y < other.max_y
            and self.max_y > other.min_y
        )


@dataclass(frozen=True)
class ZoneTransition:
    previous_zone: ZoneName | None
    current_zone: ZoneName | None
    position_accepted: bool = True

    @property
    def changed(self) -> bool:
        return (
            self.position_accepted
            and self.previous_zone != self.current_zone
        )

    @property
    def entered_zone(self) -> ZoneName | None:
        if not self.changed:
            return None

        return self.current_zone

    @property
    def exited_zone(self) -> ZoneName | None:
        if not self.changed:
            return None

        return self.previous_zone


class GeofenceService:
    def __init__(
        self,
        zones: tuple[Zone, ...],
        minimum_position_quality: float = 0.6,
    ) -> None:
        if not 0.0 <= minimum_position_quality <= 1.0:
            raise ValueError(
                "Minimum position quality must be "
                "between 0.0 and 1.0"
            )

        self._validate_zones(zones)

        self._zones = zones
        self._minimum_position_quality = (
            minimum_position_quality
        )

    @property
    def zones(self) -> tuple[Zone, ...]:
        return self._zones

    @property
    def minimum_position_quality(self) -> float:
        return self._minimum_position_quality

    def resolve_zone(
        self,
        position: Position,
    ) -> ZoneName | None:
        for zone in self._zones:
            if zone.contains(position):
                return zone.name

        return None

    def evaluate(
        self,
        previous_zone: ZoneName | None,
        position: Position,
    ) -> ZoneTransition:
        if (
            position.quality
            < self._minimum_position_quality
        ):
            return ZoneTransition(
                previous_zone=previous_zone,
                current_zone=previous_zone,
                position_accepted=False,
            )

        current_zone = self.resolve_zone(position)

        return ZoneTransition(
            previous_zone=previous_zone,
            current_zone=current_zone,
        )

    @staticmethod
    def _validate_zones(
        zones: tuple[Zone, ...],
    ) -> None:
        names = [zone.name for zone in zones]

        if len(names) != len(set(names)):
            raise ValueError(
                "Zone names must be unique"
            )

        for index, zone in enumerate(zones):
            for other in zones[index + 1:]:
                if zone.overlaps(other):
                    raise ValueError(
                        f"Zones {zone.name.value} and "
                        f"{other.name.value} overlap"
                    )


DEFAULT_ZONES = (
    Zone(
        name=ZoneName.RECEIVING,
        min_x=0.0,
        max_x=10.0,
        min_y=0.0,
        max_y=20.0,
    ),
    Zone(
        name=ZoneName.STORAGE,
        min_x=10.0,
        max_x=25.0,
        min_y=0.0,
        max_y=20.0,
    ),
    Zone(
        name=ZoneName.ASSEMBLY,
        min_x=25.0,
        max_x=40.0,
        min_y=0.0,
        max_y=20.0,
    ),
    Zone(
        name=ZoneName.SHIPPING,
        min_x=40.0,
        max_x=55.0,
        min_y=0.0,
        max_y=20.0,
    ),
)


def create_default_geofence() -> GeofenceService:
    return GeofenceService(
        zones=DEFAULT_ZONES,
        minimum_position_quality=0.6,
    )
