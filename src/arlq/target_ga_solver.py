"""Genetic solver whose genes are absolute target coordinates."""

from __future__ import annotations

import argparse
import heapq
import random
import sys
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from dataclasses import dataclass

from . import defs as d
from .ga_solver import (
    LEVEL_MILESTONE_REWARDS,
    SEGMENT_MOVE_RATE,
    STARVATION_PENALTY,
    _lp_reward_value,
    _worker_init,
    apply_ga_move,
)
from .solver import apply_runtime_flags, build_simulation
from .utils import rand

Point = tuple[int, int]
TARGETABLE = (d.Monster, d.Treasure)
STEP_PENALTY = 2


@dataclass(frozen=True)
class TargetEvaluation:
    score: float
    won: bool
    df_defeated: bool
    steps: int
    lp: int
    level: int
    targets: tuple[Point, ...]
    moves: str


@dataclass
class _TargetEvaluationCheckpoint:
    state: object
    checkpoint: Point
    target_index: int
    spawned_targets: tuple[Point, ...]
    seen_spawned: frozenset[Point]
    score: float
    steps: int
    move_log: str
    rand_value: int
    df_defeated_with_sword: bool
    df_defeat_level: int | None


def _walkable(state, point: Point, can_break_walls: bool) -> int | None:
    x, y = point
    tile = state.field[y][x]
    if tile == " ":
        return 1
    if tile == d.CHAR_CALTROP:
        return 4
    if can_break_walls and tile == d.WALL_CHAR:
        return 1
    return None


def find_min_cost_path(state, target: Point) -> list[str] | None:
    """Find a terrain-only path, or None if it is too costly for current LP."""
    start = (state.player.x, state.player.y)
    can_break_walls = state.player.item in (d.ITEM_SWORD_X1_5, d.ITEM_SWORD_CURSED) and state.player.item_uses > 0
    if can_break_walls:
        moves: list[str] = []
        x, y = start
        while x != target[0]:
            moves.append("r" if target[0] > x else "l")
            x += 1 if target[0] > x else -1
        while y != target[1]:
            moves.append("d" if target[1] > y else "u")
            y += 1 if target[1] > y else -1
        return moves if len(moves) < state.player.lp else None

    distances: dict[Point, int] = {target: 0}
    previous: dict[Point, tuple[Point, str]] = {}
    queue: list[tuple[int, Point]] = [(0, target)]
    while queue:
        cost, current = heapq.heappop(queue)
        if cost != distances[current]:
            continue
        if cost >= state.player.lp:
            continue
        for dx, dy, move in ((0, -1, "d"), (0, 1, "u"), (-1, 0, "r"), (1, 0, "l")):
            nx, ny = current[0] + dx, current[1] + dy
            if not (0 <= nx < d.FIELD_WIDTH and 0 <= ny < d.FIELD_HEIGHT):
                continue
            step_cost = _walkable(state, (nx, ny), False)
            if step_cost is None:
                continue
            next_point = (nx, ny)
            next_cost = cost + step_cost
            if next_cost < distances.get(next_point, 10**9) and next_cost < state.player.lp:
                distances[next_point] = next_cost
                previous[next_point] = (current, move)
                heapq.heappush(queue, (next_cost, next_point))

    if start not in distances:
        return None
    moves = []
    point = start
    while point != target:
        next_point, move = previous[point]
        moves.append(move)
        point = next_point
    return moves


def initial_target_pool(stage: int, seed: int) -> list[Point]:
    state = build_simulation(stage, seed)
    return list(dict.fromkeys((entity.x, entity.y) for entity in state.entities if isinstance(entity, TARGETABLE)))


def _make_target_checkpoint(
    state,
    checkpoint: Point,
    target_index: int,
    spawned_targets: list[Point],
    seen_spawned: set[Point],
    score: float,
    steps: int,
    move_log: list[str],
    df_defeated_with_sword: bool,
    df_defeat_level: int | None,
) -> _TargetEvaluationCheckpoint:
    return _TargetEvaluationCheckpoint(
        deepcopy(state),
        deepcopy(checkpoint),
        target_index,
        tuple(spawned_targets),
        frozenset(seen_spawned),
        score,
        steps,
        "".join(move_log),
        rand._value,
        df_defeated_with_sword,
        df_defeat_level,
    )


