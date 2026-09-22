"""Events produced by gameplay rules before trace serialization."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field


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
        """Keep the legacy four-value unpacking API during migration."""
        yield self.effect
        yield self.tribes_to_be_respawned
        yield self.message
        yield self.contact_happened
