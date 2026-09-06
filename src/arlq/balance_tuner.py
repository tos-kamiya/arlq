from __future__ import annotations

import argparse
import hashlib
import json
import random
import statistics
import subprocess
import sys
import time
from collections import Counter, deque
from collections.abc import Iterable
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import defs as d
from .arlq import get_torched, respawn_entity, update_entities
from .solver import build_simulation

POLICY_VERSION = "observed-v1"
POLICIES = ("discovery", "nearest", "situational", "food", "growth")
DEFAULT_CONFIG: dict[str, Any] = {
    "stages": [1, 2],
    "policies": list(POLICIES),
    "max_steps": 3000,
    "stalled_steps": 200,
    "early_turn": 150,
    "search": {"seed_start": 1, "seeds": 20, "candidates": 12},
    "validation": {"seed_start": 100001, "seeds": 50, "keep": 4},
    "final": {"seed_start": 200001, "seeds": 100, "keep": 3},
    "jobs": 1,
    "parameters": {
        "feed": {
            "a": {"min": 6, "max": 12, "step": 2},
            "b": {"min": 30, "max": 50, "step": 5},
            "c": {"min": 6, "max": 12, "step": 2},
            "d": {"min": 30, "max": 50, "step": 5},
        },
        "spawn": {
            "1": {
                "a": {"min": 10, "max": 18, "step": 2},
                "A": {"min": 1, "max": 2, "step": 1},
                "b": {"min": 5, "max": 9, "step": 1},
                "c": {"min": 2, "max": 5, "step": 1},
                "d": {"min": 2, "max": 5, "step": 1},
            },
            "2": {
                "a": {"min": 10, "max": 18, "step": 2},
                "A": {"min": 1, "max": 2, "step": 1},
                "b": {"min": 5, "max": 9, "step": 1},
                "c": {"min": 2, "max": 5, "step": 1},
                "C": {"min": 1, "max": 2, "step": 1},
                "d": {"min": 2, "max": 5, "step": 1},
            },
        },
        "max_total_population": {"1": 40, "2": 48},
    },
    "targets": {},
}


