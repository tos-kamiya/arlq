from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
from dataclasses import dataclass
import heapq

from . import defs as d
from .arlq import respawn_entity, update_entities
from .solver import apply_runtime_flags, build_simulation


@dataclass(frozen=True)
class Candidate:
    entity_index: int
    entity_id: int
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


@dataclass
class BeamState:
    state: object
    first_choice: int | None = None
    depth: int = 0
    choice_history: tuple[int, ...] = ()


LP_SAFETY_MARGIN = 1
MANHATTAN_CANDIDATE_POOL = 10


def ensure_branch_metadata(state) -> None:
    if not hasattr(state, "lost_monsters"):
        state.lost_monsters = set()
    if not hasattr(state, "next_entity_id"):
        state.next_entity_id = 1
    if not hasattr(state, "entity_id_to_label"):
        state.entity_id_to_label = {}
    for entity in state.entities:
        if isinstance(entity, d.Player):
            continue
        if not hasattr(entity, "entity_id"):
            entity.entity_id = state.next_entity_id
            state.next_entity_id += 1
        state.entity_id_to_label[entity.entity_id] = entity_label(entity)


def structural_state_key(state) -> tuple[int, int, str | None, int, tuple[str, ...], frozenset[str]]:
    return (
        state.player.x,
        state.player.y,
        state.player.item,
        getattr(state.player, "item_uses", 0),
        tuple("".join(row) for row in state.field),
        frozenset(state.encountered_types),
    )


PathCache = dict[
    tuple[int, int, str | None, int, tuple[str, ...], frozenset[str], tuple[d.Point, ...]],
    dict[d.Point, tuple[d.Point, ...]],
]


def path_query_key(
    state,
    goals: tuple[d.Point, ...],
) -> tuple[int, int, str | None, int, tuple[str, ...], frozenset[str], tuple[d.Point, ...]]:
    return (
        state.player.x,
        state.player.y,
        state.player.item,
        getattr(state.player, "item_uses", 0),
        tuple("".join(row) for row in state.field),
        frozenset(state.encountered_types),
        goals,
    )


def build_paths_from_source(
    state,
    source: d.Point,
    goals: set[d.Point],
) -> dict[d.Point, tuple[d.Point, ...]]:
    sword_uses = (
        getattr(state.player, "item_uses", 0)
        if state.player.item in (d.ITEM_SWORD_X1_5, d.ITEM_SWORD_CURSED)
        else 0
    )
    start_state = (source, sword_uses)
    queue: list[tuple[int, d.Point, int]] = [(0, source, sword_uses)]
    best_cost_by_state: dict[tuple[d.Point, int], int] = {start_state: 0}
    previous: dict[tuple[d.Point, int], tuple[d.Point, int]] = {}

    while queue:
        cost, current, breaks_left = heapq.heappop(queue)
        state_key = (current, breaks_left)
        if cost != best_cost_by_state.get(state_key):
            continue
        cx, cy = current
        for dx, dy in ((0, -1), (-1, 0), (1, 0), (0, 1)):
            nx, ny = cx + dx, cy + dy
            if not (0 <= nx < d.FIELD_WIDTH and 0 <= ny < d.FIELD_HEIGHT):
                continue
            tile = state.field[ny][nx]
            next_breaks_left = breaks_left
            if tile not in (" ", d.CHAR_CALTROP):
                if tile != d.WALL_CHAR or breaks_left <= 0:
                    continue
                next_breaks_left -= 1
            next_point = (nx, ny)
            step_cost = 4 if tile == d.CHAR_CALTROP else 1
            next_cost = cost + step_cost
            next_state_key = (next_point, next_breaks_left)
            if next_cost >= best_cost_by_state.get(next_state_key, 10**9):
                continue
            best_cost_by_state[next_state_key] = next_cost
            previous[next_state_key] = state_key
            heapq.heappush(queue, (next_cost, next_point, next_breaks_left))

    paths: dict[d.Point, tuple[d.Point, ...]] = {}
    for goal in goals:
        goal_states = [state_key for state_key in best_cost_by_state if state_key[0] == goal]
        if not goal_states:
            continue
        goal_state = min(goal_states, key=lambda state_key: best_cost_by_state[state_key])
        path_states = [goal_state]
        while path_states[-1][0] != source:
            path_states.append(previous[path_states[-1]])
        path = tuple(point for point, _breaks_left in reversed(path_states))
        paths[goal] = path
    return paths


