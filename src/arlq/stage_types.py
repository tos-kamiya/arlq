"""State and result types shared by the game loop and replay code."""

from collections import Counter
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

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
    # Decorations (d.DECOR_*), one per cell and the same size as `field`.
    # No rule reads them; the sprite GUI draws them. They are written by turn
    # processing, so a rewind's replay rebuilds them along with `field`.
    decor: Optional[List[List[str]]] = None

    def __post_init__(self) -> None:
        if self.decor is None:
            self.decor = [[d.DECOR_NONE] * len(row) for row in self.field]


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
    turn_to_operation: Dict[int, int] = dataclass_field(
        default_factory=lambda: {0: 0}
    )
    rewind_targets: Dict[int, int] = dataclass_field(default_factory=dict)
    vortex_maps: List[Tuple[int, List[List[List[int]]]]] = dataclass_field(
        default_factory=list
    )


@dataclass(frozen=True)
class _ContactResult:
    """Package-private outcome of an entity contact during one game turn."""

    message: Optional[str]
    end_turn: bool = False
    message_ticks: int = MESSAGE_TICKS
    rewind_requested: bool = False


@dataclass(frozen=True)
class _RewindRequest:
    """Package-private signal to the game loop to run rewind handling."""

    floor_index: int