def _evaluate_target_genome_from_checkpoint(
    genome: tuple[Point, ...],
    stage: int,
    max_steps: int,
    start: _TargetEvaluationCheckpoint,
    save_at: int | None = None,
    no_sword_df: bool = False,
) -> tuple[TargetEvaluation, _TargetEvaluationCheckpoint | None]:
    state = deepcopy(start.state)
    checkpoint = start.checkpoint
    target_index = start.target_index
    spawned_targets = list(start.spawned_targets)
    seen_spawned = set(start.seen_spawned)
    score = start.score
    steps = start.steps
    move_log = list(start.move_log)
    df_defeated_with_sword = start.df_defeated_with_sword
    df_defeat_level = start.df_defeat_level
    rand._value = start.rand_value
    saved = (
        _make_target_checkpoint(
            state,
            checkpoint,
            target_index,
            spawned_targets,
            seen_spawned,
            score,
            steps,
            move_log,
            df_defeated_with_sword,
            df_defeat_level,
        )
        if save_at == target_index
        else None
    )

    # Spawned targets are appended after the requested genome, matching the
    # original target-list behavior.  The requested suffix can therefore be
    # replaced when resuming from a common prefix checkpoint.
    targets = list(genome) + spawned_targets

    while target_index < len(targets) and not state.ended and steps < max_steps:
        target = targets[target_index]
        target_index += 1
        entity = next((item for item in state.entities if (item.x, item.y) == target and isinstance(item, TARGETABLE)), None)
        if entity is None:
            continue
        path = find_min_cost_path(state, target)
        if path is None:
            continue
        for move in path:
            if state.ended or steps >= max_steps:
                break
            before_level = state.player.level
            before_lp = state.player.lp
            before_item = state.player.item
            before_df_defeated = not any(
                isinstance(item, d.Monster) and item.tribe.effect == d.EFFECT_UNLOCK_TREASURE
                for item in state.entities
            )
            before_entities = {
                (item.x, item.y): item for item in state.entities if isinstance(item, d.Monster)
            }
            checkpoint = apply_ga_move(state, move, checkpoint)
            move_log.append(move)
            steps += 1
            score += _lp_reward_value(state.player.lp) - _lp_reward_value(before_lp)
            if not before_df_defeated:
                score += (state.player.level - before_level) * 80
                for level, reward in LEVEL_MILESTONE_REWARDS.items():
                    if before_level < level <= state.player.level:
                        score += reward
            score -= STEP_PENALTY
            after_entities = {
                (item.x, item.y): item for item in state.entities if isinstance(item, d.Monster)
            }
            removed = set(before_entities) - set(after_entities)
            if any(
                before_entities[point].tribe.effect == d.EFFECT_UNLOCK_TREASURE
                and before_item in (d.ITEM_SWORD_X1_5, d.ITEM_SWORD_CURSED)
                for point in removed
            ):
                df_defeated_with_sword = True
            if any(
                before_entities[point].tribe.effect == d.EFFECT_UNLOCK_TREASURE
                for point in removed
            ):
                df_defeat_level = state.player.level
            if target in removed:
                score += 250
                if entity.tribe.effect == d.EFFECT_UNLOCK_TREASURE:
                    score += 100_000
            for point, spawned in after_entities.items():
                if (
                    point not in before_entities
                    and point not in seen_spawned
                    and point not in genome
                    and spawned.tribe.feed > 0
                ):
                    spawned_targets.append(point)
                    targets.append(point)
                    seen_spawned.add(point)
            if (state.player.x, state.player.y) == target and target not in after_entities:
                break

        if save_at == target_index:
            saved = _make_target_checkpoint(
                state,
                checkpoint,
                target_index,
                spawned_targets,
                seen_spawned,
                score,
                steps,
                move_log,
                df_defeated_with_sword,
                df_defeat_level,
            )

    # A sword-assisted D/F defeat is accepted only if the player was above the
    # natural level threshold at the moment of that defeat.  The strict
    # comparison excludes reaching exactly 60 from the D/F defeat level-up.
    invalid_sword_win = no_sword_df and df_defeated_with_sword and (df_defeat_level or 0) <= 60
    valid_win = state.won and not invalid_sword_win
    if invalid_sword_win:
        # Do not let a sword-based clear become a useful stepping stone when
        # searching specifically for a no-sword D/F defeat.
        score = -1_000_000.0 - steps
    elif valid_win:
        route_score = score
        score = 1_000_000 + route_score / max(steps, 1) + state.player.lp * 20
    elif state.player.lp <= 0:
        score -= STARVATION_PENALTY
    else:
        score += state.player.lp
    df_defeated = not any(
        isinstance(item, d.Monster) and item.tribe.effect == d.EFFECT_UNLOCK_TREASURE for item in state.entities
    )
    return (
        TargetEvaluation(
            score,
            valid_win,
            df_defeated,
            steps,
            state.player.lp,
            state.player.level,
            tuple(targets),
            "".join(move_log),
        ),
        saved,
    )