def get_paths_from_current(
    state,
    goals: tuple[d.Point, ...],
    cache: PathCache,
) -> dict[d.Point, tuple[d.Point, ...]]:
    key = path_query_key(state, goals)
    if key in cache:
        return cache[key]
    source = (state.player.x, state.player.y)
    paths = build_paths_from_source(state, source, set(goals))
    cache[key] = paths
    return paths


def find_path_ignoring_entities(
    state,
    entity: d.Entity,
    cache: PathCache,
) -> list[d.Point] | None:
    goal = (entity.x, entity.y)
    paths = get_paths_from_current(state, (goal,), cache)
    if goal not in paths:
        return None
    return list(paths[goal])


def entity_label(entity: d.Entity) -> str:
    if isinstance(entity, d.Monster):
        return f"monster:{entity.tribe.char}"
    if isinstance(entity, d.Companion):
        return f"companion:{entity.tribe.char}"
    if isinstance(entity, d.Treasure):
        return "treasure:T"
    return "unknown"


def entity_label_by_id(state, entity_id: int) -> str:
    ensure_branch_metadata(state)
    for entity in state.entities:
        if getattr(entity, "entity_id", None) == entity_id:
            return f"{entity_label(entity)}#{entity_id}"
    if entity_id in state.entity_id_to_label:
        return f"{state.entity_id_to_label[entity_id]}#{entity_id}"
    return f"unknown#{entity_id}"


def monster_signature(entity: d.Monster) -> tuple[str, int, int]:
    return (entity.tribe.char, entity.x, entity.y)


def is_branch_target(state, entity: d.Entity) -> bool:
    ensure_branch_metadata(state)
    if entity is state.player:
        return False
    if isinstance(entity, d.Monster):
        if d.player_attack_by_level(state.player) < entity.tribe.level and monster_signature(entity) in state.lost_monsters:
            return False
        return True
    if isinstance(entity, d.Companion):
        return True
    if isinstance(entity, d.Treasure):
        return entity.encounter_type in state.encountered_types
    return False


def rank_nearest_targets(state, limit: int, path_cache: PathCache, forbidden_chars: frozenset[str] = frozenset()) -> list[Candidate]:
    ensure_branch_metadata(state)
    preliminary: list[tuple[int, int, int, d.Entity]] = []
    for index, entity in enumerate(state.entities):
        if not is_branch_target(state, entity):
            continue
        if isinstance(entity, d.Monster) and entity.tribe.char in forbidden_chars:
            continue
        manhattan = abs(entity.x - state.player.x) + abs(entity.y - state.player.y)
        preliminary.append((manhattan, getattr(entity, "entity_id", 10**9), index, entity))

    preliminary.sort(key=lambda item: (item[0], item[1], item[2]))
    shortlist = preliminary[:MANHATTAN_CANDIDATE_POOL]
    goals = tuple((entity.x, entity.y) for _manhattan, _entity_id, _index, entity in shortlist)
    paths = get_paths_from_current(state, goals, path_cache)

    ranked: list[Candidate] = []
    for _manhattan, _entity_id, index, entity in shortlist:
        path = paths.get((entity.x, entity.y))
        if path is None:
            continue
        distance = len(path) - 1
        if distance + LP_SAFETY_MARGIN >= state.player.lp:
            continue
        ranked.append(Candidate(index, entity.entity_id, distance))
    ranked.sort(key=lambda item: (item.distance, item.entity_id, item.entity_index))
    return ranked[:limit]


