"""Shared state types for multi-floor stages."""

from collections import Counter
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import TYPE_CHECKING, List, Optional, Tuple

from . import defs as d
from .arlq import MESSAGE_TICKS

if TYPE_CHECKING:
    from .arlq import GameConfig


@dataclass
class Floor:
    """State owned by one floor in a multi-floor stage."""

    field: List[List[str]]
    entities: List[d.Entity]
    seen: List[List[int]]
    up: d.Point
    down: d.Point
    island: Optional[d.Point]
    up_stairs: List[d.Point] = dataclass_field(default_factory=list)
    down_stairs: List[d.Point] = dataclass_field(default_factory=list)
    contact_reveal: Optional[d.Point] = None
    collapse_landings: set[d.Point] = dataclass_field(default_factory=set)
    room_components: Tuple[set[d.Point], ...] = ()
    persistent_barriers: set[d.Point] = dataclass_field(default_factory=set)


HistoryEntry = Optional[
    Tuple[List[Floor], d.Player, int, d.Point, Counter[Tuple[int, str]]]
]


@dataclass
class ReplayContext:
    """Inputs and map snapshots needed to reconstruct rewindable game state."""

    stage_num: int
    seed: int
    config: "GameConfig"
    operations: List[d.Point] = dataclass_field(default_factory=list)
    vortex_maps: List[Tuple[int, List[List[List[int]]]]] = dataclass_field(
        default_factory=list
    )


@dataclass(frozen=True)
class _ContactResult:
    """Outcome of an entity contact within one Stage 3 turn."""

    message: Optional[str]
    end_turn: bool = False
    message_ticks: int = MESSAGE_TICKS
    rewind_requested: bool = False


@dataclass(frozen=True)
class _RewindRequest:
    """Signal from a turn step to the game loop to run rewind handling."""

    floor_index: int