def evaluate_target_genome(
    genome: tuple[Point, ...],
    stage: int,
    seed: int,
    max_steps: int,
    no_sword_df: bool = False,
) -> TargetEvaluation:
    state = build_simulation(stage, seed)
    initial = _make_target_checkpoint(
        state,
        (state.player.x, state.player.y),
        0,
        [],
        set(),
        0.0,
        0,
        [],
        False,
        None,
    )
    result, _ = _evaluate_target_genome_from_checkpoint(
        genome, stage, max_steps, initial, no_sword_df=no_sword_df
    )
    return result


def _target_worker(task: tuple[list[tuple[Point, ...]], int, int, int, bool]):
    genomes, stage, seed, max_steps, no_sword_df = task
    initial_state = build_simulation(stage, seed)
    initial = _make_target_checkpoint(
        initial_state,
        (initial_state.player.x, initial_state.player.y),
        0,
        [],
        set(),
        0.0,
        0,
        [],
        False,
        None,
    )
    previous_genome: tuple[Point, ...] = ()
    previous_checkpoint = initial
    results = []

    for index, genome in enumerate(genomes):
        common = 0
        while common < len(previous_genome) and common < len(genome) and previous_genome[common] == genome[common]:
            common += 1
        if previous_checkpoint.target_index != common:
            common = 0
            previous_checkpoint = initial

        next_common = None
        if index + 1 < len(genomes):
            next_genome = genomes[index + 1]
            next_common = 0
            while next_common < len(genome) and next_common < len(next_genome) and genome[next_common] == next_genome[next_common]:
                next_common += 1

        result, saved = _evaluate_target_genome_from_checkpoint(
            genome,
            stage,
            max_steps,
            previous_checkpoint,
            next_common,
            no_sword_df,
        )
        results.append((genome, result))
        previous_genome = genome if saved is not None else ()
        previous_checkpoint = saved if saved is not None else initial
    return results


def random_genome(pool: list[Point], length: int, rng: random.Random) -> tuple[Point, ...]:
    return tuple(rng.choice(pool) for _ in range(length))


def mutate(genome: tuple[Point, ...], pool: list[Point], rng: random.Random, rate: float) -> tuple[Point, ...]:
    genes = [rng.choice(pool) if rng.random() < rate else gene for gene in genome]
    if len(genes) >= 2 and rng.random() < SEGMENT_MOVE_RATE:
        length = rng.randint(1, min(4, len(genes) - 1))
        start = rng.randrange(len(genes) - length + 1)
        segment = genes[start : start + length]
        del genes[start : start + length]
        insert_at = rng.randrange(len(genes) + 1)
        genes[insert_at:insert_at] = segment
    return tuple(genes)


