"""Input replay and rewind reconstruction for multi-floor stages."""

from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from . import defs as d
from . import stage5
from . import stage56
from . import stage6
from .i18n import trp
from .stage_types import Floor, ReplayContext, _RewindRequest
from .stage_world import _spawn, build
from .utils import rand


ReplayedState = Tuple[List[Floor], d.Player, int, d.Point, Counter[Tuple[int, str]]]


@dataclass
class _RewindKnowledge:
    """Discoveries carried across reconstruction; encounter state is excluded."""

    known_monsters: Set[str]
    known_c_floors: Set[int]
    elf_floors: Dict[str, int]
    known_elf_floors: Set[str]
    known_member_floors: Dict[str, int]
    seen_members: Set[str]
    seen: List[List[List[int]]]
    discovered_secrets: List[Dict[d.Point, str]]

    @classmethod
    def capture(cls, floors: List[Floor], player: d.Player) -> "_RewindKnowledge":
        return cls(
            known_monsters=set(player.known_monsters),
            known_c_floors=set(player.known_c_floors),
            elf_floors=deepcopy(player.elf_stage_floors),
            known_elf_floors=set(player.known_elf_floors),
            known_member_floors=deepcopy(player.known_member_floors),
            seen_members=set(player.seen_members),
            seen=deepcopy([floor_data.seen for floor_data in floors]),
            discovered_secrets=[
                {
                    (x, y): cell
                    for y, row in enumerate(floor_data.field)
                    for x, cell in enumerate(row)
                    if cell in (
                        d.CHAR_SCHOLAR_STAIRS_UP,
                        d.CHAR_SCHOLAR_STAIRS_DOWN,
                        d.CHAR_D_GATE,
                    )
                }
                for floor_data in floors
            ],
        )

    def restore(self, floors: List[Floor], player: d.Player) -> None:
        for floor_data, preserved_seen, preserved_secrets in zip(
            floors, self.seen, self.discovered_secrets, strict=True
        ):
            floor_data.seen = preserved_seen
            for (x, y), cell in preserved_secrets.items():
                floor_data.field[y][x] = cell
        player.known_monsters = self.known_monsters
        player.known_c_floors = self.known_c_floors
        player.elf_stage_floors = self.elf_floors
        player.known_elf_floors = self.known_elf_floors
        player.known_member_floors = self.known_member_floors
        player.seen_members = self.seen_members


def replay_to_operation(replay: ReplayContext, operation_count: int) -> ReplayedState:
    """Rebuild a run, including discoveries, from its seed and input prefix."""
    # Imported lazily because game_engine owns turn execution.
    from .game_engine import _step, observe_world

    rand.set_seed(replay.seed)
    if replay.stage_num == 6:
        floors, player = stage6.build(replay.config)
    elif replay.stage_num == 5:
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

    def observe() -> None:
        observe_world(
            floors, player, floor[0], replay.config.torch_radius,
        )

    if 0 in replay.ration_uses:
        player.lp = d.STAGE6_RATION_LP if replay.stage_num == 6 else d.RATION_LP
        player.rations -= 1
    for index, direction in enumerate(replay.operations[:operation_count]):
        observe()
        for destination in replay.rogue_checks.get(index, ()):
            stage56.rogue_danger(floors[floor[0]], destination)
            observe()
        result = _step(
            direction, floors, player, floor, checkpoint, queue, index,
            stage_num=replay.stage_num,
        )
        if isinstance(result, _RewindRequest):
            rewind(
                floors, player, floor, checkpoint, queue, replay,
                operation_count=index + 1, loop_floor_index=result.floor_index,
            )
        else:
            player.lp -= d.movement_lp_cost(player)
        if index + 1 in replay.ration_uses:
            player.lp = d.STAGE6_RATION_LP if replay.stage_num == 6 else d.RATION_LP
            player.rations -= 1
        player.current_floor = floor[0]
    observe()
    return floors, player, floor[0], checkpoint[0], queue


def rewind(
    floors: List[Floor],
    player: d.Player,
    floor: List[int],
    checkpoint: List[d.Point],
    queue: Counter[Tuple[int, str]],
    replay_context: ReplayContext,
    *,
    operation_count: int,
    loop_floor_index: Optional[int] = None,
) -> str:
    """Replay to the rewind target and carry over the player's current knowledge."""
    remaining_rations = player.rations
    knowledge = _RewindKnowledge.capture(floors, player)

    target_count = replay_context.rewind_targets.get(
        operation_count, max(0, operation_count - d.LOOP_TURNS),
    )
    (
        restored_floors, restored_player_state, restored_floor,
        restored_checkpoint, restored_queue,
    ) = replay_to_operation(replay_context, target_count)
    floors[:] = restored_floors
    floor[0] = restored_floor
    checkpoint[0] = restored_checkpoint
    queue.clear()
    queue.update(restored_queue)

    player.__dict__.update(restored_player_state.__dict__)
    player.rations = remaining_rations
    knowledge.restore(floors, player)

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
