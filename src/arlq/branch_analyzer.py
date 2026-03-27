from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import dataclass
import heapq

from . import defs as d
from .arlq import respawn_entity, update_entities
from .solver import apply_runtime_flags, build_simulation


@dataclass(frozen=True)
class Candidate:
    entity_index: int
    label: str
    distance: int


@dataclass
class AnalysisStats:
    leaves: int = 0
    wins: int = 0
    losses: int = 0
    stalled: int = 0


@dataclass
class AggregateRow:
    leaves: int = 0
    wins: int = 0
    losses: int = 0
    stalled: int = 0

    def add(self, stats: AnalysisStats) -> None:
        self.leaves += stats.leaves
        self.wins += stats.wins
        self.losses += stats.losses
        self.stalled += stats.stalled


@dataclass
class SearchBudget:
    nodes_left: int


LP_SAFETY_MARGIN = 1


def structural_state_key(state) -> tuple[int, int, tuple[str, ...], frozenset[str]]:
    return (
        state.player.x,
        state.player.y,
        tuple("".join(row) for row in state.field),
        frozenset(state.encountered_types),
    )


def get_distance_map(state, cache: dict[tuple[int, int, tuple[str, ...], frozenset[str]], tuple[dict[d.Point, int], dict[d.Point, d.Point]]]):
    key = structural_state_key(state)
    if key in cache:
        return cache[key]

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
            if state.field[ny][nx] not in (" ", d.CHAR_CALTROP):
                continue
            next_point = (nx, ny)
            step_cost = 4 if state.field[ny][nx] == d.CHAR_CALTROP else 1
            next_cost = cost + step_cost
            if next_cost >= best_cost.get(next_point, 10**9):
                continue
            best_cost[next_point] = next_cost
            previous[next_point] = current
            heapq.heappush(queue, (next_cost, next_point))

    cache[key] = (best_cost, previous)
    return best_cost, previous


def reconstruct_path(previous: dict[d.Point, d.Point], start: d.Point, goal: d.Point) -> list[d.Point]:
    path = [goal]
    while path[-1] != start:
        path.append(previous[path[-1]])
    path.reverse()
    return path


def find_path_ignoring_entities(
    state,
    entity: d.Entity,
    cache: dict[tuple[int, int, tuple[str, ...], frozenset[str]], tuple[dict[d.Point, int], dict[d.Point, d.Point]]],
) -> list[d.Point] | None:
    best_cost, previous = get_distance_map(state, cache)
    start = (state.player.x, state.player.y)
    goal = (entity.x, entity.y)
    if goal not in best_cost:
        return None
    return reconstruct_path(previous, start, goal)


def entity_label(entity: d.Entity) -> str:
    if isinstance(entity, d.Monster):
        return f"monster:{entity.tribe.char}"
    if isinstance(entity, d.Companion):
        return f"companion:{entity.tribe.char}"
    if isinstance(entity, d.Treasure):
        return "treasure:T"
    return "unknown"


def is_branch_target(state, entity: d.Entity) -> bool:
    if entity is state.player:
        return False
    if isinstance(entity, d.Monster):
        return True
    if isinstance(entity, d.Companion):
        return True
    if isinstance(entity, d.Treasure):
        return entity.encounter_type in state.encountered_types
    return False


def rank_nearest_targets(state, limit: int, path_cache) -> list[Candidate]:
    ranked: list[Candidate] = []
    for index, entity in enumerate(state.entities):
        if not is_branch_target(state, entity):
            continue
        path = find_path_ignoring_entities(state, entity, path_cache)
        if path is None:
            continue
        distance = len(path) - 1
        if distance + LP_SAFETY_MARGIN >= state.player.lp:
            continue
        ranked.append(Candidate(index, entity_label(entity), distance))
    ranked.sort(key=lambda item: (item.distance, item.label, item.entity_index))
    return ranked[:limit]


def apply_move(state, move_direction: d.Point) -> None:
    effect, tribes_to_be_respawned, _ = update_entities(
        move_direction,
        state.field,
        state.player,
        state.entities,
        state.encountered_types,
    )

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


def advance_until_contact(state, entity_index: int, max_travel_steps: int, path_cache) -> bool:
    travel_steps = 0
    while not state.ended and travel_steps < max_travel_steps:
        if entity_index >= len(state.entities):
            return False
        target = state.entities[entity_index]
        if not is_branch_target(state, target):
            return False
        path = find_path_ignoring_entities(state, target, path_cache)
        if path is None or len(path) < 2:
            return False
        next_x, next_y = path[1]
        reaches_target = (next_x, next_y) == (target.x, target.y)
        apply_move(state, (next_x - state.player.x, next_y - state.player.y))
        travel_steps += 1
        if state.player.lp <= 0:
            state.ended = True
        if reaches_target:
            return True
    return False


def terminal_stats(state, stalled: bool = False) -> AnalysisStats:
    if stalled:
        return AnalysisStats(leaves=1, stalled=1)
    if state.won:
        return AnalysisStats(leaves=1, wins=1)
    return AnalysisStats(leaves=1, losses=1)


def merge_stats(items: list[AnalysisStats]) -> AnalysisStats:
    merged = AnalysisStats()
    for item in items:
        merged.leaves += item.leaves
        merged.wins += item.wins
        merged.losses += item.losses
        merged.stalled += item.stalled
    return merged


