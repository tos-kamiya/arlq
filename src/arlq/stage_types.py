"""State and result types shared by the game loop and replay code."""

from dataclasses import dataclass
from dataclasses import field as dataclass_field
import pickle
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
    room_components: Tuple[set[d.Point], ...] = ()
    persistent_barriers: set[d.Point] = dataclass_field(default_factory=set)
    broken_walls: set[d.Point] = dataclass_field(default_factory=set)
    respawn_exclusions: set[d.Point] = dataclass_field(default_factory=set)
    monster_spawn_blocked_rooms: set[d.Point] = dataclass_field(default_factory=set)
    monster_spawn_room_rates: Dict[d.Point, int] = dataclass_field(default_factory=dict)
    # Decorations (d.DECOR_*), one per cell and the same size as `field`.
    # No gameplay rule reads them; renderers draw them. They are written by turn
    # processing, so a rewind's replay rebuilds them along with `field`.
    decor: Optional[List[List[str]]] = None
    bridgehead: Optional[d.Point] = None
    # Where the player respawned this turn, and where monsters (not elves)
    # respawned with the turns left (d.RESPAWN_GLOW_TURNS): the sprite GUI
    # lights a column there, around whoever stands on the cell. No rule reads
    # them.
    player_respawn_glow: Optional[d.Point] = None
    respawn_glows: Dict[d.Point, int] = dataclass_field(default_factory=dict)

    # Tutorial monsters allowed to remain horizontally or diagonally adjacent.
    adjacent_monster_exemptions: set[d.Point] = dataclass_field(default_factory=set)

    @property
    def collapse_landings(self) -> set[d.Point]:
        """Derive pit landing positions from terrain."""
        return {(x, y) for y, row in enumerate(self.field)
                for x, cell in enumerate(row) if cell == d.CHAR_PIT_LANDING}

    @property
    def d_gates(self) -> Dict[d.Point, str]:
        """Derive hidden-passage positions and their display glyph from terrain."""
        return {(x, y): "." for y, row in enumerate(self.field)
                for x, cell in enumerate(row) if cell in d.HIDDEN_PASSAGE_CHARS}

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
    """History and saved game states for Loop Fairy rewinds."""

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
    snapshots: Dict[int, bytes] = dataclass_field(default_factory=dict, repr=False)

    def save_snapshot(self, operation_count, floors, player, floor, checkpoint, queue) -> None:
        """Save game state without capturing or changing the random generator."""
        self.snapshots[operation_count] = pickle.dumps(
            (floors, player, floor[0], checkpoint[0], queue), protocol=pickle.HIGHEST_PROTOCOL
        )

    def load_snapshot(self, operation_count):
        return pickle.loads(self.snapshots[operation_count])

    def prune_snapshots(self, game_turn: int) -> None:
        """Retain only states reachable within the Loop Fairy's time limit."""
        oldest_turn = max(0, game_turn - d.LOOP_TURNS)
        keep = {operation for turn, operation in self.turn_to_operation.items()
                if turn >= oldest_turn}
        self.snapshots = {index: snapshot for index, snapshot in self.snapshots.items()
                          if index in keep}

    def prepare_loop_rewind(self, game_turn: int, anchor_turn: int) -> Tuple[int, int]:
        """Record the operation target before restoring a Loop rewind."""
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