def apply_move(state, move_direction: d.Point) -> None:
    ensure_branch_metadata(state)
    target_x = state.player.x + move_direction[0]
    target_y = state.player.y + move_direction[1]
    losing_monster_signature = None
    for entity in state.entities:
        if (
            isinstance(entity, d.Monster)
            and (entity.x, entity.y) == (target_x, target_y)
            and d.player_attack_by_level(state.player) < entity.tribe.level
        ):
            losing_monster_signature = monster_signature(entity)
            break

    effect, tribes_to_be_respawned, _, _ = update_entities(
        move_direction,
        state.field,
        state.player,
        state.entities,
        state.encountered_types,
    )
    if losing_monster_signature is not None:
        state.lost_monsters.add(losing_monster_signature)

    for tribe_char in tribes_to_be_respawned:
        state.respawn_queue[tribe_char] += 1

    if state.hours % d.MONSTER_RESPAWN_INTERVAL == 0:
        for tribe_char in list(state.respawn_queue.keys()):
            if state.respawn_queue[tribe_char] > 0:
                respawn_entity(d.CHAR_TO_TRIBE[tribe_char], state.entities, state.field, state.torched)
                state.respawn_queue[tribe_char] -= 1
    ensure_branch_metadata(state)

    if effect == d.EFFECT_GOT_TREASURE:
        state.won = True
        state.ended = True
        return

    state.hours += 1
    state.player.lp -= 1
    if state.player.lp <= 0:
        state.ended = True


def advance_until_contact(state, entity_index: int, max_travel_steps: int, path_cache: PathCache) -> bool:
    ensure_branch_metadata(state)
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
    path_cache: PathCache,
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


def load_seed_file(path: str) -> list[int]:
    seeds: list[int] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            for token in stripped.replace(",", " ").split():
                seeds.append(int(token))
    return seeds


def evaluate_state(beam_state: BeamState, lp_weight: float, level_weight: float) -> float:
    state = beam_state.state
    return state.player.lp * lp_weight + state.player.level * level_weight


def beam_state_key(beam_state: BeamState) -> tuple:
    state = beam_state.state
    return (
        state.player.x,
        state.player.y,
        state.player.lp,
        state.player.level,
        state.player.item,
        tuple("".join(row) for row in state.field),
        frozenset(state.encountered_types),
        tuple(sorted(getattr(state, "lost_monsters", set()))),
        beam_state.first_choice,
    )


def dedupe_beam(beam: list[BeamState], lp_weight: float, level_weight: float) -> list[BeamState]:
    best_by_key: dict[tuple, BeamState] = {}
    for beam_state in beam:
        key = beam_state_key(beam_state)
        if key not in best_by_key or evaluate_state(beam_state, lp_weight, level_weight) > evaluate_state(
            best_by_key[key], lp_weight, level_weight
        ):
            best_by_key[key] = beam_state
    return list(best_by_key.values())


def select_top_beam(
    beam: list[BeamState],
    beam_width: int,
    lp_weight: float,
    level_weight: float,
) -> list[BeamState]:
    deduped = dedupe_beam(beam, lp_weight, level_weight)
    deduped.sort(
        key=lambda beam_state: (
            evaluate_state(beam_state, lp_weight, level_weight),
            beam_state.state.player.level,
            beam_state.state.player.lp,
        ),
        reverse=True,
    )
    return deduped[:beam_width]


