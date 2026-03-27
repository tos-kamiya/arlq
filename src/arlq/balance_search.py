from __future__ import annotations

import argparse
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass
from types import SimpleNamespace

from . import defs as d
from .branch_analyzer import analyze_seed_with_beam, replay_win_history
from .solver import apply_runtime_flags


TARGET_LABELS = ("monster:b", "monster:d", "monster:a", "monster:c")
STAGE1_SPAWN_LABELS = ("a", "A", "b", "c", "d")


@dataclass(frozen=True)
class Stage1Tuning:
    b_feed: int
    count_a: int
    count_A: int
    count_b: int
    count_c: int
    count_d: int


@dataclass
class EvaluationResult:
    tuning: Stage1Tuning
    wins: int
    leaves: int
    preference_rows: dict[str, tuple[int, int]]
    preference_rates: dict[str, float]
    comparison_totals: dict[str, int]
    variance: float


def current_stage1_tuning() -> Stage1Tuning:
    counts = {sc.tribe.char: int(sc.population) for sc in d.SPAWN_CONFIGS_ST1 if sc.tribe.char in STAGE1_SPAWN_LABELS}
    return Stage1Tuning(
        b_feed=d.CHAR_TO_MONSTER_TRIBE["b"].feed,
        count_a=counts["a"],
        count_A=counts["A"],
        count_b=counts["b"],
        count_c=counts["c"],
        count_d=counts["d"],
    )


@contextmanager
def patched_stage1_tuning(tuning: Stage1Tuning):
    old_feed = d.CHAR_TO_MONSTER_TRIBE["b"].feed
    old_counts = {sc.tribe.char: sc.population for sc in d.SPAWN_CONFIGS_ST1 if sc.tribe.char in STAGE1_SPAWN_LABELS}
    try:
        d.CHAR_TO_MONSTER_TRIBE["b"].feed = tuning.b_feed
        for sc in d.SPAWN_CONFIGS_ST1:
            if sc.tribe.char == "a":
                sc.population = tuning.count_a
            elif sc.tribe.char == "A":
                sc.population = tuning.count_A
            elif sc.tribe.char == "b":
                sc.population = tuning.count_b
            elif sc.tribe.char == "c":
                sc.population = tuning.count_c
            elif sc.tribe.char == "d":
                sc.population = tuning.count_d
        yield
    finally:
        d.CHAR_TO_MONSTER_TRIBE["b"].feed = old_feed
        for sc in d.SPAWN_CONFIGS_ST1:
            if sc.tribe.char in old_counts:
                sc.population = old_counts[sc.tribe.char]


def build_runtime_args(args: argparse.Namespace) -> argparse.Namespace:
    return SimpleNamespace(
        large_field=args.large_field,
        large_torch=args.large_torch,
        small_torch=args.small_torch,
        narrower_corridors=args.narrower_corridors,
    )


def evaluate_seed(task: tuple[int, int, int, int, int, int, int, float, float, bool, bool, bool, bool, Stage1Tuning]):
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
        tuning,
    ) = task

    runtime_args = SimpleNamespace(
        large_field=large_field,
        large_torch=large_torch,
        small_torch=small_torch,
        narrower_corridors=narrower_corridors,
    )
    apply_runtime_flags(runtime_args)

    with patched_stage1_tuning(tuning):
        _, stats, _, winning_histories = analyze_seed_with_beam(
            stage_num=stage_num,
            seed=seed,
            top_k=top_k,
            max_depth=max_depth,
            beam_width=beam_width,
            node_budget=node_budget,
            max_travel_steps=max_travel_steps,
            lp_weight=lp_weight,
            level_weight=level_weight,
        )
        preference_rows: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        replay_path_cache = {}
        rank_rows: dict[int, int] = defaultdict(int)
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
            )
    return {
        "seed": seed,
        "wins": stats.wins,
        "leaves": stats.leaves,
        "preference_rows": {label: tuple(counts) for label, counts in preference_rows.items()},
    }


