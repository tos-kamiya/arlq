"""Genetic-algorithm solver for ARLQ.

The genome is a string of ``u``, ``d``, ``l`` and ``r`` characters.  The
game itself continues to use (dx, dy) points internally.
"""

from __future__ import annotations

import argparse
import heapq
import random
import sys
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from dataclasses import dataclass

from . import defs as d
from .arlq import get_torched, respawn_entity, update_entities
from .solver import apply_runtime_flags, build_simulation
from .utils import rand

MOVE_TO_POINT: dict[str, d.Point] = {
    "u": (0, -1),
    "d": (0, 1),
    "l": (-1, 0),
    "r": (1, 0),
}
MOVES = tuple(MOVE_TO_POINT)
LEVEL_MILESTONE_REWARDS = {
    5: 50,
    10: 150,
    15: 300,
    20: 700,
    30: 1_500,
    40: 3_000,
    60: 5_000,
}
STARVATION_PENALTY = 10_000
MAX_PATH_DISTANCE = 100
SEGMENT_MOVE_RATE = 0.08
LP_REWARD_FULL_CAP = 40
LP_REWARD_CAP = 70
LP_REWARD_RATE = 0.5
LP_REWARD_REDUCED_RATE = 0.25


@dataclass(frozen=True)
class Evaluation:
    score: float
    won: bool
    df_defeated: bool
    steps: int
    lp: int
    level: int


@dataclass
class _EvaluationCheckpoint:
    state: object
    checkpoint: d.Point
    distance_cache: dict
    score: float
    steps: int
    rand_value: int


DistanceMap = dict[d.Point, int]


def _distance_map(state, target: d.Entity, can_break_walls: bool, cache: dict) -> DistanceMap:
    """Build or retrieve a terrain-only distance map to a target."""
    key = ((target.x, target.y), can_break_walls)
    if key in cache:
        return cache[key]

    def cost_at(point: d.Point) -> int | None:
        x, y = point
        tile = state.field[y][x]
        if tile == d.CHAR_CALTROP:
            return 4
        if tile == " ":
            return 1
        if can_break_walls and tile == d.WALL_CHAR:
            return 1
        return None

    goal = (target.x, target.y)
    distances: DistanceMap = {goal: 0}
    queue: list[tuple[int, d.Point]] = [(0, goal)]
    while queue:
        distance, current = heapq.heappop(queue)
        if distance != distances[current]:
            continue
        cx, cy = current
        for dx, dy in ((0, -1), (-1, 0), (1, 0), (0, 1)):
            nx, ny = cx + dx, cy + dy
            if not (0 <= nx < d.FIELD_WIDTH and 0 <= ny < d.FIELD_HEIGHT):
                continue
            step_cost = cost_at((nx, ny))
            if step_cost is None:
                continue
            next_point = (nx, ny)
            next_distance = distance + step_cost
            if not can_break_walls and next_distance >= MAX_PATH_DISTANCE:
                continue
            if next_distance < distances.get(next_point, 10**9):
                distances[next_point] = next_distance
                heapq.heappush(queue, (next_distance, next_point))
    cache[key] = distances
    return distances


def _target_distance(state, target: d.Entity | None, cache: dict) -> int | None:
    """Return terrain-only path cost to a target's cell."""
    if target is None:
        return None
    can_break_walls = state.player.item in (d.ITEM_SWORD_X1_5, d.ITEM_SWORD_CURSED) and state.player.item_uses > 0
    if can_break_walls:
        return abs(state.player.x - target.x) + abs(state.player.y - target.y)
    distance = _distance_map(state, target, False, cache).get((state.player.x, state.player.y))
    return distance if distance is not None and distance < MAX_PATH_DISTANCE else None


def _current_target(state, cache: dict) -> tuple[d.Entity | None, float]:
    unlockers = [
        entity
        for entity in state.entities
        if isinstance(entity, d.Monster) and entity.tribe.effect == d.EFFECT_UNLOCK_TREASURE
    ]
    beatable_unlockers = [
        entity for entity in unlockers if d.player_attack_by_level(state.player) >= entity.tribe.level
    ]
    if beatable_unlockers:
        target = min(
            beatable_unlockers,
            key=lambda entity: (
                _target_distance(state, entity, cache)
                if _target_distance(state, entity, cache) is not None
                else 10**9
            ),
        )
        return target, 120.0
    if unlockers:
        useful = [
            entity
            for entity in state.entities
            if isinstance(entity, d.Monster) and d.player_attack_by_level(state.player) >= entity.tribe.level
        ]
        if useful:
            def useful_score(entity: d.Monster) -> float:
                value = max(entity.tribe.feed, 0) * 4
                if entity.tribe.effect == d.EFFECT_SPECIAL_EXP:
                    value += 3_000
                if entity.tribe.item == d.ITEM_SWORD_X1_5:
                    value += 8_000
                elif entity.tribe.item == d.ITEM_SWORD_CURSED:
                    value += 10_000
                distance = _target_distance(state, entity, cache)
                if distance is None:
                    return -10**9
                return value - distance * 15

            target = max(
                useful,
                key=useful_score,
            )
            target_weight = 35.0 if target.tribe.item or target.tribe.effect == d.EFFECT_SPECIAL_EXP else 12.0
            return target, target_weight
        return None, 0.0

    treasures = [entity for entity in state.entities if isinstance(entity, d.Treasure)]
    if treasures:
        return treasures[0], 180.0
    return None, 0.0