@dataclass(frozen=True)
class Tuning:
    feed: tuple[tuple[str, int], ...]
    spawn: tuple[tuple[int, str, int | float], ...]

    def payload(self) -> dict[str, Any]:
        return {
            "feed": dict(self.feed),
            "spawn": {
                str(stage): {char: value for s, char, value in self.spawn if s == stage}
                for stage in (1, 2)
            },
        }

    @property
    def candidate_id(self) -> str:
        raw = json.dumps(self.payload(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode()).hexdigest()[:12]


@dataclass
class RunResult:
    candidate_id: str
    phase: str
    seed: int
    stage: int
    policy: str
    won: bool
    end_reason: str
    steps: int
    lp: int
    level: int
    contacts: int
    battle_losses: int
    kills: dict[str, int]
    first_kill_turn: dict[str, int]
    nominal_feed: dict[str, int]
    effective_recovery: dict[str, int]
    wasted_recovery: dict[str, int]
    discovery_order: list[str]
    kill_order: list[str]
    item_transitions: list[dict[str, Any]]


@dataclass
class PolicyMemory:
    next_serial: int = 0
    discovery: dict[int, tuple[int, int]] = field(default_factory=dict)
    target_id: int | None = None


def _spawn_configs(stage: int) -> list[d.SpawnConfig]:
    if stage not in (1, 2):
        raise ValueError(f"unsupported stage: {stage}")
    return d.STAGE_TO_SPAWN_CONFIGS[stage - 1]


def current_tuning(config: dict[str, Any]) -> Tuning:
    feed = tuple(
        sorted(
            (char, d.CHAR_TO_MONSTER_TRIBE[char].feed)
            for char in config["parameters"]["feed"]
        )
    )
    spawn: list[tuple[int, str, int | float]] = []
    for stage_text, ranges in config["parameters"]["spawn"].items():
        stage = int(stage_text)
        by_char = {sc.tribe.char: sc.population for sc in _spawn_configs(stage)}
        spawn.extend((stage, char, by_char[char]) for char in ranges)
    return Tuning(feed, tuple(sorted(spawn)))


@contextmanager
def patched_tuning(tuning: Tuning):
    old_feed = {char: d.CHAR_TO_MONSTER_TRIBE[char].feed for char, _ in tuning.feed}
    old_spawn: dict[tuple[int, str], int | float] = {}
    try:
        for char, value in tuning.feed:
            d.CHAR_TO_MONSTER_TRIBE[char].feed = value
        for stage, char, value in tuning.spawn:
            sc = next(sc for sc in _spawn_configs(stage) if sc.tribe.char == char)
            old_spawn[(stage, char)] = sc.population
            sc.population = value
        yield
    finally:
        for char, value in old_feed.items():
            d.CHAR_TO_MONSTER_TRIBE[char].feed = value
        for (stage, char), value in old_spawn.items():
            next(
                sc for sc in _spawn_configs(stage) if sc.tribe.char == char
            ).population = value


@contextmanager
def patched_lp_max(value: int):
    old = d.LP_MAX
    d.LP_MAX = value
    try:
        yield
    finally:
        d.LP_MAX = old


def _range_values(spec: dict[str, int]) -> list[int]:
    low, high, step = spec["min"], spec["max"], spec["step"]
    if step <= 0 or low > high:
        raise ValueError(f"invalid parameter range: {spec}")
    return list(range(low, high + 1, step))


def validate_config(config: dict[str, Any]) -> None:
    if not config.get("stages") or any(
        stage not in (1, 2) for stage in config["stages"]
    ):
        raise ValueError("stages must contain 1 and/or 2")
    unknown = set(config["policies"]) - set(POLICIES)
    if unknown:
        raise ValueError(f"unknown policies: {sorted(unknown)}")
    if not isinstance(config.get("jobs", 1), int) or config.get("jobs", 1) <= 0:
        raise ValueError("jobs must be a positive integer")
    phase_seeds: list[set[int]] = []
    for phase in ("search", "validation", "final"):
        section = config[phase]
        if section["seeds"] <= 0:
            raise ValueError(f"{phase}.seeds must be positive")
        phase_seeds.append(
            set(range(section["seed_start"], section["seed_start"] + section["seeds"]))
        )
    if any(phase_seeds[i] & phase_seeds[j] for i in range(3) for j in range(i + 1, 3)):
        raise ValueError("search, validation, and final seed sets must be disjoint")
    for spec in config["parameters"]["feed"].values():
        _range_values(spec)
    if "lp_max" in config and (
        not isinstance(config["lp_max"], int) or config["lp_max"] <= 0
    ):
        raise ValueError("lp_max must be a positive integer")
    for ranges in config["parameters"]["spawn"].values():
        for spec in ranges.values():
            _range_values(spec)


def generate_candidates(config: dict[str, Any], rng: random.Random) -> list[Tuning]:
    baseline = current_tuning(config)
    candidates = [baseline]
    seen = {baseline.candidate_id}
    wanted = config["search"]["candidates"]
    attempts = max(100, wanted * 20)
    for _ in range(attempts):
        feed = tuple(
            sorted(
                (char, rng.choice(_range_values(spec)))
                for char, spec in config["parameters"]["feed"].items()
            )
        )
        spawn: list[tuple[int, str, int | float]] = []
        valid = True
        for stage_text, ranges in config["parameters"]["spawn"].items():
            stage = int(stage_text)
            chosen = {
                char: rng.choice(_range_values(spec)) for char, spec in ranges.items()
            }
            fixed = sum(
                float(sc.population)
                for sc in _spawn_configs(stage)
                if sc.tribe.char not in chosen
            )
            limit = config["parameters"].get("max_total_population", {}).get(stage_text)
            if limit is not None and fixed + sum(chosen.values()) > limit:
                valid = False
                break
            spawn.extend((stage, char, value) for char, value in chosen.items())
        tuning = Tuning(feed, tuple(sorted(spawn)))
        if valid and tuning.candidate_id not in seen:
            candidates.append(tuning)
            seen.add(tuning.candidate_id)
        if len(candidates) >= wanted:
            break
    return candidates


def _visible(state, entity: d.Entity) -> bool:
    return bool(state.torched[entity.y][entity.x])


def _observe(state, memory: PolicyMemory) -> None:
    for entity in state.entities:
        if (
            isinstance(entity, d.Monster)
            and _visible(state, entity)
            and id(entity) not in memory.discovery
        ):
            memory.discovery[id(entity)] = (memory.next_serial, state.hours)
            memory.next_serial += 1


def _known_passable(state, point: d.Point) -> bool:
    x, y = point
    return (
        0 <= x < d.FIELD_WIDTH
        and 0 <= y < d.FIELD_HEIGHT
        and bool(state.torched[y][x])
        and state.field[y][x] in (" ", d.CHAR_CALTROP)
    )


def _paths(
    state, target: d.Entity | None = None
) -> tuple[dict[d.Point, int], dict[d.Point, d.Point]]:
    start = (state.player.x, state.player.y)
    blocked = {
        (e.x, e.y)
        for e in state.entities
        if e is not state.player
        and e is not target
        and _visible(state, e)
        and isinstance(e, (d.Monster, d.Companion, d.Treasure))
    }
    queue = deque([start])
    dist = {start: 0}
    previous: dict[d.Point, d.Point] = {}
    while queue:
        point = queue.popleft()
        for dx, dy in ((0, -1), (-1, 0), (1, 0), (0, 1)):
            nxt = (point[0] + dx, point[1] + dy)
            if nxt in dist or nxt in blocked or not _known_passable(state, nxt):
                continue
            dist[nxt] = dist[point] + 1
            previous[nxt] = point
            queue.append(nxt)
    return dist, previous


def _target_route(state, target: d.Entity) -> tuple[int, d.Point] | None:
    dist, previous = _paths(state, target)
    goal = (target.x, target.y)
    if goal not in dist:
        return None
    point = goal
    while previous.get(point) != (state.player.x, state.player.y):
        if point not in previous:
            return None
        point = previous[point]
    return dist[goal], point


def _identified(state, monster: d.Monster) -> bool:
    return monster.tribe.char in state.encountered_types


def _target_score(
    policy: str, state, monster: d.Monster, distance: int, serial: int
) -> tuple[float, int, int]:
    known = _identified(state, monster)
    if not known:
        return (-50_000 - distance, -distance, -serial)
    tribe = monster.tribe
    if d.player_attack_by_level(state.player) < tribe.level:
        return (-1e9, -distance, -serial)
    if policy == "discovery":
        return (-serial, -distance, 0)
    if policy == "nearest":
        return (-distance, -serial, 0)
    if policy == "food":
        return (tribe.feed * 100 - distance * 8, -serial, 0)
    if policy == "growth":
        bonus = 1000 if tribe.effect == d.EFFECT_SPECIAL_EXP else 0
        return (bonus + tribe.level * 25 - distance * 8, -serial, 0)
    recovery = min(max(tribe.feed, 0), max(d.LP_MAX - state.player.lp, 0))
    score = (
        recovery * (18 if state.player.lp < 45 else 3) + tribe.level * 8 - distance * 12
    )
    if tribe.effect == d.EFFECT_SPECIAL_EXP:
        score += 900
    if tribe.effect == d.EFFECT_UNLOCK_TREASURE:
        score += 5000
    if tribe.item == d.ITEM_SWORD_X1_5:
        score += 700
    elif tribe.item == d.ITEM_SWORD_CURSED:
        score += 800 if state.player.level >= 15 else -600
    elif tribe.item is None and state.player.item:
        score -= 500
    if state.player.lp > 75 and tribe.feed > 0:
        score -= tribe.feed * 12
    return (score, -distance, -serial)


def choose_observed_move(state, policy: str, memory: PolicyMemory) -> d.Point:
    _observe(state, memory)
    candidates: list[tuple[tuple[float, int, int], d.Entity, d.Point]] = []
    for entity in state.entities:
        if isinstance(entity, d.Monster) and id(entity) in memory.discovery:
            route = _target_route(state, entity)
            if route is None:
                continue
            distance, next_point = route
            serial = memory.discovery[id(entity)][0]
            score = _target_score(policy, state, entity, distance, serial)
            if score[0] > -1e8:
                candidates.append((score, entity, next_point))
        elif (
            isinstance(entity, d.Treasure)
            and _visible(state, entity)
            and entity.encounter_type in state.encountered_types
        ):
            route = _target_route(state, entity)
            if route:
                candidates.append(((1e8, 0, 0), entity, route[1]))
    if candidates:
        candidates.sort(key=lambda row: row[0], reverse=True)
        _, target, next_point = candidates[0]
        memory.target_id = id(target)
        return next_point[0] - state.player.x, next_point[1] - state.player.y

    # All policies share this frontier exploration rule. It uses only mapped cells.
    dist, previous = _paths(state)
    frontiers: list[tuple[int, int, int, d.Point]] = []
    for (x, y), distance in dist.items():
        unseen = sum(
            1
            for dx, dy in ((0, -1), (-1, 0), (1, 0), (0, 1))
            if 0 <= x + dx < d.FIELD_WIDTH
            and 0 <= y + dy < d.FIELD_HEIGHT
            and not state.torched[y + dy][x + dx]
        )
        if unseen:
            frontiers.append((distance, -unseen, y * d.FIELD_WIDTH + x, (x, y)))
    if frontiers:
        goal = min(frontiers)[3]
        point = goal
        while previous.get(point) != (state.player.x, state.player.y):
            if point not in previous:
                break
            point = previous[point]
        if point != (state.player.x, state.player.y):
            return point[0] - state.player.x, point[1] - state.player.y
    return (0, 0)


def simulate(
    tuning: Tuning,
    phase: str,
    stage: int,
    seed: int,
    policy: str,
    config: dict[str, Any],
) -> RunResult:
    with patched_tuning(tuning), patched_lp_max(config.get("lp_max", d.LP_MAX)):
        state = build_simulation(stage, seed)
        memory = PolicyMemory()
        kills: Counter[str] = Counter()
        first_kill: dict[str, int] = {}
        nominal: Counter[str] = Counter()
        effective: Counter[str] = Counter()
        wasted: Counter[str] = Counter()
        kill_order: list[str] = []
        discovery_order: list[str] = []
        item_transitions: list[dict[str, Any]] = []
        respawn_point = (state.player.x, state.player.y)
        battle_losses = 0
        stalled = 0
        steps = 0
        end_reason = "turn_limit"
        while not state.ended and steps < config["max_steps"]:
            if state.player.lp <= 0:
                end_reason = "lp_depleted"
                break
            cur_torched = get_torched(state.player, state.torch_radius)
            for y in range(d.FIELD_HEIGHT):
                for x in range(d.FIELD_WIDTH):
                    state.torched[y][x] += cur_torched[y][x]
            before_discovered = set(memory.discovery)
            move = choose_observed_move(state, policy, memory)
            newly_seen = sorted(
                (memory.discovery[eid][0], eid)
                for eid in set(memory.discovery) - before_discovered
            )
            by_id = {id(e): e for e in state.entities}
            discovery_order.extend(
                by_id[eid].tribe.char for _, eid in newly_seen if eid in by_id
            )
            before_monsters = {
                id(e): e for e in state.entities if isinstance(e, d.Monster)
            }
            before_lp = state.player.lp
            before_item = state.player.item or ""
            before_pos = (state.player.x, state.player.y)
            effect, respawns, _, contacted = update_entities(
                move,
                state.field,
                state.player,
                state.entities,
                state.encountered_types,
                config.get("sword_uses", d.SWORD_USES),
                respawn_point if config.get("respawn_mode") == "checkpoint" else None,
            )
            if contacted:
                state.contacts += 1
            after_ids = {id(e) for e in state.entities}
            removed = [
                monster
                for eid, monster in before_monsters.items()
                if eid not in after_ids
            ]
            if removed:
                respawn_point = (state.player.x, state.player.y)
                monster = removed[0]
                char = monster.tribe.char
                kills[char] += 1
                first_kill.setdefault(char, steps)
                kill_order.append(char)
                nominal[char] += monster.tribe.feed
                after_feed = max(1, min(d.LP_MAX, before_lp + monster.tribe.feed))
                # Food is applied before a cursed sword changes LP, so calculate it
                # separately from the final LP delta.
                gained = max(0, after_feed - before_lp)
                effective[char] += gained
                wasted[char] += max(monster.tribe.feed, 0) - gained
            elif contacted and state.player.lp < before_lp - 1:
                battle_losses += 1
            after_item = state.player.item or ""
            if after_item != before_item:
                item_transitions.append(
                    {"turn": steps, "from": before_item, "to": after_item}
                )
            for char in respawns:
                if respawn_allowed(stage, char, config):
                    state.respawn_queue[char] += 1
            if state.hours % d.MONSTER_RESPAWN_INTERVAL == 0:
                for char in sorted(state.respawn_queue):
                    if state.respawn_queue[char] > 0 and respawn_allowed(
                        stage, char, config
                    ):
                        respawn_entity(
                            d.CHAR_TO_TRIBE[char],
                            state.entities,
                            state.field,
                            state.torched,
                        )
                        state.respawn_queue[char] -= 1
            if effect == d.EFFECT_GOT_TREASURE:
                state.won = state.ended = True
                end_reason = "won"
                break
            state.hours += 1
            state.player.lp -= 1
            steps += 1
            stalled = (
                stalled + 1
                if before_pos == (state.player.x, state.player.y) and not contacted
                else 0
            )
            if state.player.lp <= 0:
                state.ended = True
                end_reason = "lp_depleted"
            elif stalled >= config["stalled_steps"]:
                state.ended = True
                end_reason = "stalled"
        return RunResult(
            tuning.candidate_id,
            phase,
            seed,
            stage,
            policy,
            state.won,
            end_reason,
            steps,
            state.player.lp,
            state.player.level,
            state.contacts,
            battle_losses,
            dict(kills),
            first_kill,
            dict(nominal),
            dict(effective),
            dict(wasted),
            discovery_order,
            kill_order,
            item_transitions,
        )


def _quantile(values: list[int], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return float(ordered[round((len(ordered) - 1) * fraction)])


def _paired_bootstrap_interval(differences: list[int]) -> list[float] | None:
    if not differences:
        return None
    rng = random.Random(0)
    estimates = sorted(
        sum(rng.choice(differences) for _ in differences) / len(differences)
        for _ in range(2000)
    )
    return [estimates[49], estimates[1949]]


def aggregate(runs: Iterable[RunResult], early_turn: int) -> dict[str, Any]:
    rows = list(runs)
    by_policy_stage: dict[str, Any] = {}
    for stage in sorted({r.stage for r in rows}):
        for policy in sorted({r.policy for r in rows}):
            subset = [r for r in rows if r.stage == stage and r.policy == policy]
            if not subset:
                continue
            wins = [r for r in subset if r.won]
            key = f"stage{stage}:{policy}"
            by_policy_stage[key] = {
                "runs": len(subset),
                "wins": len(wins),
                "clear_rate": len(wins) / len(subset),
                "early_starvation_rate": sum(
                    r.end_reason == "lp_depleted" and r.steps <= early_turn
                    for r in subset
                )
                / len(subset),
                "win_steps": {
                    "p25": _quantile([r.steps for r in wins], 0.25),
                    "median": _quantile([r.steps for r in wins], 0.5),
                    "p75": _quantile([r.steps for r in wins], 0.75),
                },
                "win_lp": {
                    "p25": _quantile([r.lp for r in wins], 0.25),
                    "median": _quantile([r.lp for r in wins], 0.5),
                    "p75": _quantile([r.lp for r in wins], 0.75),
                },
                "end_reasons": dict(Counter(r.end_reason for r in subset)),
            }
    deltas: dict[str, Any] = {}
    for stage in sorted({r.stage for r in rows}):
        stage_rows = [r for r in rows if r.stage == stage]
        by_seed_policy = {(r.seed, r.policy): int(r.won) for r in stage_rows}
        for policy in ("nearest", "situational", "food", "growth"):
            pairs = [
                (by_seed_policy[(seed, policy)], by_seed_policy[(seed, "discovery")])
                for seed in sorted({r.seed for r in stage_rows})
                if (seed, policy) in by_seed_policy
                and (seed, "discovery") in by_seed_policy
            ]
            if pairs:
                differences = [a - b for a, b in pairs]
                deltas[f"stage{stage}:{policy}-discovery"] = {
                    "delta_clear": sum(differences) / len(differences),
                    "interval_95": _paired_bootstrap_interval(differences),
                    "paired_seeds": len(pairs),
                }
    return {"by_policy_stage": by_policy_stage, "paired_deltas": deltas}


def change_distance(tuning: Tuning, baseline: Tuning) -> float:
    a, b = tuning.payload(), baseline.payload()
    values: list[float] = []
    for char, value in a["feed"].items():
        values.append(abs(value - b["feed"][char]))
    for stage, chars in a["spawn"].items():
        values.extend(
            abs(float(value) - float(b["spawn"][stage][char]))
            for char, value in chars.items()
        )
    return sum(values)


def candidate_key(
    summary: dict[str, Any], distance: float, targets: dict[str, Any]
) -> tuple[Any, ...]:
    metrics = summary["by_policy_stage"]
    violations = 0.0
    for key, bounds in targets.get("clear_rate", {}).items():
        value = metrics.get(key, {}).get("clear_rate", 0.0)
        violations += max(bounds.get("min", 0) - value, 0) + max(
            value - bounds.get("max", 1), 0
        )
    for key, maximum in targets.get("early_starvation_rate_max", {}).items():
        violations += max(
            metrics.get(key, {}).get("early_starvation_rate", 1.0) - maximum, 0
        )
    deltas = [
        value["delta_clear"]
        for key, value in summary["paired_deltas"].items()
        if ":situational-" in key
    ]
    nearest = [
        value["delta_clear"]
        for key, value in summary["paired_deltas"].items()
        if ":nearest-" in key
    ]
    choice_value = statistics.mean(deltas) if deltas else -1.0
    travel_effect = statistics.mean(nearest) if nearest else 0.0
    return (violations, -choice_value, -travel_effect, distance)


def _simulate_task(
    task: tuple[Tuning, str, int, int, str, dict[str, Any]],
) -> RunResult:
    tuning, phase, stage, seed, policy, config = task
    return simulate(tuning, phase, stage, seed, policy, config)


def respawn_allowed(stage: int, char: str, config: dict[str, Any]) -> bool:
    """Return whether a queued entity may respawn; companions stay unchanged."""
    if char in d.CHAR_TO_COMPANION_TRIBE:
        return True
    by_stage = config.get("respawn")
    if by_stage is None:
        return True
    return char in by_stage.get(str(stage), [])


def evaluate_phase(
    tunings: list[Tuning], phase: str, config: dict[str, Any], runs_file, jobs: int
) -> list[tuple[Tuning, dict[str, Any]]]:
    section = config[phase]
    seeds = range(section["seed_start"], section["seed_start"] + section["seeds"])
    evaluated: list[tuple[Tuning, dict[str, Any]]] = []
    total_runs = (
        len(tunings)
        * section["seeds"]
        * len(config["stages"])
        * len(config["policies"])
    )
    print(
        f"{phase}: starting {len(tunings)} candidates, {total_runs} plays, jobs={jobs}",
        file=sys.stderr,
        flush=True,
    )
    for index, tuning in enumerate(tunings, 1):
        print(
            f"{phase}: starting candidate {index}/{len(tunings)} id={tuning.candidate_id}",
            file=sys.stderr,
            flush=True,
        )
        tasks = [
            (tuning, phase, stage, seed, policy, config)
            for seed in seeds
            for stage in config["stages"]
            for policy in config["policies"]
        ]
        if jobs == 1:
            rows = [_simulate_task(task) for task in tasks]
        else:
            with ProcessPoolExecutor(max_workers=jobs) as executor:
                futures = [executor.submit(_simulate_task, task) for task in tasks]
                ordered: list[RunResult | None] = [None] * len(futures)
                future_indices = {future: index for index, future in enumerate(futures)}
                for future in as_completed(futures):
                    ordered[future_indices[future]] = future.result()
                rows = [result for result in ordered if result is not None]
        for result in rows:
            runs_file.write(json.dumps(asdict(result), sort_keys=True) + "\n")
        runs_file.flush()
        evaluated.append((tuning, aggregate(rows, config["early_turn"])))
        print(
            f"{phase}: evaluated {index}/{len(tunings)} candidate={tuning.candidate_id}",
            file=sys.stderr,
            flush=True,
        )
    return evaluated


def _git_info() -> dict[str, Any]:
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"], text=True, capture_output=True, check=True
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                text=True,
                capture_output=True,
                check=True,
            ).stdout
        )
        return {"revision": revision, "dirty": dirty}
    except (OSError, subprocess.CalledProcessError):
        return {"revision": None, "dirty": None}


