"""Input replay and rewind reconstruction for multi-floor stages."""

from collections import Counter, deque
from copy import deepcopy
from typing import Deque, List, Optional, Tuple

from . import defs as d
from .i18n import t as tr
from .stage_types import Floor, HistoryEntry, ReplayContext, _RewindRequest
from .stage_world import _spawn, build
from .utils import rand


def replay_to_operation(
    replay: ReplayContext,
    operation_count: int,
) -> Tuple[List[Floor], d.Player, int, d.Point, Counter[Tuple[int, str]]]:
    """Rebuild a run from its seed and replay the requested input prefix."""
    # Imported lazily because game_engine owns turn execution and imports this
    # module for rewind handling.
    from .game_engine import _step

    previous_vortex_maps = replay.vortex_maps
    # Rebuild V snapshots from the seed as well. Earlier l contacts need the
    # pre-disturbance map generated on this replayed timeline.
    replay.vortex_maps = []
    try:
        rand.set_seed(replay.seed)
        floors, player = build(
            replay.config.corridor_h_width,
            replay.config.corridor_v_width,
            replay.stage_num,
        )
        player.known_monsters = set()
        player.boss_defeated = False
        player.treasure_collected = False
        floor = [0]
        checkpoint = [floors[0].up]
        queue: Counter[Tuple[int, str]] = Counter()
        history: Deque[HistoryEntry] = deque()
        turn = 0
        for index, direction in enumerate(replay.operations[:operation_count]):
            result = _step(
                direction,
                floors,
                player,
                floor,
                checkpoint,
                queue,
                history,
                turn,
                stage_num=replay.stage_num,
                replay_context=replay,
                operation_index=index,
            )
            if isinstance(result, _RewindRequest):
                rewind_to_history(
                    floors,
                    player,
                    floor,
                    checkpoint,
                    queue,
                    history,
                    replay,
                    operation_count=index + 1,
                    loop_floor_index=result.floor_index,
                )
            turn += 1
            player.lp -= 1
        return floors, player, floor[0], checkpoint[0], queue
    finally:
        replay.vortex_maps = previous_vortex_maps


def rewind_to_history(
    floors: List[Floor],
    player: d.Player,
    floor: List[int],
    checkpoint: List[d.Point],
    queue: Counter[Tuple[int, str]],
    history: Deque[HistoryEntry],
    replay_context: Optional[ReplayContext] = None,
    operation_count: Optional[int] = None,
    loop_floor_index: Optional[int] = None,
) -> str:
    """Rebuild the state at the start of the recorded rewind window."""
    known_monsters = set(player.known_monsters)
    elf_floors = deepcopy(player.elf_stage_floors)
    known_elf_floors = set(player.known_elf_floors)
    seen = deepcopy([floor_data.seen for floor_data in floors])

    if replay_context is not None:
        if operation_count is None:
            raise ValueError("operation_count is required when replaying a rewind")
        # The rewind window follows the complete recorded input timeline, not
        # the post-rewind history deque (which is cleared after each l).
        target_count = max(0, operation_count - d.LOOP_TURNS)
        first_vortex_map = next(
            (
                map_state
                for operation_index, map_state in replay_context.vortex_maps
                if target_count <= operation_index < operation_count
            ),
            seen,
        )
        (
            restored_floors,
            restored_player,
            restored_floor,
            restored_checkpoint,
            restored_queue,
        ) = replay_to_operation(replay_context, target_count)
        floors[:] = restored_floors
        floor[0] = restored_floor
        checkpoint[0] = restored_checkpoint
        queue.clear()
        queue.update(restored_queue)
        restored_player_state = restored_player
        seen = deepcopy(first_vortex_map)
    else:
        # Keep direct rule-level callers compatible; actual game sessions use
        # seed-and-input replay through replay_context.
        old_entry = history[0]
        if old_entry is None:
            raise RuntimeError("snapshot-free rewind requires a replay context")
        old_floors, restored_player_state, old_floor, old_checkpoint, old_queue = (
            old_entry
        )
        floors[:] = old_floors
        queue.clear()
        queue.update(old_queue)
        floor[0], checkpoint[0] = old_floor, old_checkpoint

    for floor_data, preserved_seen in zip(floors, seen, strict=True):
        floor_data.seen = preserved_seen
    player.__dict__.update(restored_player_state.__dict__)
    # Monster/trap identification, elf floor locations, and known elf contacts
    # survive the rewind. Entity encounter state is restored by replay.
    player.known_monsters = known_monsters
    player.elf_stage_floors = elf_floors
    player.known_elf_floors = known_elf_floors

    history.clear()

    respawn_floor = floor[0] if loop_floor_index is None else loop_floor_index
    loop_floor = floors[respawn_floor]
    restored_entities = loop_floor.entities
    for index, restored in enumerate(restored_entities):
        if isinstance(restored, d.Companion) and restored.tribe.char == "l":
            del restored_entities[index]
            break
    l_position = _spawn(
        restored_entities,
        loop_floor.field,
        "l",
        {(player.x, player.y)} if respawn_floor == floor[0] else set(),
        loop_floor.island,
        respawn_floor,
    )
    for restored in restored_entities:
        if (
            isinstance(restored, d.Companion)
            and restored.tribe.char == "l"
            and (restored.x, restored.y) == l_position
        ):
            restored.revealed = True
            break

    return tr("-- Time folds back to the beginning of the recorded past.")
