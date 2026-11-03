"""State and result types shared by the game loop and replay code."""

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
    scholar_up_stairs: List[d.Point] = dataclass_field(default_factory=list)
    scholar_down_stairs: List[d.Point] = dataclass_field(default_factory=list)
    contact_reveal: Optional[d.Point] = None
    collapse_landings: set[d.Point] = dataclass_field(default_factory=set)
    room_components: Tuple[set[d.Point], ...] = ()
    d_gates: Dict[d.Point, str] = dataclass_field(default_factory=dict)
    persistent_barriers: set[d.Point] = dataclass_field(default_factory=set)
    broken_walls: set[d.Point] = dataclass_field(default_factory=set)
    respawn_exclusions: set[d.Point] = dataclass_field(default_factory=set)
    # Decorations (d.DECOR_*), one per cell and the same size as `field`.
    # No rule reads them; the sprite GUI draws them. They are written by turn
    # processing, so a rewind's replay rebuilds them along with `field`.
    decor: Optional[List[List[str]]] = None

    # Tutorial monsters allowed to remain horizontally or diagonally adjacent.
    adjacent_monster_exemptions: set[d.Point] = dataclass_field(default_factory=set)

    def __post_init__(self) -> None:
        if self.decor is None:
            self.decor = [[d.DECOR_NONE] * len(row) for row in self.field]

    def update_outer_wall_decor(self) -> None:
        """Mark buried walls at the edges and inside solid wall areas."""
        for row in self.decor:
            for x, value in enumerate(row):
                if value in (d.DECOR_OUTER_WALL, d.DECOR_BURIED_WALL):
                    row[x] = d.DECOR_NONE
        for y, row in enumerate(self.field):
            walls = (*d.WALL_CHARS, d.CHAR_HIDDEN_D_GATE)
            interior = [x for x, cell in enumerate(row) if cell not in walls]
            edge_row = y in (0, len(self.field) - 1)
            if not interior and not edge_row:
                continue
            for x, cell in enumerate(row):
                if (cell != d.CHAR_WALL or self.decor[y][x] != d.DECOR_NONE
                        or (not edge_row and interior[0] <= x <= interior[-1])):
                    continue
                if all(not (0 <= ny < len(self.field) and 0 <= nx < len(self.field[ny]))
                       or self.field[ny][nx] in walls
                       for ny in range(y - 1, y + 2)
                       for nx in range(x - 1, x + 2)):
                    self.decor[y][x] = d.DECOR_OUTER_WALL
        walls = (*d.WALL_CHARS, d.CHAR_HIDDEN_D_GATE)
        for y, row in enumerate(self.field):
            for x, cell in enumerate(row):
                if (cell == d.CHAR_WALL and self.decor[y][x] == d.DECOR_NONE
                        and all(
                            0 <= ny < len(self.field)
                            and 0 <= nx < len(self.field[ny])
                            and self.field[ny][nx] in walls
                            for ny in range(y - 1, y + 2)
                            for nx in range(x - 1, x + 2)
                        )):
                    self.decor[y][x] = d.DECOR_BURIED_WALL


@dataclass
class ReplayContext:
    """Seed and player inputs needed to reconstruct rewindable game state."""

    stage_num: int
    seed: int
    config: "GameConfig"
    operations: List[d.Point] = dataclass_field(default_factory=list)
    turn_to_operation: Dict[int, int] = dataclass_field(
        default_factory=lambda: {0: 0}
    )
    rewind_targets: Dict[int, int] = dataclass_field(default_factory=dict)
    ration_uses: set[int] = dataclass_field(default_factory=set)
    # Non-turn Rogue checks, indexed by the next committed operation.
    rogue_checks: Dict[int, List[d.Point]] = dataclass_field(default_factory=dict)

    def prepare_loop_rewind(self, game_turn: int, anchor_turn: int) -> Tuple[int, int]:
        """Record the operation target before reconstructing a Loop rewind."""
        rewind_turn = max(anchor_turn, game_turn - d.LOOP_TURNS)
        rewind_operation = self.turn_to_operation.get(rewind_turn, 0)
        self.rewind_targets[len(self.operations)] = rewind_operation
        return rewind_turn, rewind_operation

    def anchor_loop_rewind(self, rewind_turn: int) -> None:
        """Map the restored turn to this contact, including its Loop respawn."""
        for recorded_turn in tuple(self.turn_to_operation):
            if recorded_turn > rewind_turn:
                del self.turn_to_operation[recorded_turn]
        self.turn_to_operation[rewind_turn] = len(self.operations)


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
