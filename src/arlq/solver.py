from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import argparse
import heapq
from typing import Iterable, Optional

from . import defs as d
from .arlq import create_field, get_torched, respawn_entity, spawn_entities, update_entities
from .utils import rand


DEFAULT_RUNTIME_CONSTANTS = {
    "TILE_NUM_Y": d.TILE_NUM_Y,
    "FIELD_HEIGHT": d.FIELD_HEIGHT,
    "TORCH_RADIUS": d.TORCH_RADIUS,
    "CORRIDOR_H_WIDTH": d.CORRIDOR_H_WIDTH,
    "CORRIDOR_V_WIDTH": d.CORRIDOR_V_WIDTH,
}


@dataclass
class SimulationState:
    stage_num: int
    field: list[list[str]]
    player: d.Player
    entities: list[d.Entity]
    encountered_types: set[str]
    torched: list[list[int]]
    hours: int = -1
    torch_radius: int = d.TORCH_RADIUS
    respawn_queue: Counter[str] | None = None
    planned_target: Optional[d.Entity] = None
    won: bool = False
    ended: bool = False

    def __post_init__(self) -> None:
        if self.respawn_queue is None:
            self.respawn_queue = Counter()


@dataclass
class SimulationResult:
    seed: int
    won: bool
    hours: int
    lp: int
    level: int


def apply_runtime_flags(args: argparse.Namespace) -> None:
    d.TILE_NUM_Y = DEFAULT_RUNTIME_CONSTANTS["TILE_NUM_Y"]
    d.FIELD_HEIGHT = DEFAULT_RUNTIME_CONSTANTS["FIELD_HEIGHT"]
    d.TORCH_RADIUS = DEFAULT_RUNTIME_CONSTANTS["TORCH_RADIUS"]
    d.CORRIDOR_H_WIDTH = DEFAULT_RUNTIME_CONSTANTS["CORRIDOR_H_WIDTH"]
    d.CORRIDOR_V_WIDTH = DEFAULT_RUNTIME_CONSTANTS["CORRIDOR_V_WIDTH"]

    if args.large_field:
        d.TILE_NUM_Y += 1
        d.FIELD_HEIGHT = (d.TILE_HEIGHT + 1) * d.TILE_NUM_Y + 1

    if args.large_torch:
        d.TORCH_RADIUS += 1
    elif args.small_torch:
        d.TORCH_RADIUS -= 1

    if args.narrower_corridors:
        d.CORRIDOR_H_WIDTH -= 1
        d.CORRIDOR_V_WIDTH -= 1


def build_simulation(stage_num: int, seed: int) -> SimulationState:
    rand.set_seed(seed)
    spawn_config = d.STAGE_TO_SPAWN_CONFIGS[stage_num - 1]
    field, first_p, last_p = create_field(d.CORRIDOR_H_WIDTH, d.CORRIDOR_V_WIDTH, d.WALL_CHAR)
    encountered_types: set[str] = set()
    torched = [[0 for _ in range(d.FIELD_WIDTH)] for _ in range(d.FIELD_HEIGHT)]
    entities: list[d.Entity] = []

    for sc in spawn_config:
        if isinstance(sc.tribe, d.MonsterTribe) and sc.tribe.effect == d.EFFECT_UNLOCK_TREASURE:
            entities.append(d.Treasure(last_p[0], last_p[1], d.CHAR_TREASURE + sc.tribe.char))
            break

    player = d.Player(first_p[0], first_p[1], 1, d.LP_INIT)
    entities.append(player)
    spawn_entities(entities, field, torched, spawn_config)

    return SimulationState(
        stage_num=stage_num,
        field=field,
        player=player,
        entities=entities,
        encountered_types=encountered_types,
        torched=torched,
        torch_radius=d.TORCH_RADIUS,
    )


def is_target_entity(state: SimulationState, entity: d.Entity) -> bool:
    player = state.player
    if isinstance(entity, d.Treasure):
        return entity.encounter_type in state.encountered_types
    if isinstance(entity, d.Monster):
        return d.player_attack_by_level(player) >= entity.tribe.level
    if isinstance(entity, d.Companion):
        return entity.tribe.char == "p"
    return False


