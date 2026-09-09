"""Run the coordinate-target GA for multiple seeds and write CSV results."""

from __future__ import annotations

import argparse
import csv
import sys
from concurrent.futures import ProcessPoolExecutor

from .solver import apply_runtime_flags
from .target_ga_solver import run_ga


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run arlq-target-ga for multiple seeds.")
    parser.add_argument("--stage", type=int, choices=(1, 2), default=1)
    parser.add_argument("--seed-start", type=int, default=1)
    parser.add_argument("--seed-count", type=int, default=10)
    parser.add_argument("--output", default="target-ga-results.csv")
    parser.add_argument("--target-length", type=int, default=50)
    parser.add_argument("--population", type=int, default=100)
    parser.add_argument("--generations", type=int, default=200)
    parser.add_argument("--max-steps", type=int, default=500)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument(
        "--seed-workers",
        type=int,
        default=1,
        help="Number of seeds to evaluate in parallel.",
    )
    parser.add_argument("--random-seed", type=int)
    parser.add_argument(
        "--stop-on-win",
        action="store_true",
        help="Stop each seed immediately after finding a winning genome.",
    )
    parser.add_argument("-F", "--large-field", action="store_true")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-T", "--large-torch", action="store_true")
    group.add_argument("-t", "--small-torch", action="store_true")
    parser.add_argument("-n", "--narrower-corridors", action="store_true")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.seed_count <= 0:
        parser.error("--seed-count must be positive")
    if args.workers <= 0:
        parser.error("--workers must be positive")
    if args.seed_workers <= 0:
        parser.error("--seed-workers must be positive")
    apply_runtime_flags(args)

    jobs = [
        (
            index,
            args.seed_start + index,
            None if args.random_seed is None else args.random_seed + index,
            args,
        )
        for index in range(args.seed_count)
    ]

    with open(args.output, "w", newline="", encoding="utf-8") as output_file:
        writer = csv.writer(output_file)
        writer.writerow(("seed", "moves"))
        if args.seed_workers > 1:
            # Avoid nested process pools: one PyPy process owns one complete GA run.
            with ProcessPoolExecutor(max_workers=args.seed_workers) as executor:
                results = executor.map(_run_seed, jobs)
                for index, seed, result in results:
                    _write_result(writer, output_file, index, seed, result, args.seed_count)
        else:
            for job in jobs:
                index, seed, result = _run_seed(job)
                _write_result(writer, output_file, index, seed, result, args.seed_count)


def _run_seed(job):
    index, seed, random_seed, args = job
    apply_runtime_flags(args)
    # Seed-level parallelism is the outer layer, so the inner evaluator is serial.
    workers = 1 if args.seed_workers > 1 else args.workers
    _, result, _ = run_ga(
        args.stage,
        seed,
        target_length=args.target_length,
        population_size=args.population,
        generations=args.generations,
        workers=workers,
        max_steps=args.max_steps,
        random_seed=random_seed,
        stop_on_win=args.stop_on_win,
        progress=False,
    )
    return index, seed, result


def _write_result(writer, output_file, index, seed, result, seed_count):
    print(
        f"seed={seed} ({index + 1}/{seed_count}) "
        f"won={result.won} steps={result.steps} lp={result.lp} level={result.level}",
        file=sys.stderr,
        flush=True,
    )
    writer.writerow((seed, result.moves if result.won else ""))
    output_file.flush()


if __name__ == "__main__":
    main()