def analyze_seed_with_beam(
    *,
    stage_num: int,
    seed: int,
    top_k: int,
    max_depth: int,
    beam_width: int,
    node_budget: int,
    max_travel_steps: int,
    lp_weight: float,
    level_weight: float,
    forbidden_chars: frozenset[str] = frozenset(),
) -> tuple[dict[str, AggregateRow], AnalysisStats, int, list[tuple[int, ...]]]:
    path_cache: PathCache = {}
    initial_state = build_simulation(stage_num, seed)
    ensure_branch_metadata(initial_state)
    beam: list[BeamState] = [BeamState(state=initial_state)]
    budget = SearchBudget(nodes_left=node_budget)
    rows: dict[str, AggregateRow] = defaultdict(AggregateRow)
    stats = AnalysisStats()
    winning_histories: list[tuple[int, ...]] = []

    for depth in range(max_depth):
        if not beam or budget.nodes_left <= 0:
            break
        next_beam: list[BeamState] = []
        for beam_state in beam:
            if budget.nodes_left <= 0:
                break
            state = beam_state.state
            if state.won:
                label = entity_label_by_id(state, beam_state.first_choice) if beam_state.first_choice is not None else "(initial)"
                rows[label].add(AnalysisStats(leaves=1, wins=1))
                stats.leaves += 1
                stats.wins += 1
                continue
            if state.ended:
                label = entity_label_by_id(state, beam_state.first_choice) if beam_state.first_choice is not None else "(initial)"
                rows[label].add(AnalysisStats(leaves=1, losses=1))
                stats.leaves += 1
                stats.losses += 1
                continue

            candidates = rank_nearest_targets(state, top_k, path_cache, forbidden_chars)
            if not candidates:
                label = entity_label_by_id(state, beam_state.first_choice) if beam_state.first_choice is not None else "(initial)"
                rows[label].add(AnalysisStats(leaves=1, stalled=1))
                stats.leaves += 1
                stats.stalled += 1
                continue

            for candidate in candidates:
                if budget.nodes_left <= 0:
                    break
                budget.nodes_left -= 1
                child_state = deepcopy(state)
                ensure_branch_metadata(child_state)
                contacted = advance_until_contact(child_state, candidate.entity_index, max_travel_steps, path_cache)
                child = BeamState(
                    state=child_state,
                    first_choice=beam_state.first_choice or candidate.entity_id,
                    depth=depth + 1,
                    choice_history=beam_state.choice_history + (candidate.entity_id,),
                )
                if not contacted:
                    label = entity_label_by_id(child_state, child.first_choice) if child.first_choice is not None else "(initial)"
                    rows[label].add(AnalysisStats(leaves=1, stalled=1))
                    stats.leaves += 1
                    stats.stalled += 1
                elif child_state.won:
                    label = entity_label_by_id(child_state, child.first_choice) if child.first_choice is not None else "(initial)"
                    rows[label].add(AnalysisStats(leaves=1, wins=1))
                    stats.leaves += 1
                    stats.wins += 1
                    winning_histories.append(child.choice_history)
                elif child_state.ended:
                    label = entity_label_by_id(child_state, child.first_choice) if child.first_choice is not None else "(initial)"
                    rows[label].add(AnalysisStats(leaves=1, losses=1))
                    stats.leaves += 1
                    stats.losses += 1
                else:
                    next_beam.append(child)

        beam = select_top_beam(next_beam, beam_width, lp_weight, level_weight)

    if beam:
        for beam_state in beam:
            label = entity_label_by_id(beam_state.state, beam_state.first_choice) if beam_state.first_choice is not None else "(initial)"
            rows[label].add(AnalysisStats(leaves=1, stalled=1))
            stats.leaves += 1
            stats.stalled += 1

    return rows, stats, budget.nodes_left, winning_histories


def find_candidate_by_entity_id(candidates: list[Candidate], entity_id: int) -> Candidate | None:
    for candidate in candidates:
        if candidate.entity_id == entity_id:
            return candidate
    return None


def summarize_priority_rows(rows: dict[str, tuple[int, int]]) -> list[str]:
    ordered = sorted(
        rows.items(),
        key=lambda item: (
            ((item[1][0] - item[1][1]) / (item[1][0] + item[1][1])) if (item[1][0] + item[1][1]) else -2.0,
            item[1][0] + item[1][1],
            item[0],
        ),
        reverse=True,
    )
    lines: list[str] = []
    for label, (wins, losses) in ordered:
        total = wins + losses
        score = (wins - losses) / total if total else 0.0
        lines.append(f"{label:14s} preferred={wins:6d} deferred={losses:6d} preference_score={score:.3f}")
    return lines


def summarize_rank_rows(rank_rows: dict[int, int]) -> list[str]:
    total = sum(rank_rows.values())
    lines: list[str] = []
    for rank in sorted(rank_rows):
        count = rank_rows[rank]
        share = count / total if total else 0.0
        lines.append(f"rank={rank:2d} chosen={count:6d} share={share:.3f}")
    return lines


def base_label_with_id(label_with_id: str) -> str:
    return label_with_id.split("#", 1)[0]