def entity_priority(state: SimulationState, entity: d.Entity) -> int:
    player = state.player
    if isinstance(entity, d.Treasure):
        return 10_000
    if isinstance(entity, d.Companion):
        return 250
    if not isinstance(entity, d.Monster):
        return -10_000

    priority = 0
    if entity.tribe.effect == d.EFFECT_UNLOCK_TREASURE:
        priority += 8_000
    if entity.tribe.effect == d.EFFECT_SPECIAL_EXP:
        priority += 4_000
    if entity.tribe.item == d.ITEM_SWORD_CURSED:
        priority += 2_500
    elif entity.tribe.item == d.ITEM_SWORD_X1_5:
        priority += 1_800

    if player.lp <= 30:
        priority += max(entity.tribe.feed, 0) * 25
    else:
        priority += max(entity.tribe.feed, 0) * 4

    priority += entity.tribe.level * 10
    if entity.tribe.effect == d.EFFECT_ENERGY_DRAIN:
        priority -= 600
    if entity.tribe.effect == d.EFFECT_CALTROP_SPREAD:
        priority -= 200

    priority += strategy_bonus(state, entity)
    return priority


def strategy_bonus(state: SimulationState, entity: d.Monster) -> int:
    atk = d.player_attack_by_level(state.player)
    lp = state.player.lp
    ch = entity.tribe.char
    item = state.player.item

    if state.stage_num == 1:
        if item == d.ITEM_SWORD_X1_5:
            if ch == d.CHAR_DRAGON:
                return 20_000 if atk >= d.CHAR_TO_MONSTER_TRIBE[d.CHAR_DRAGON].level else -8_000
            return -9_000
        if ch == d.CHAR_DRAGON:
            return 12_000 if atk >= entity.tribe.level else -8_000
        if ch == "A":
            if atk < 10:
                return 5_000 if atk >= 2 else -3_000
            if atk < 20:
                return 1_200
            return -300 if lp < 35 else 300
        if ch == "a":
            if atk < 5:
                return 2_500
            if lp < 20:
                return 600
            return -500
        if ch == "b":
            if atk < 5:
                return -3_000
            if lp < 45:
                return 4_500
            if atk < 20:
                return 2_000
            return 1_000
        if ch == "c":
            if state.player.level < 27 or lp < 45:
                return -2_500
            return 5_500
        if ch == "d":
            if atk < 20:
                return -4_000
            if lp < 55:
                return 3_000
            return 1_500
        if ch == "X":
            return -1_000
        if ch == "e":
            return -3_000

    if state.stage_num == 2:
        if item == d.ITEM_SWORD_CURSED:
            if ch == d.CHAR_FIRE_DRAKE:
                return 22_000 if atk >= d.CHAR_TO_MONSTER_TRIBE[d.CHAR_FIRE_DRAKE].level else -9_000
            return -10_000
        if ch == d.CHAR_FIRE_DRAKE:
            return 14_000 if atk >= entity.tribe.level else -8_000
        if ch == "C":
            if state.player.level < 20 or lp < 50:
                return -3_000
            return 8_000
        if ch == "A":
            if atk < 10:
                return 5_000 if atk >= 2 else -3_000
            if atk < 15:
                return 1_400
            return -500 if lp < 35 else 400
        if ch == "a":
            if atk < 5:
                return 2_500
            if lp < 20:
                return 600
            return -500
        if ch == "b":
            if atk < 5:
                return -3_000
            if lp < 45:
                return 4_800
            return 1_800
        if ch == "c":
            return -2_000
        if ch == "d":
            if atk < 20:
                return -4_000
            if lp < 55:
                return 3_200
            return 1_500
        if ch == "g":
            if atk < 30:
                return -5_000
            return 800
        if ch == "X":
            return -2_500
        if ch == "e":
            return -4_000
        if ch == "h":
            return -10_000

    return 0