def _unlocker_count(state) -> int:
    return sum(
        isinstance(entity, d.Monster) and entity.tribe.effect == d.EFFECT_UNLOCK_TREASURE
        for entity in state.entities
    )


def _lp_reward_value(lp: int) -> float:
    """Return the capped, piecewise-linear LP value used by fitness."""
    full_part = min(max(lp, 0), LP_REWARD_FULL_CAP) * LP_REWARD_RATE
    reduced_part = min(max(lp - LP_REWARD_FULL_CAP, 0), LP_REWARD_CAP - LP_REWARD_FULL_CAP)
    return full_part + reduced_part * LP_REWARD_REDUCED_RATE


def apply_ga_move(state, move: str, checkpoint: d.Point) -> d.Point:
    """Apply one genome character using the same turn rules as the game."""
    cur_torched = get_torched(state.player, state.torch_radius)
    for y in range(d.FIELD_HEIGHT):
        for x in range(d.FIELD_WIDTH):
            state.torched[y][x] += cur_torched[y][x]

    effect, tribes, _, _ = update_entities(
        MOVE_TO_POINT[move],
        state.field,
        state.player,
        state.entities,
        state.encountered_types,
        respawn_point=checkpoint,
    )
    for tribe_char in tribes:
        if tribe_char not in d.NO_RESPAWN_MONSTERS:
            state.respawn_queue[tribe_char] += 1

    if state.hours % d.MONSTER_RESPAWN_INTERVAL == 0:
        for tribe_char in list(state.respawn_queue):
            if state.respawn_queue[tribe_char] > 0:
                respawn_entity(d.CHAR_TO_TRIBE[tribe_char], state.entities, state.field, state.torched)
                state.respawn_queue[tribe_char] -= 1

    if effect == d.EFFECT_GOT_TREASURE:
        state.won = True
        state.ended = True
        return checkpoint

    state.hours += 1
    state.player.lp -= 1
    if tribes:
        checkpoint = (state.player.x, state.player.y)
    if state.player.lp <= 0:
        state.ended = True
    return checkpoint


def _make_checkpoint(state, checkpoint: d.Point, distance_cache: dict, score: float, steps: int):
    return _EvaluationCheckpoint(
        deepcopy(state), deepcopy(checkpoint), deepcopy(distance_cache), score, steps, rand._value
    )


