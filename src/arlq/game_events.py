"""Events produced by gameplay rules before trace serialization."""

from __future__ import annotations

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
    # Where the stage boss stood when this fight first defeated it (not set
    # for the Dungeon Core), for the boss's afterglow.
    boss_at: Point | None = None
    # Where the Dungeon Core stood when this fight destroyed it.
    core_at: Point | None = None


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
class IrisRation(GameEvent):
    # Where Iris stands as she hands over her ration.
    at: Point


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