def build_blocked_cells(state: SimulationState, target: d.Entity) -> set[d.Point]:
    blocked: set[d.Point] = set()
    for entity in state.entities:
        if entity is state.player or entity is target:
            continue
        if isinstance(entity, d.Treasure) and entity.encounter_type not in state.encountered_types:
            blocked.add((entity.x, entity.y))
        elif isinstance(entity, d.Monster):
            blocked.add((entity.x, entity.y))
        elif isinstance(entity, d.Companion):
            blocked.add((entity.x, entity.y))
    return blocked


def build_full_blocked_cells(state: SimulationState) -> set[d.Point]:
    blocked: set[d.Point] = set()
    for entity in state.entities:
        if entity is state.player:
            continue
        if isinstance(entity, d.Treasure) and entity.encounter_type not in state.encountered_types:
            blocked.add((entity.x, entity.y))
        elif isinstance(entity, (d.Monster, d.Companion)):
            blocked.add((entity.x, entity.y))
    return blocked


def run_weighted_search(
    state: SimulationState, blocked: set[d.Point]
) -> tuple[dict[d.Point, int], dict[d.Point, d.Point]]:
    start = (state.player.x, state.player.y)
    queue: list[tuple[int, d.Point]] = [(0, start)]
    best_cost: dict[d.Point, int] = {start: 0}
    previous: dict[d.Point, d.Point] = {}

    while queue:
        cost, current = heapq.heappop(queue)
        if cost != best_cost.get(current):
            continue
        cx, cy = current
        for dx, dy in ((0, -1), (-1, 0), (1, 0), (0, 1)):
            nx, ny = cx + dx, cy + dy
            if not (0 <= nx < d.FIELD_WIDTH and 0 <= ny < d.FIELD_HEIGHT):
                continue
            next_point = (nx, ny)
            if next_point in blocked:
                continue
            if state.field[ny][nx] not in (" ", d.CHAR_CALTROP):
                continue
            step_cost = 4 if state.field[ny][nx] == d.CHAR_CALTROP else 1
            next_cost = cost + step_cost
            if next_cost >= best_cost.get(next_point, 10**9):
                continue
            best_cost[next_point] = next_cost
            previous[next_point] = current
            heapq.heappush(queue, (next_cost, next_point))

    return best_cost, previous


def reconstruct_path(
    previous: dict[d.Point, d.Point], start: d.Point, goal: d.Point
) -> list[d.Point]:
    path = [goal]
    while path[-1] != start:
        path.append(previous[path[-1]])
    path.reverse()
    return path


def find_path_to_target(state: SimulationState, target: d.Entity) -> Optional[list[d.Point]]:
    start = (state.player.x, state.player.y)
    goal = (target.x, target.y)
    blocked = build_blocked_cells(state, target)
    best_cost, previous = run_weighted_search(state, blocked)
    if goal not in best_cost:
        return None
    return reconstruct_path(previous, start, goal)


def choose_target(state: SimulationState) -> tuple[Optional[d.Entity], Optional[d.Point]]:
    start = (state.player.x, state.player.y)
    immediate_candidates: list[tuple[int, d.Entity, d.Point]] = []
    for entity in state.entities:
        if entity is state.player or not is_target_entity(state, entity):
            continue
        if abs(entity.x - state.player.x) + abs(entity.y - state.player.y) == 1:
            immediate_candidates.append((entity_priority(state, entity), entity, (entity.x, entity.y)))
    if immediate_candidates:
        immediate_candidates.sort(key=lambda item: item[0], reverse=True)
        _, entity, next_point = immediate_candidates[0]
        return entity, next_point

    blocked = build_full_blocked_cells(state)
    best_cost, previous = run_weighted_search(state, blocked)
    candidates: list[tuple[int, int, d.Entity, d.Point, d.Point]] = []
    for entity in state.entities:
        if entity is state.player or not is_target_entity(state, entity):
            continue
        target_pos = (entity.x, entity.y)
        approach_points: list[tuple[int, d.Point]] = []
        for dx, dy in ((0, -1), (-1, 0), (1, 0), (0, 1)):
            neighbor = (entity.x + dx, entity.y + dy)
            if neighbor == start:
                approach_points.append((0, start))
                continue
            if neighbor in best_cost:
                approach_points.append((best_cost[neighbor], neighbor))
        if not approach_points:
            continue
        distance, approach_point = min(approach_points, key=lambda item: item[0])
        score = entity_priority(state, entity) - distance * 15
        if isinstance(entity, d.Monster) and entity.tribe.effect == d.EFFECT_UNLOCK_TREASURE:
            if state.player.lp <= distance + 18:
                score -= 12_000
        elif isinstance(entity, d.Treasure):
            if state.player.lp <= distance + 8:
                score -= 12_000
        candidates.append((score, -distance, entity, approach_point, target_pos))
    if candidates:
        candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
        _, _, entity, approach_point, target_pos = candidates[0]
        if approach_point == start:
            return entity, target_pos
        path = reconstruct_path(previous, start, approach_point)
        return entity, path[1]
    return None, None