def replay_win_history(
    stage_num: int,
    seed: int,
    history: tuple[int, ...],
    top_k: int,
    max_travel_steps: int,
    path_cache: PathCache,
    preference_rows: dict[str, list[int]],
    rank_rows: dict[int, int],
    forbidden_chars: frozenset[str] = frozenset(),
) -> None:
    state = build_simulation(stage_num, seed)
    ensure_branch_metadata(state)
    for entity_id in history:
        candidates = rank_nearest_targets(state, top_k, path_cache, forbidden_chars)
        chosen = find_candidate_by_entity_id(candidates, entity_id)
        if chosen is None:
            break
        chosen_entity = state.entities[chosen.entity_index]
        if isinstance(chosen_entity, d.Monster):
            monster_candidates = [
                candidate
                for candidate in candidates
                if isinstance(state.entities[candidate.entity_index], d.Monster)
            ]
            for rank_index, candidate in enumerate(monster_candidates, start=1):
                if candidate.entity_id == entity_id:
                    rank_rows[rank_index] += 1
                    break
            chosen_label = base_label_with_id(entity_label_by_id(state, entity_id))
            for candidate in candidates:
                candidate_entity = state.entities[candidate.entity_index]
                if not isinstance(candidate_entity, d.Monster) or candidate.entity_id == entity_id:
                    continue
                candidate_label = base_label_with_id(entity_label_by_id(state, candidate.entity_id))
                preference_rows[chosen_label][0] += 1
                preference_rows[candidate_label][1] += 1
        advance_until_contact(state, chosen.entity_index, max_travel_steps, path_cache)
        if state.ended:
            break


