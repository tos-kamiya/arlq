"""Input replay and rewind reconstruction for multi-floor stages."""

from collections import Counter, deque
from copy import deepcopy
from typing import Deque, List, Optional, Tuple

from . import defs as d
from . import stage5
from .i18n import trp
from .stage_types import Floor, ReplayContext, _RewindRequest
from .stage_world import _spawn, build
from .utils import rand


ReplayedState = Tuple[List[Floor], d.Player, int, d.Point, Counter[Tuple[int, str]]]
ExploredMaps = List[List[List[int]]]


def replay_to_operation(replay: ReplayContext, operation_count: int) -> ReplayedState:
    """Rebuild a run, including discoveries, from its seed and input prefix."""
    state, _ = _replay(replay, operation_count)
    return state


def _replay(
    replay: ReplayContext, operation_count: int, map_since: Optional[int] = None,
) -> Tuple[ReplayedState, Optional[ExploredMaps]]:
    # Imported lazily because game_engine owns turn execution.
    from .game_engine import _step, observe_world

    rand.set_seed(replay.seed)
    if replay.stage_num == 5:
        floors, player = stage5.build(replay.config)
    elif replay.stage_num == 6:
        floors, player = stage5.build_member_trial(replay.config)
    else:
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
    history: Deque[None] = deque()
    # These maps are derived during this replay only, never stored in the
    # live session. Nested Loop contacts reuse them instead of replaying again
    # just to recover knowledge from an earlier disturbance.
    vortex_maps: List[Tuple[int, ExploredMaps]] = []
    first_vortex_map = None

    def observe() -> None:
        observe_world(
            floors, player, floor[0], replay.stage_num, replay.config.torch_radius,
        )

    def remember_map() -> None:
        vortex_maps.append((index, deepcopy([current.seen for current in floors])))

    for index, direction in enumerate(replay.operations[:operation_count]):
        observe()
        for destination in replay.rogue_checks.get(index, ()):
            stage5.rogue_danger(floors[floor[0]], player, destination)
            observe()
        result = _step(
            direction, floors, player, floor, checkpoint, queue, history, index,
            stage_num=replay.stage_num,
            before_vortex=remember_map,
        )
        if map_since is not None:
            first_vortex_map = next(
                (
                    explored for operation, explored in vortex_maps
                    if operation >= map_since
                ),
                None,
            )
            if first_vortex_map is not None:
                break
        if isinstance(result, _RewindRequest):
            target = replay.rewind_targets.get(
                index + 1, max(0, index + 1 - d.LOOP_TURNS),
            )
            preserved_seen = next(
                (
                    explored for operation, explored in vortex_maps
                    if target <= operation <= index
                ),
                [current.seen for current in floors],
            )
            rewind_to_history(
                floors, player, floor, checkpoint, queue, history, replay,
                operation_count=index + 1, loop_floor_index=result.floor_index,
                regenerated_map=preserved_seen,
            )
        else:
            player.lp -= d.movement_lp_cost(player)
        player.current_floor = floor[0]
    observe()
    return (floors, player, floor[0], checkpoint[0], queue), first_vortex_map


def _map_before_vortex(
    replay: ReplayContext, target_count: int, operation_count: int,
) -> Optional[ExploredMaps]:
    # The last operation is the Loop contact itself. Replay earlier inputs to
    # regenerate the first pre-Vortex map in the rewind window, only when needed.
    if target_count >= operation_count - 1:
        return None
    _, explored = _replay(replay, operation_count - 1, map_since=target_count)
    return explored


def rewind_to_history(
    floors: List[Floor],
    player: d.Player,
    floor: List[int],
    checkpoint: List[d.Point],
    queue: Counter[Tuple[int, str]],
    history: Deque[None],
    replay_context: ReplayContext,
    *,
    operation_count: int,
    loop_floor_index: Optional[int] = None,
    regenerated_map: Optional[ExploredMaps] = None,
) -> str:
    """Rebuild the state at the start of the recorded rewind window."""
    known_monsters = set(player.known_monsters)
    known_c_floors = set(player.known_c_floors)
    elf_floors = deepcopy(player.elf_stage_floors)
    known_elf_floors = set(player.known_elf_floors)
    known_member_floors = deepcopy(player.known_member_floors)
    joined_members = set(player.joined_members)
    seen_members = set(player.seen_members)
    seen = deepcopy([floor_data.seen for floor_data in floors])
    discovered_secrets = [
        {
            (x, y): cell
            for y, row in enumerate(floor_data.field)
            for x, cell in enumerate(row)
            if cell
            in (
                d.CHAR_SCHOLAR_STAIRS_UP,
                d.CHAR_SCHOLAR_STAIRS_DOWN,
                d.CHAR_D_GATE,
            )
        }
        for floor_data in floors
    ]

    target_count = replay_context.rewind_targets.get(
        operation_count, max(0, operation_count - d.LOOP_TURNS),
    )
    if regenerated_map is None:
        regenerated_map = _map_before_vortex(replay_context, target_count, operation_count)
    (
        restored_floors, restored_player_state, restored_floor,
        restored_checkpoint, restored_queue,
    ) = replay_to_operation(replay_context, target_count)
    floors[:] = restored_floors
    floor[0] = restored_floor
    checkpoint[0] = restored_checkpoint
    queue.clear()
    queue.update(restored_queue)
    if regenerated_map is not None:
        seen = deepcopy(regenerated_map)

    for floor_data, preserved_seen, preserved_secrets in zip(
        floors, seen, discovered_secrets, strict=True
    ):
        floor_data.seen = preserved_seen
        for (x, y), cell in preserved_secrets.items():
            floor_data.field[y][x] = cell
    player.__dict__.update(restored_player_state.__dict__)
    # Monster/trap identification, elf floor locations, and member discoveries
    # survive the rewind. Entity encounter state is restored by replay.
    player.known_monsters = known_monsters
    player.known_c_floors = known_c_floors
    player.elf_stage_floors = elf_floors
    player.known_elf_floors = known_elf_floors
    player.known_member_floors = known_member_floors
    player.joined_members = joined_members
    player.seen_members = seen_members

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

    return trp("-- Time folds back to the beginning of the recorded past.", 9)