def write_report(
    path: Path,
    ranked: list[dict[str, Any]],
    config: dict[str, Any],
    total_runs: int,
    elapsed: float,
) -> None:
    lines = [
        "# ARLQ static balance tuning report",
        "",
        "The policies use mapped terrain and observed entities. `discovery` means the order in which the player first saw each monster; it is not internal spawn order. Unknown monster stats are not read by a policy.",
        "",
        f"Evaluated {total_runs} plays in {elapsed:.1f} seconds. Candidates are proposals; no game constants were modified.",
        "",
        "Finite policies, seeds, and budgets do not prove optimality. Spawn changes also change random-number consumption, so equal seeds do not guarantee identical layouts.",
        "",
        "## Final candidates",
        "",
    ]
    for rank, row in enumerate(ranked, 1):
        lines.extend(
            [
                f"### {rank}. `{row['candidate_id']}`",
                "",
                f"Change distance: {row['change_distance']}",
                "",
                "```json",
                json.dumps(row["tuning"], indent=2, sort_keys=True),
                "```",
                "",
                "| Policy and stage | Clear rate | Early starvation | Win steps (median) | Win LP (median) |",
                "| --- | ---: | ---: | ---: | ---: |",
            ]
        )
        for key, metric in sorted(row["summary"]["by_policy_stage"].items()):
            lines.append(
                f"| {key} | {metric['clear_rate']:.3f} | {metric['early_starvation_rate']:.3f} | {metric['win_steps']['median']} | {metric['win_lp']['median']} |"
            )
        lines.extend(["", "Paired clear-rate differences:", ""])
        for key, metric in sorted(row["summary"]["paired_deltas"].items()):
            interval = metric["interval_95"]
            lines.append(
                f"- `{key}`: {metric['delta_clear']:+.3f}, "
                f"95% paired bootstrap [{interval[0]:+.3f}, {interval[1]:+.3f}] "
                f"({metric['paired_seeds']} seeds)"
            )
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    validate_config(config)
    return config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Search static ARLQ feed and spawn balance candidates."
    )
    parser.add_argument("--config", type=Path, help="JSON tuning configuration.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("balance-tuning-output"),
        help="Output directory.",
    )
    parser.add_argument(
        "--random-seed", type=int, default=20260906, help="Candidate-generation seed."
    )
    parser.add_argument(
        "--jobs",
        type=int,
        help="Number of worker processes (overrides config.jobs).",
    )
    parser.add_argument(
        "--write-default-config",
        type=Path,
        help="Write an example configuration and exit.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.write_default_config:
        args.write_default_config.write_text(
            json.dumps(DEFAULT_CONFIG, indent=2) + "\n", encoding="utf-8"
        )
        print(args.write_default_config)
        return
    if args.config is None:
        raise SystemExit("--config is required (or use --write-default-config)")
    config = load_config(args.config)
    jobs = args.jobs if args.jobs is not None else config.get("jobs", 1)
    if jobs <= 0:
        raise SystemExit("--jobs must be positive")
    args.output.mkdir(parents=True, exist_ok=True)
    baseline = current_tuning(config)
    candidates = generate_candidates(config, random.Random(args.random_seed))
    started = time.monotonic()
    total_runs = 0
    all_candidate_rows: list[dict[str, Any]] = []
    phase_rows: list[dict[str, Any]] = []
    with (args.output / "runs.jsonl").open("w", encoding="utf-8") as runs_file:
        search = evaluate_phase(candidates, "search", config, runs_file, jobs)
        total_runs += (
            len(candidates)
            * config["search"]["seeds"]
            * len(config["stages"])
            * len(config["policies"])
        )
        search.sort(
            key=lambda row: candidate_key(
                row[1], change_distance(row[0], baseline), config["targets"]
            )
        )
        phase_rows.extend(
            {
                "phase": "search",
                "candidate_id": tuning.candidate_id,
                "tuning": tuning.payload(),
                "change_distance": change_distance(tuning, baseline),
                "summary": summary,
                "rank_key": candidate_key(
                    summary, change_distance(tuning, baseline), config["targets"]
                ),
            }
            for tuning, summary in search
        )
        validation_tunings = [row[0] for row in search[: config["validation"]["keep"]]]
        validation = evaluate_phase(
            validation_tunings, "validation", config, runs_file, jobs
        )
        total_runs += (
            len(validation_tunings)
            * config["validation"]["seeds"]
            * len(config["stages"])
            * len(config["policies"])
        )
        validation.sort(
            key=lambda row: candidate_key(
                row[1], change_distance(row[0], baseline), config["targets"]
            )
        )
        phase_rows.extend(
            {
                "phase": "validation",
                "candidate_id": tuning.candidate_id,
                "tuning": tuning.payload(),
                "change_distance": change_distance(tuning, baseline),
                "summary": summary,
                "rank_key": candidate_key(
                    summary, change_distance(tuning, baseline), config["targets"]
                ),
            }
            for tuning, summary in validation
        )
        final_tunings = [row[0] for row in validation[: config["final"]["keep"]]]
        final = evaluate_phase(final_tunings, "final", config, runs_file, jobs)
        total_runs += (
            len(final_tunings)
            * config["final"]["seeds"]
            * len(config["stages"])
            * len(config["policies"])
        )
    final.sort(
        key=lambda row: candidate_key(
            row[1], change_distance(row[0], baseline), config["targets"]
        )
    )
    for tuning, summary in final:
        all_candidate_rows.append(
            {
                "candidate_id": tuning.candidate_id,
                "tuning": tuning.payload(),
                "change_distance": change_distance(tuning, baseline),
                "summary": summary,
                "rank_key": candidate_key(
                    summary, change_distance(tuning, baseline), config["targets"]
                ),
            }
        )
    phase_rows.extend({"phase": "final", **row} for row in all_candidate_rows)
    with (args.output / "candidates.jsonl").open("w", encoding="utf-8") as handle:
        for row in phase_rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    elapsed = time.monotonic() - started
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "config": config,
        "random_seed": args.random_seed,
        "policy_version": POLICY_VERSION,
        "information_condition": "observed",
        "git": _git_info(),
        "baseline": baseline.payload(),
        "candidate_ids": [t.candidate_id for t in candidates],
        "total_runs": total_runs,
        "elapsed_seconds": elapsed,
        "randomness": "ARLQ MyRandom for games; Python random.Random for candidates",
        "jobs": jobs,
    }
    (args.output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (args.output / "decision_examples.jsonl").write_text("", encoding="utf-8")
    write_report(
        args.output / "report.md", all_candidate_rows, config, total_runs, elapsed
    )
    print(f"report: {args.output / 'report.md'}")


if __name__ == "__main__":
    main()