def compute_rates(preference_rows: dict[str, tuple[int, int]]) -> tuple[dict[str, float], dict[str, int], float]:
    rates: dict[str, float] = {}
    totals: dict[str, int] = {}
    for label in TARGET_LABELS:
        preferred, deferred = preference_rows.get(label, (0, 0))
        total = preferred + deferred
        totals[label] = total
        if total > 0:
            rates[label] = preferred / total
    if len(rates) != len(TARGET_LABELS):
        return rates, totals, float("inf")
    mean_rate = sum(rates.values()) / len(rates)
    variance = sum((rate - mean_rate) ** 2 for rate in rates.values()) / len(rates)
    return rates, totals, variance


def evaluate_tuning(args: argparse.Namespace, tuning: Stage1Tuning, seed_values: list[int]) -> EvaluationResult:
    runtime_args = build_runtime_args(args)
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
            runtime_args.large_field,
            runtime_args.large_torch,
            runtime_args.small_torch,
            runtime_args.narrower_corridors,
            tuning,
        )
        for seed in seed_values
    ]

    aggregate_rows: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    wins = 0
    leaves = 0

    if args.jobs <= 1:
        iterator = (evaluate_seed(task) for task in tasks)
        for result in iterator:
            wins += result["wins"]
            leaves += result["leaves"]
            for label, counts in result["preference_rows"].items():
                aggregate_rows[label][0] += counts[0]
                aggregate_rows[label][1] += counts[1]
    else:
        with ProcessPoolExecutor(max_workers=args.jobs) as executor:
            futures = [executor.submit(evaluate_seed, task) for task in tasks]
            for future in as_completed(futures):
                result = future.result()
                wins += result["wins"]
                leaves += result["leaves"]
                for label, counts in result["preference_rows"].items():
                    aggregate_rows[label][0] += counts[0]
                    aggregate_rows[label][1] += counts[1]

    normalized_rows = {label: (counts[0], counts[1]) for label, counts in aggregate_rows.items()}
    rates, totals, variance = compute_rates(normalized_rows)
    return EvaluationResult(
        tuning=tuning,
        wins=wins,
        leaves=leaves,
        preference_rows=normalized_rows,
        preference_rates=rates,
        comparison_totals=totals,
        variance=variance,
    )


def format_result(result: EvaluationResult) -> str:
    leaves = result.leaves or 1
    win_rate = result.wins / leaves
    rates_text = " ".join(
        f"{label.split(':', 1)[1]}={result.preference_rates.get(label, float('nan')):.3f}/{result.comparison_totals[label]}"
        for label in TARGET_LABELS
    )
    variance_text = "inf" if result.variance == float("inf") else f"{result.variance:.6f}"
    tuning = result.tuning
    return (
        f"b_feed={tuning.b_feed} a={tuning.count_a} A={tuning.count_A} "
        f"b={tuning.count_b} c={tuning.count_c} d={tuning.count_d} "
        f"wins={result.wins} leaves={result.leaves} win_rate={win_rate:.3f} "
        f"variance={variance_text} {rates_text}"
    )


def neighbor_tunings(base: Stage1Tuning, feed_step: int, spawn_step: int, min_b_feed: int) -> list[Stage1Tuning]:
    neighbors: list[Stage1Tuning] = []
    seen: set[Stage1Tuning] = set()

    def add(candidate: Stage1Tuning) -> None:
        if candidate not in seen:
            seen.add(candidate)
            neighbors.append(candidate)

    for delta in (-feed_step, feed_step):
        new_feed = base.b_feed + delta
        if new_feed >= min_b_feed:
            add(
                Stage1Tuning(
                    b_feed=new_feed,
                    count_a=base.count_a,
                    count_A=base.count_A,
                    count_b=base.count_b,
                    count_c=base.count_c,
                    count_d=base.count_d,
                )
            )

    for field_name in ("count_a", "count_A", "count_b", "count_c", "count_d"):
        for delta in (-spawn_step, spawn_step):
            new_value = getattr(base, field_name) + delta
            if new_value < 0:
                continue
            add(
                Stage1Tuning(
                    b_feed=base.b_feed,
                    count_a=base.count_a if field_name != "count_a" else new_value,
                    count_A=base.count_A if field_name != "count_A" else new_value,
                    count_b=base.count_b if field_name != "count_b" else new_value,
                    count_c=base.count_c if field_name != "count_c" else new_value,
                    count_d=base.count_d if field_name != "count_d" else new_value,
                )
            )

    return neighbors