def choose_wander_direction(state: SimulationState) -> d.Point:
    cur_torched = get_torched(state.player, state.torch_radius)
    target_cells: list[d.Point] = []
    for y in range(d.FIELD_HEIGHT):
        for x in range(d.FIELD_WIDTH):
            if state.field[y][x] == " " and not state.torched[y][x] and not cur_torched[y][x]:
                target_cells.append((x, y))

    if target_cells:
        queue: list[tuple[int, d.Point]] = [(0, (state.player.x, state.player.y))]
        previous: dict[d.Point, d.Point] = {}
        seen = {(state.player.x, state.player.y)}
        blocked = build_blocked_cells(state, state.player)
        target_set = set(target_cells)
        while queue:
            _, current = heapq.heappop(queue)
            if current in target_set:
                path = [current]
                while path[-1] != (state.player.x, state.player.y):
                    path.append(previous[path[-1]])
                path.reverse()
                if len(path) >= 2:
                    nx, ny = path[1]
                    return nx - state.player.x, ny - state.player.y
                break
            cx, cy = current
            for dx, dy in ((0, -1), (-1, 0), (1, 0), (0, 1)):
                nx, ny = cx + dx, cy + dy
                next_point = (nx, ny)
                if not (0 <= nx < d.FIELD_WIDTH and 0 <= ny < d.FIELD_HEIGHT):
                    continue
                if next_point in seen or next_point in blocked:
                    continue
                if state.field[ny][nx] not in (" ", d.CHAR_CALTROP):
                    continue
                seen.add(next_point)
                previous[next_point] = current
                heapq.heappush(queue, (len(previous), next_point))

    for dx, dy in ((0, -1), (-1, 0), (1, 0), (0, 1)):
        nx, ny = state.player.x + dx, state.player.y + dy
        if not (0 <= nx < d.FIELD_WIDTH and 0 <= ny < d.FIELD_HEIGHT):
            continue
        if state.field[ny][nx] not in (" ", d.CHAR_CALTROP):
            continue
        occupied = any(
            entity is not state.player and (entity.x, entity.y) == (nx, ny) and isinstance(entity, (d.Monster, d.Companion))
            for entity in state.entities
        )
        if not occupied:
            return dx, dy
    return (0, 0)


def choose_move_direction(state: SimulationState) -> d.Point:
    if state.planned_target is not None:
        if state.planned_target not in state.entities or not is_target_entity(state, state.planned_target):
            state.planned_target = None
        else:
            path = find_path_to_target(state, state.planned_target)
            if path is not None and len(path) >= 2 and len(path) - 1 <= 8:
                nx, ny = path[1]
                return nx - state.player.x, ny - state.player.y
            if abs(state.planned_target.x - state.player.x) + abs(state.planned_target.y - state.player.y) == 1:
                return state.planned_target.x - state.player.x, state.planned_target.y - state.player.y
            state.planned_target = None

    target, next_point = choose_target(state)
    if next_point is not None:
        if target is not None:
            path = find_path_to_target(state, target)
            special_target = isinstance(target, d.Treasure) or (
                isinstance(target, d.Monster)
                and (target.tribe.effect in (d.EFFECT_UNLOCK_TREASURE, d.EFFECT_SPECIAL_EXP) or target.tribe.item)
            )
            if special_target and path is not None and len(path) - 1 <= 8:
                state.planned_target = target
            else:
                state.planned_target = None
        nx, ny = next_point
        return nx - state.player.x, ny - state.player.y
    return choose_wander_direction(state)


