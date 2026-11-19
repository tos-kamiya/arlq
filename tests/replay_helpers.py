"""Test-only reconstruction of a multi-floor run from its seed and inputs.

Replays a ``ReplayContext`` the way ``game_engine.run_game()`` plays it, so
tests can check that a recorded run and its replay reach the same state.
"""

from collections import Counter

from arlq import bridgehead, stage5, stage56, stage6, stage_replay, stage_world
from arlq import defs as d
from arlq.game_engine import _process_multi_floor_turn, observe_world
from arlq.stage_types import Floor, ReplayContext, _RewindRequest
from arlq.utils import rand

ReplayedState = tuple[list[Floor], d.Player, int, d.Point, Counter[tuple[int, str]]]


def replay_to_operation(replay: ReplayContext, operation_count: int) -> ReplayedState:
    """Rebuild a run, including discoveries, from its seed and input prefix."""
    rand.set_seed(replay.seed)
    if replay.stage_num == 6:
        floors, player = stage6.build(replay.config)
    elif replay.stage_num == 5:
        floors, player = stage5.build_member_trial()
    else:
        floors, player = stage_world.build(
            replay.config.corridor_h_width,
            replay.config.corridor_v_width,
            replay.stage_num,
        )
    for floor_data in floors:
        floor_data.update_outer_wall_decor()
    player.known_monsters = set(d.INITIALLY_KNOWN_MONSTERS)
    player.boss_defeated = False
    player.dungeon_core_destroyed = False
    player.treasure_collected = False
    floor = [0]
    checkpoint = [floors[0].up]
    queue: Counter[tuple[int, str]] = Counter()
    replay_state = ReplayContext(replay.stage_num, replay.seed, replay.config)
    replay_state.rewind_targets = replay.rewind_targets.copy()

    def observe() -> None:
        observe_world(
            floors, player, floor[0], replay.config.torch_radius,
        )

    for index, direction in enumerate(replay.operations[:operation_count]):
        observe()
        for destination in replay.rogue_checks.get(index, ()):
            stage56.rogue_danger(floors[floor[0]], destination)
            observe()
        replay_state.save_snapshot(index, floors, player, floor, checkpoint, queue)
        previous_floor = floor[0]
        previous_point = (player.x, player.y)
        result = _process_multi_floor_turn(
            direction, floors, player, floor, checkpoint, queue, index,
            stage_num=replay.stage_num,
        )
        if isinstance(result, _RewindRequest):
            stage_replay.rewind(
                floors, player, floor, checkpoint, queue, replay_state,
                operation_count=index + 1, loop_floor_index=result.floor_index,
            )
        else:
            player.lp -= d.movement_lp_cost(player)
            bridgehead.recover_at_bridgehead(
                floors, player, floor[0], previous_floor, previous_point
            )
        player.current_floor = floor[0]
    observe()
    return floors, player, floor[0], checkpoint[0], queue