def result_order_key(result: EvaluationResult) -> tuple[float, int, int]:
    variance = result.variance
    if variance == float("inf"):
        variance = 10**9
    sample_floor = min(result.comparison_totals.get(label, 0) for label in TARGET_LABELS)
    return (variance, -sample_floor, -result.wins)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Search Stage 1 balance parameters for flatter monster priority.")
    parser.add_argument("--stage", type=int, default=1, help="Only stage 1 is currently supported.")
    parser.add_argument("--seeds", type=int, default=10, help="Number of seeds to analyze.")
    parser.add_argument("--seed-start", type=int, default=1, help="First seed value to use.")
    parser.add_argument(
        "--seed-file",
        type=str,
        help="Path to a file containing explicit seed values. Whitespace and commas are accepted.",
    )
    parser.add_argument("--top-k", type=int, default=4, help="Nearest targets expanded by the analyzer.")
    parser.add_argument("--max-depth", type=int, default=30, help="Maximum beam-search depth.")
    parser.add_argument("--beam-width", type=int, default=110, help="Maximum number of beam states kept per depth.")
    parser.add_argument("--node-budget", type=int, default=10000, help="Maximum expanded child states per seed.")
    parser.add_argument("--max-travel-steps", type=int, default=500, help="Movement cap while advancing to a target.")
    parser.add_argument("--lp-weight", type=float, default=1.0, help="Weight for LP in the beam evaluation score.")
    parser.add_argument("--level-weight", type=float, default=10.0, help="Weight for level in the beam evaluation score.")
    parser.add_argument("--jobs", type=int, default=1, help="Number of worker processes to use across seeds.")
    parser.add_argument("--rounds", type=int, default=5, help="Maximum hill-climb rounds.")
    parser.add_argument("--feed-step", type=int, default=1, help="Step size for b LP recovery.")
    parser.add_argument("--spawn-step", type=int, default=1, help="Step size for Stage 1 spawn counts.")
    parser.add_argument("--min-b-feed", type=int, default=1, help="Minimum allowed LP recovery for b.")
    parser.add_argument("-F", "--large-field", action="store_true", help="Large field.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-T", "--large-torch", action="store_true", help="Large torch.")
    group.add_argument("-t", "--small-torch", action="store_true", help="Small torch.")
    parser.add_argument("-n", "--narrower-corridors", action="store_true", help="Narrower corridors.")
    return parser


def load_seed_values(args: argparse.Namespace) -> list[int]:
    if args.seed_file:
        from .branch_analyzer import load_seed_file

        return load_seed_file(args.seed_file)
    return list(range(args.seed_start, args.seed_start + args.seeds))


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.stage != 1:
        raise SystemExit("balance search currently supports only --stage 1")

    seed_values = load_seed_values(args)
    baseline = current_stage1_tuning()
    best_result = evaluate_tuning(args, baseline, seed_values)
    print("[baseline]")
    print(format_result(best_result))
    print("")

    current = baseline
    for round_index in range(1, args.rounds + 1):
        print(f"[round {round_index}]")
        candidates = neighbor_tunings(current, args.feed_step, args.spawn_step, args.min_b_feed)
        results = [evaluate_tuning(args, tuning, seed_values) for tuning in candidates]
        results.sort(key=result_order_key)
        for result in results[: min(5, len(results))]:
            print(format_result(result))
        if not results:
            print("no valid neighbors")
            break
        chosen = results[0]
        if result_order_key(chosen) >= result_order_key(best_result):
            print("no improvement")
            break
        print("")
        print("[adopted]")
        print(format_result(chosen))
        print("")
        current = chosen.tuning
        best_result = chosen

    print("[best]")
    print(format_result(best_result))


if __name__ == "__main__":
    main()