def _evaluate_from_checkpoint(
    genome: str,
    stage: int,
    max_steps: int,
    start: _EvaluationCheckpoint,
    save_at: int | None = None,
) -> tuple[Evaluation, _EvaluationCheckpoint | None]:
    state = deepcopy(start.state)
    checkpoint = start.checkpoint
    distance_cache = deepcopy(start.distance_cache)
    score = start.score
    steps = start.steps
    rand._value = start.rand_value
    saved = _make_checkpoint(state, checkpoint, distance_cache, score, steps) if save_at == steps else None

    for move in genome[steps:max_steps]:
        if state.ended:
            break
        target_before, weight_before = _current_target(state, distance_cache)
        distance_before = _target_distance(state, target_before, distance_cache)
        before_level = state.player.level
        before_attack = d.player_attack_by_level(state.player)
        before_unlockers = _unlocker_count(state)
        before_item = state.player.item
        before_lp = state.player.lp
        terrain_before = tuple("".join(row) for row in state.field)
        checkpoint = apply_ga_move(state, move, checkpoint)
        steps += 1
        terrain_after = tuple("".join(row) for row in state.field)
        if terrain_before != terrain_after:
            distance_cache.clear()

        target_after, weight_after = _current_target(state, distance_cache)
        distance_after = _target_distance(state, target_after, distance_cache)
        if distance_before is not None and distance_after is not None:
            score += (distance_before - distance_after) * max(weight_before, weight_after)
        score += (state.player.level - before_level) * 80
        for level, reward in LEVEL_MILESTONE_REWARDS.items():
            if before_level < level <= state.player.level:
                score += reward
        after_attack = d.player_attack_by_level(state.player)
        unlocker_levels = [
            entity.tribe.level
            for entity in state.entities
            if isinstance(entity, d.Monster) and entity.tribe.effect == d.EFFECT_UNLOCK_TREASURE
        ]
        if unlocker_levels and before_attack < max(unlocker_levels) <= after_attack:
            score += 10_000
        if before_unlockers > 0 and _unlocker_count(state) == 0:
            score += 100_000
        if state.player.item != before_item and state.player.item:
            score += 250 if state.player.item in (d.ITEM_SWORD_X1_5, d.ITEM_SWORD_CURSED) else 50
        score += _lp_reward_value(state.player.lp) - _lp_reward_value(before_lp)
        score -= 1
        if save_at == steps:
            saved = _make_checkpoint(state, checkpoint, distance_cache, score, steps)

    if state.won:
        score += 1_000_000 + state.player.lp * 20 - steps * 2
    elif state.player.lp <= 0:
        score -= STARVATION_PENALTY
    else:
        score += state.player.lp
    df_defeated = _unlocker_count(state) == 0
    return Evaluation(score, state.won, df_defeated, steps, state.player.lp, state.player.level), saved


def evaluate_individual(genome: str, stage: int, seed: int, max_steps: int) -> Evaluation:
    state = build_simulation(stage, seed)
    start = _make_checkpoint(state, (state.player.x, state.player.y), {}, 0.0, 0)
    result, _ = _evaluate_from_checkpoint(genome, stage, max_steps, start)
    return result


def _worker_init(runtime_config: tuple[int, int, int, int, int]) -> None:
    d.TILE_NUM_Y, d.FIELD_HEIGHT, d.TORCH_RADIUS, d.CORRIDOR_H_WIDTH, d.CORRIDOR_V_WIDTH = runtime_config


def _evaluate_worker(task: tuple[list[str], int, int, int]) -> list[tuple[str, Evaluation]]:
    genomes, stage, seed, max_steps = task
    initial_state = build_simulation(stage, seed)
    initial = _make_checkpoint(initial_state, (initial_state.player.x, initial_state.player.y), {}, 0.0, 0)
    previous_genome = ""
    previous_checkpoint = initial
    results = []

    for index, genome in enumerate(genomes):
        common = 0
        while common < len(previous_genome) and common < len(genome) and previous_genome[common] == genome[common]:
            common += 1
        if previous_checkpoint.steps != common:
            common = 0
            previous_checkpoint = initial

        next_common = None
        if index + 1 < len(genomes):
            next_genome = genomes[index + 1]
            next_common = 0
            while next_common < len(genome) and next_common < len(next_genome) and genome[next_common] == next_genome[next_common]:
                next_common += 1

        result, saved = _evaluate_from_checkpoint(
            genome,
            stage,
            max_steps,
            previous_checkpoint,
            next_common,
        )
        results.append((genome, result))
        previous_genome = genome if saved is not None else ""
        previous_checkpoint = saved if saved is not None else initial
    return results


def random_genome(length: int, rng: random.Random) -> str:
    return "".join(rng.choice(MOVES) for _ in range(length))


def crossover(first: str, second: str, rng: random.Random) -> str:
    left, right = sorted(rng.sample(range(len(first) + 1), 2))
    return first[:left] + second[left:right] + first[right:]


def move_segment(genome: str, rng: random.Random) -> str:
    """Move a random segment of one to four genes to another position."""
    if len(genome) < 2:
        return genome
    segment_length = rng.randint(1, min(4, len(genome) - 1))
    start = rng.randrange(len(genome) - segment_length + 1)
    segment = genome[start : start + segment_length]
    remaining = genome[:start] + genome[start + segment_length :]
    insert_at = rng.randrange(len(remaining) + 1)
    return remaining[:insert_at] + segment + remaining[insert_at:]


def mutate(genome: str, rate: float, rng: random.Random, segment_move_rate: float = SEGMENT_MOVE_RATE) -> str:
    genes = list(genome)
    for index, gene in enumerate(genes):
        if rng.random() < rate:
            genes[index] = rng.choice(tuple(move for move in MOVES if move != gene))
    mutated = "".join(genes)
    if rng.random() < segment_move_rate:
        mutated = move_segment(mutated, rng)
    return mutated