def explore_tree(
    state,
    *,
    top_k: int,
    max_depth: int,
    max_travel_steps: int,
    budget: SearchBudget,
    overall_rows: dict[str, AggregateRow],
    root_rows: dict[str, AggregateRow],
    path_cache: dict[tuple[int, int, tuple[str, ...], frozenset[str]], tuple[dict[d.Point, int], dict[d.Point, d.Point]]],
    depth: int = 0,
) -> AnalysisStats:
    if state.ended:
        return terminal_stats(state)
    if budget.nodes_left <= 0 or depth >= max_depth:
        return terminal_stats(state, stalled=True)

    candidates = rank_nearest_targets(state, top_k, path_cache)
    if not candidates:
        return terminal_stats(state, stalled=True)

    outcomes: list[AnalysisStats] = []
    for candidate in candidates:
        if budget.nodes_left <= 0:
            break
        budget.nodes_left -= 1
        child_state = deepcopy(state)
        contacted = advance_until_contact(child_state, candidate.entity_index, max_travel_steps, path_cache)
        if contacted:
            child_stats = explore_tree(
                child_state,
                top_k=top_k,
                max_depth=max_depth,
                max_travel_steps=max_travel_steps,
                budget=budget,
                overall_rows=overall_rows,
                root_rows=root_rows,
                path_cache=path_cache,
                depth=depth + 1,
            )
        else:
            child_stats = terminal_stats(child_state, stalled=True)
        overall_rows[candidate.label].add(child_stats)
        if depth == 0:
            root_rows[candidate.label].add(child_stats)
        outcomes.append(child_stats)

    if not outcomes:
        return terminal_stats(state, stalled=True)
    return merge_stats(outcomes)


def summarize_rows(rows: dict[str, AggregateRow]) -> list[str]:
    ordered = sorted(
        rows.items(),
        key=lambda item: (
            (item[1].wins / item[1].leaves) if item[1].leaves else -1.0,
            item[1].leaves,
            item[0],
        ),
        reverse=True,
    )
    lines: list[str] = []
    for label, row in ordered:
        win_rate = row.wins / row.leaves if row.leaves else 0.0
        lines.append(
            f"{label:14s} leaves={row.leaves:6d} wins={row.wins:6d} "
            f"losses={row.losses:6d} stalled={row.stalled:6d} win_rate={win_rate:.3f}"
        )
    return lines


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze branch choices for ARLQ with full-map visibility.")
    parser.add_argument("--stage", type=int, default=1, help="Stage number to analyze.")
    parser.add_argument("--seeds", type=int, default=10, help="Number of seeds to analyze.")
    parser.add_argument("--seed-start", type=int, default=1, help="First seed value to use.")
    parser.add_argument("--top-k", type=int, default=5, help="Branch on the nearest K targets.")
    parser.add_argument("--max-depth", type=int, default=12, help="Maximum contact depth per branch.")
    parser.add_argument(
        "--node-budget",
        type=int,
        default=5000,
        help="Maximum expanded branch nodes per seed to keep the search tractable.",
    )
    parser.add_argument(
        "--max-travel-steps",
        type=int,
        default=500,
        help="Maximum movement steps allowed while advancing to a chosen target.",
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

    overall_rows: dict[str, AggregateRow] = defaultdict(AggregateRow)
    root_rows: dict[str, AggregateRow] = defaultdict(AggregateRow)
    seed_summaries: list[str] = []
    aggregate_terminal = Counter()

    for seed in range(args.seed_start, args.seed_start + args.seeds):
        state = build_simulation(args.stage, seed)
        budget = SearchBudget(nodes_left=args.node_budget)
        path_cache: dict[
            tuple[int, int, tuple[str, ...], frozenset[str]],
            tuple[dict[d.Point, int], dict[d.Point, d.Point]],
        ] = {}
        stats = explore_tree(
            state,
            top_k=args.top_k,
            max_depth=args.max_depth,
            max_travel_steps=args.max_travel_steps,
            budget=budget,
            overall_rows=overall_rows,
            root_rows=root_rows,
            path_cache=path_cache,
        )
        aggregate_terminal["leaves"] += stats.leaves
        aggregate_terminal["wins"] += stats.wins
        aggregate_terminal["losses"] += stats.losses
        aggregate_terminal["stalled"] += stats.stalled
        seed_summaries.append(
            f"seed={seed} leaves={stats.leaves} wins={stats.wins} "
            f"losses={stats.losses} stalled={stats.stalled} nodes_left={budget.nodes_left}"
        )

    total_leaves = aggregate_terminal["leaves"]
    total_win_rate = aggregate_terminal["wins"] / total_leaves if total_leaves else 0.0

    print(
        f"stage={args.stage} seeds={args.seeds} top_k={args.top_k} max_depth={args.max_depth} "
        f"node_budget={args.node_budget}"
    )
    print(
        f"aggregate leaves={aggregate_terminal['leaves']} wins={aggregate_terminal['wins']} "
        f"losses={aggregate_terminal['losses']} stalled={aggregate_terminal['stalled']} "
        f"win_rate={total_win_rate:.3f}"
    )
    print("")
    print("[root choice stats]")
    for line in summarize_rows(root_rows):
        print(line)
    print("")
    print("[all choice stats]")
    for line in summarize_rows(overall_rows):
        print(line)
    print("")
    print("[seed summaries]")
    for line in seed_summaries:
        print(line)


if __name__ == "__main__":
    main()