def analyze_single_seed(task: tuple[int, int, int, int, int, int, float, float, bool, bool, bool, bool, tuple[str, ...]]):
    (
        stage_num,
        seed,
        top_k,
        max_depth,
        beam_width,
        node_budget,
        max_travel_steps,
        lp_weight,
        level_weight,
        large_field,
        large_torch,
        small_torch,
        narrower_corridors,
        forbidden_chars_tuple,
    ) = task
    forbidden_chars = frozenset(forbidden_chars_tuple)

    parser = build_parser()
    args = parser.parse_args([])
    args.stage = stage_num
    args.large_field = large_field
    args.large_torch = large_torch
    args.small_torch = small_torch
    args.narrower_corridors = narrower_corridors
    apply_runtime_flags(args)

    _, stats, nodes_left, winning_histories = analyze_seed_with_beam(
        stage_num=stage_num,
        seed=seed,
        top_k=top_k,
        max_depth=max_depth,
        beam_width=beam_width,
        node_budget=node_budget,
        max_travel_steps=max_travel_steps,
        lp_weight=lp_weight,
        level_weight=level_weight,
        forbidden_chars=forbidden_chars,
    )

    preference_rows: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    rank_rows: dict[int, int] = defaultdict(int)
    replay_path_cache: PathCache = {}
    for history in winning_histories:
        replay_win_history(
            stage_num,
            seed,
            history,
            top_k,
            max_travel_steps,
            replay_path_cache,
            preference_rows,
            rank_rows,
            forbidden_chars,
        )

    return {
        "seed": seed,
        "stats": stats,
        "nodes_left": nodes_left,
        "preference_rows": dict(preference_rows),
        "rank_rows": dict(rank_rows),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze branch choices for ARLQ with beam search.")
    parser.add_argument("--stage", type=int, default=1, help="Stage number to analyze.")
    parser.add_argument("--seeds", type=int, default=10, help="Number of seeds to analyze.")
    parser.add_argument("--seed-start", type=int, default=1, help="First seed value to use.")
    parser.add_argument(
        "--seed-file",
        type=str,
        help="Path to a file containing explicit seed values. Whitespace and commas are accepted.",
    )
    parser.add_argument("--top-k", type=int, default=5, help="Expand the nearest K targets from each beam state.")
    parser.add_argument("--max-depth", type=int, default=12, help="Maximum beam-search depth.")
    parser.add_argument("--beam-width", type=int, default=64, help="Maximum number of states kept at each depth.")
    parser.add_argument(
        "--node-budget",
        type=int,
        default=5000,
        help="Maximum expanded child states per seed to keep the search tractable.",
    )
    parser.add_argument(
        "--max-travel-steps",
        type=int,
        default=500,
        help="Maximum movement steps allowed while advancing to a chosen target.",
    )
    parser.add_argument("--lp-weight", type=float, default=1.0, help="Weight for LP in the pool evaluation score.")
    parser.add_argument("--level-weight", type=float, default=10.0, help="Weight for level in the pool evaluation score.")
    parser.add_argument("--jobs", type=int, default=1, help="Number of worker processes to use across seeds.")
    parser.add_argument(
        "--forbid-char",
        action="append",
        default=[],
        help="Monster char to exclude from candidate choices. Repeat to forbid multiple chars.",
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
    seed_values = load_seed_file(args.seed_file) if args.seed_file else list(
        range(args.seed_start, args.seed_start + args.seeds)
    )

    preference_rows: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    rank_rows: dict[int, int] = defaultdict(int)
    seed_summaries: list[str] = []
    aggregate_terminal = Counter()
    tasks = [
        (
            args.stage,
            seed,
            args.top_k,
            args.max_depth,
            args.beam_width,
            args.node_budget,
            args.max_travel_steps,
            args.lp_weight,
            args.level_weight,
            args.large_field,
            args.large_torch,
            args.small_torch,
            args.narrower_corridors,
            tuple(args.forbid_char),
        )
        for seed in seed_values
    ]

    completed = 0
    if args.jobs <= 1:
        results = [analyze_single_seed(task) for task in tasks]
        iterator = results
    else:
        executor = ProcessPoolExecutor(max_workers=args.jobs)
        iterator = as_completed(executor.submit(analyze_single_seed, task) for task in tasks)

    try:
        for item in iterator:
            result = item.result() if args.jobs > 1 else item
            seed = result["seed"]
            stats = result["stats"]
            nodes_left = result["nodes_left"]
            for label, counts in result["preference_rows"].items():
                preference_rows[label][0] += counts[0]
                preference_rows[label][1] += counts[1]
            for rank, count in result["rank_rows"].items():
                rank_rows[rank] += count
            aggregate_terminal["leaves"] += stats.leaves
            aggregate_terminal["wins"] += stats.wins
            aggregate_terminal["losses"] += stats.losses
            aggregate_terminal["stalled"] += stats.stalled
            seed_summaries.append(
                f"seed={seed} leaves={stats.leaves} wins={stats.wins} "
                f"losses={stats.losses} stalled={stats.stalled} nodes_left={nodes_left}"
            )
            completed += 1
            progress_ratio = completed / len(seed_values) if seed_values else 1.0
            print(
                f"[progress] seeds={completed}/{len(seed_values)} "
                f"({progress_ratio:.0%}) current_seed={seed} "
                f"wins={aggregate_terminal['wins']} leaves={aggregate_terminal['leaves']}"
            )
    finally:
        if args.jobs > 1:
            executor.shutdown()

    seed_summaries.sort(key=lambda line: int(line.split()[0].split("=")[1]))

    total_leaves = aggregate_terminal["leaves"]
    total_win_rate = aggregate_terminal["wins"] / total_leaves if total_leaves else 0.0

    print(
        f"stage={args.stage} seeds={len(seed_values)} top_k={args.top_k} max_depth={args.max_depth} "
        f"beam_width={args.beam_width} node_budget={args.node_budget}"
    )
    if args.forbid_char:
        print(f"forbidden_chars={' '.join(args.forbid_char)}")
    print(
        f"aggregate leaves={aggregate_terminal['leaves']} wins={aggregate_terminal['wins']} "
        f"losses={aggregate_terminal['losses']} stalled={aggregate_terminal['stalled']} "
        f"win_rate={total_win_rate:.3f}"
    )
    print("")
    print("[winning path monster priority]")
    for line in summarize_priority_rows({label: (counts[0], counts[1]) for label, counts in preference_rows.items()}):
        print(line)
    print("")
    print("[winning path monster choice rank]")
    for line in summarize_rank_rows(rank_rows):
        print(line)
    print("")
    print("[seed summaries]")
    for line in seed_summaries:
        print(line)


if __name__ == "__main__":
    main()
