"""Events produced by gameplay rules before trace serialization."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from .defs import Point


@dataclass(frozen=True)
class EntityRef:
    uid: int
    glyph: str
    kind: str


@dataclass
class GameEvent:
    floor: int


@dataclass
class Combat(GameEvent):
    attacker: Point
    targets: list[tuple[EntityRef, Point]]
    won: bool
    lp_delta: float
    # Party positions before contact, used by the existing loss flash.
    party_positions: list[Point] = field(default_factory=list)


@dataclass
class BarrierHit(GameEvent):
    at: Point
    amount: float


@dataclass
class FloorChanged(GameEvent):
    kind: str
    to_floor: int
    exit_point: Point | None


@dataclass
class Rewound(GameEvent):
    message: str
    trail: dict[int, set[Point]]


def _emit(events: list[GameEvent] | None, event: GameEvent) -> None:
    if events is not None:
        events.append(event)


@dataclass
class WallEvent:
    result: str
    item_uses_left: int | None = None


@dataclass
class ContactEvent:
    kind: str
    event_id: str
    outcome: str | None = None
    respawn_to: tuple[int, int] | None = None
    collected: bool | None = None
    from_floor: int | None = None
    to_floor: int | None = None


@dataclass
class ExpiredEvent:
    kind: str
    event_id: str | None = None
    item: str | None = None
    reason: str | None = None


@dataclass
class WorldEvent:
    kind: str
    event_id: str
    at: tuple[int, int]
    floor: int | None = None


@dataclass
class TurnEvents:
    wall: WallEvent | None = None
    contact: ContactEvent | None = None
    expired: list[ExpiredEvent] = field(default_factory=list)
    world: list[WorldEvent] = field(default_factory=list)


@dataclass
class UpdateResult:
    effect: str | None
    tribes_to_be_respawned: list[str]
    message: tuple[int, str] | None
    contact_happened: bool
    events: TurnEvents

    def __iter__(self) -> Iterator[object]:
        """Keep the earlier four-value unpacking API for direct callers."""
        yield self.effect
        yield self.tribes_to_be_respawned
        yield self.message
        yield self.contact_happened