def step_simulation(state: SimulationState) -> None:
    if state.ended:
        return
    if state.player.lp <= 0:
        state.ended = True
        state.won = False
        return

    cur_torched = get_torched(state.player, state.torch_radius)
    for y in range(d.FIELD_HEIGHT):
        for x in range(d.FIELD_WIDTH):
            state.torched[y][x] += cur_torched[y][x]

    move_direction = choose_move_direction(state)
    effect, tribes_to_be_respawned, _ = update_entities(
        move_direction,
        state.field,
        state.player,
        state.entities,
        state.encountered_types,
    )
    if state.planned_target is not None and state.planned_target not in state.entities:
        state.planned_target = None

    for tribe_char in tribes_to_be_respawned:
        state.respawn_queue[tribe_char] += 1

    if state.hours % d.MONSTER_RESPAWN_INTERVAL == 0:
        for tribe_char in list(state.respawn_queue.keys()):
            if state.respawn_queue[tribe_char] > 0:
                respawn_entity(d.CHAR_TO_TRIBE[tribe_char], state.entities, state.field, state.torched)
                state.respawn_queue[tribe_char] -= 1

    if effect == d.EFFECT_GOT_TREASURE:
        state.won = True
        state.ended = True
        return

    state.hours += 1
    state.player.lp -= 1
    if state.player.lp <= 0:
        state.ended = True


def simulate_game(stage_num: int, seed: int, max_steps: int = 10_000) -> SimulationResult:
    state = build_simulation(stage_num, seed)
    steps = 0
    while not state.ended and steps < max_steps:
        step_simulation(state)
        steps += 1
    return SimulationResult(
        seed=seed,
        won=state.won,
        hours=state.hours,
        lp=state.player.lp,
        level=state.player.level,
    )


def summarize_results(results: Iterable[SimulationResult]) -> dict[str, float | int]:
    items = list(results)
    wins = sum(1 for result in items if result.won)
    total = len(items)
    avg_hours = sum(result.hours for result in items) / total if total else 0.0
    avg_level = sum(result.level for result in items) / total if total else 0.0
    avg_lp = sum(result.lp for result in items) / total if total else 0.0
    return {
        "games": total,
        "wins": wins,
        "win_rate": wins / total if total else 0.0,
        "avg_hours": avg_hours,
        "avg_level": avg_level,
        "avg_lp": avg_lp,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run heuristic solver simulations for ARLQ.")
    parser.add_argument("--stage", type=int, default=1, help="Stage number to simulate.")
    parser.add_argument("--games", type=int, default=100, help="Number of games to simulate.")
    parser.add_argument("--seed-start", type=int, default=1, help="First seed value to use.")
    parser.add_argument("--max-steps", type=int, default=10_000, help="Maximum turns per game.")
    parser.add_argument(
        "--print-winning-seeds",
        action="store_true",
        help="Print the seed values of winning runs after the summary.",
    )
    parser.add_argument("-F", "--large-field", action="store_true", help="Large field.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-T", "--large-torch", action="store_true", help="Large torch.")
    group.add_argument("-t", "--small-torch", action="store_true", help="Small torch.")
    parser.add_argument("-n", "--narrower-corridors", action="store_true", help="Narrower corridors.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    apply_runtime_flags(args)

    results = [
        simulate_game(args.stage, args.seed_start + game_index, max_steps=args.max_steps)
        for game_index in range(args.games)
    ]
    summary = summarize_results(results)

    print(f"stage={args.stage} games={summary['games']} wins={summary['wins']} win_rate={summary['win_rate']:.3f}")
    print(
        f"avg_hours={summary['avg_hours']:.1f} avg_level={summary['avg_level']:.1f} avg_lp={summary['avg_lp']:.1f}"
    )
    if args.print_winning_seeds:
        winning_seeds = [str(result.seed) for result in results if result.won]
        print("")
        print("[winning seeds]")
        if winning_seeds:
            print(" ".join(winning_seeds))
        else:
            print("(none)")


if __name__ == "__main__":
    main()