def _select(population: list[tuple[str, Evaluation]], rng: random.Random) -> str:
    contestants = rng.sample(population, min(4, len(population)))
    return max(contestants, key=lambda item: item[1].score)[0]


def run_ga(
    stage: int,
    seed: int,
    max_steps: int = 500,
    population_size: int = 200,
    generations: int = 500,
    mutation_rate: float = 0.04,
    segment_move_rate: float = SEGMENT_MOVE_RATE,
    random_seed: int | None = None,
    workers: int = 1,
) -> tuple[str, Evaluation, int]:
    rng = random.Random(seed if random_seed is None else random_seed)
    population = [random_genome(max_steps, rng) for _ in range(population_size)]
    best_genome = population[0]
    best_result = evaluate_individual(best_genome, stage, seed, max_steps)
    best_generation = 0
    stagnant = 0

    runtime_config = (d.TILE_NUM_Y, d.FIELD_HEIGHT, d.TORCH_RADIUS, d.CORRIDOR_H_WIDTH, d.CORRIDOR_V_WIDTH)
    executor = (
        ProcessPoolExecutor(max_workers=workers, initializer=_worker_init, initargs=(runtime_config,))
        if workers > 1
        else None
    )
    try:
        for generation in range(generations):
            sorted_population = sorted(population)
            chunk_count = workers if executor is not None else 1
            chunk_size = (len(sorted_population) + chunk_count - 1) // chunk_count
            chunks = [sorted_population[index : index + chunk_size] for index in range(0, len(sorted_population), chunk_size)]
            tasks = [(chunk, stage, seed, max_steps) for chunk in chunks]
            if executor is None:
                evaluated = [item for task in tasks for item in _evaluate_worker(task)]
            else:
                evaluated = [item for chunk_result in executor.map(_evaluate_worker, tasks) for item in chunk_result]
            evaluated.sort(key=lambda item: item[1].score, reverse=True)
            if evaluated[0][1].score > best_result.score:
                best_genome, best_result, best_generation = evaluated[0][0], evaluated[0][1], generation
                stagnant = 0
            else:
                stagnant += 1
            print(
                f"generation={generation + 1}/{generations} "
                f"generation_best={evaluated[0][1].score:.1f} "
                f"best={best_result.score:.1f} steps={best_result.steps} "
                f"lp={best_result.lp} level={best_result.level} "
                f"df_defeated={best_result.df_defeated} won={best_result.won} "
                f"stagnant={stagnant}",
                file=sys.stderr,
                flush=True,
            )
            if best_result.won:
                break

            effective_rate = 0.12 if stagnant >= 40 else mutation_rate
            effective_segment_rate = 0.20 if stagnant >= 40 else segment_move_rate
            next_population = [genome for genome, _ in evaluated[:10]]
            while len(next_population) < population_size:
                first = _select(evaluated, rng)
                second = _select(evaluated, rng)
                child = crossover(first, second, rng)
                next_population.append(mutate(child, effective_rate, rng, effective_segment_rate))
            population = next_population
    finally:
        if executor is not None:
            executor.shutdown()
    return best_genome, best_result, best_generation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Solve an ARLQ stage with a genetic algorithm.")
    parser.add_argument("--stage", type=int, default=1)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--max-steps", type=int, default=500)
    parser.add_argument("--population", type=int, default=200)
    parser.add_argument("--generations", type=int, default=500)
    parser.add_argument("--mutation-rate", type=float, default=0.04)
    parser.add_argument("--segment-move-rate", type=float, default=SEGMENT_MOVE_RATE)
    parser.add_argument("--random-seed", type=int)
    parser.add_argument("--workers", type=int, default=1, help="Number of worker processes for individual evaluation.")
    parser.add_argument("-F", "--large-field", action="store_true")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-T", "--large-torch", action="store_true")
    group.add_argument("-t", "--small-torch", action="store_true")
    parser.add_argument("-n", "--narrower-corridors", action="store_true")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    apply_runtime_flags(args)
    genome, result, generation = run_ga(
        args.stage,
        args.seed,
        max_steps=args.max_steps,
        population_size=args.population,
        generations=args.generations,
        mutation_rate=args.mutation_rate,
        segment_move_rate=args.segment_move_rate,
        random_seed=args.random_seed,
        workers=args.workers,
    )
    print(
        f"stage={args.stage} seed={args.seed} generation={generation} "
        f"df_defeated={result.df_defeated} won={result.won}"
    )
    print(f"score={result.score:.1f} steps={result.steps} lp={result.lp} level={result.level}")
    print(f"moves={genome[:result.steps]}")


if __name__ == "__main__":
    main()