def run_ga(
    stage: int,
    seed: int,
    target_length: int = 25,
    population_size: int = 100,
    generations: int = 200,
    workers: int = 1,
    max_steps: int = 500,
    random_seed: int | None = None,
    stop_on_win: bool = False,
    no_sword_df: bool = False,
    progress: bool = True,
):
    pool = initial_target_pool(stage, seed)
    if not pool:
        raise ValueError("No target entities were found.")
    rng = random.Random(seed if random_seed is None else random_seed)
    population = [random_genome(pool, target_length, rng) for _ in range(population_size)]
    best = (
        population[0],
        evaluate_target_genome(population[0], stage, seed, max_steps, no_sword_df),
        0,
    )
    runtime_config = (d.TILE_NUM_Y, d.FIELD_HEIGHT, d.TORCH_RADIUS, d.CORRIDOR_H_WIDTH, d.CORRIDOR_V_WIDTH)
    executor = ProcessPoolExecutor(max_workers=workers, initializer=_worker_init, initargs=(runtime_config,)) if workers > 1 else None
    try:
        for generation in range(generations):
            ordered = sorted(population)
            chunk_count = workers if executor is not None else 1
            chunk_size = (len(ordered) + chunk_count - 1) // chunk_count
            chunks = [ordered[i : i + chunk_size] for i in range(0, len(ordered), chunk_size)]
            tasks = [(chunk, stage, seed, max_steps, no_sword_df) for chunk in chunks]
            if executor is None:
                evaluated = [item for task in tasks for item in _target_worker(task)]
            else:
                evaluated = [item for result in executor.map(_target_worker, tasks) for item in result]
            evaluated.sort(key=lambda item: item[1].score, reverse=True)
            if evaluated[0][1].score > best[1].score:
                best = (evaluated[0][0], evaluated[0][1], generation)
            result = best[1]
            if progress:
                print(
                    f"generation={generation + 1}/{generations} best={result.score:.1f} "
                    f"steps={result.steps} lp={result.lp} level={result.level} "
                    f"df_defeated={result.df_defeated} won={result.won}",
                    file=sys.stderr,
                    flush=True,
                )
            if stop_on_win and result.won:
                break
            population = [genome for genome, _ in evaluated[:10]]
            while len(population) < population_size:
                parent = evaluated[rng.randrange(min(len(evaluated), max(1, population_size // 2)))][0]
                population.append(mutate(parent, pool, rng, 0.08))
    finally:
        if executor is not None:
            executor.shutdown()
    return best


def main() -> None:
    parser = argparse.ArgumentParser(description="Solve ARLQ with absolute-coordinate target genes.")
    parser.add_argument("--stage", type=int, default=1)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--target-length", type=int, default=25)
    parser.add_argument("--population", type=int, default=100)
    parser.add_argument("--generations", type=int, default=200)
    parser.add_argument("--max-steps", type=int, default=500)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--random-seed", type=int)
    parser.add_argument("--stop-on-win", action="store_true", help="Stop immediately after finding a winning genome.")
    parser.add_argument(
        "--no-sword-df",
        action="store_true",
        help="Ignore sword-assisted D/F wins unless level is above 60 at defeat.",
    )
    parser.add_argument("-F", "--large-field", action="store_true")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-T", "--large-torch", action="store_true")
    group.add_argument("-t", "--small-torch", action="store_true")
    parser.add_argument("-n", "--narrower-corridors", action="store_true")
    args = parser.parse_args()
    apply_runtime_flags(args)
    genome, result, generation = run_ga(
        args.stage,
        args.seed,
        args.target_length,
        args.population,
        args.generations,
        args.workers,
        args.max_steps,
        args.random_seed,
        args.stop_on_win,
        args.no_sword_df,
    )
    print(f"stage={args.stage} seed={args.seed} generation={generation} df_defeated={result.df_defeated} won={result.won}")
    print(f"score={result.score:.1f} steps={result.steps} lp={result.lp} level={result.level}")
    print(f"genome={genome}")
    print(f"targets={result.targets}")
    print(f"moves={result.moves}")


if __name__ == "__main__":
    main()
