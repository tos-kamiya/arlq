"""Small same-seed comparison for monster respawn rules."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path

from . import defs as d
from .balance_tuner import DEFAULT_CONFIG, RunResult, current_tuning, simulate

CONDITIONS = {
    "all": (),
    "checkpoint": (),
    "no-a": ("a",),
    "no-b": ("b",),
    "no-a-b": ("a", "b"),
    "no-weak": ("a", "A", "b"),
    "no-core": ("a", "A", "b", "c", "C"),
}


def condition_config(condition: str, base: dict) -> dict:
    if condition not in CONDITIONS:
        raise ValueError(f"unknown condition: {condition}")
    config = dict(base)
    if condition == "checkpoint":
        config["respawn_mode"] = "checkpoint"
        config["respawn"] = {
            str(stage): [
                tribe.char
                for spawn in d.STAGE_TO_SPAWN_CONFIGS[stage - 1]
                for tribe in (spawn.tribe,)
                if isinstance(tribe, d.MonsterTribe)
                and tribe.char not in d.NO_RESPAWN_MONSTERS
            ]
            for stage in (1, 2)
        }
        return config
    if not CONDITIONS[condition]:
        config.pop("respawn", None)
        return config
    config["respawn"] = {}
    for stage in (1, 2):
        disabled = set(CONDITIONS[condition])
        config["respawn"][str(stage)] = [
            tribe.char
            for spawn in d.STAGE_TO_SPAWN_CONFIGS[stage - 1]
            for tribe in (spawn.tribe,)
            if isinstance(tribe, d.MonsterTribe) and tribe.char not in disabled
        ]
        if (
            stage == 1
            and config.get("stage1_c_count")
            and "C" not in disabled
            and "C" not in config["respawn"][str(stage)]
        ):
            config["respawn"][str(stage)].append("C")
    return config


@contextmanager
def temporary_stage1_c(count: int | None):
    if count is None:
        yield
        return
    if count < 0:
        raise ValueError("stage1 C count must not be negative")
    if any(spawn.tribe.char == "C" for spawn in d.SPAWN_CONFIGS_ST1):
        raise ValueError("Stage 1 already contains C")
    config = d.SpawnConfig(d.CHAR_TO_MONSTER_TRIBE["C"], count)
    d.SPAWN_CONFIGS_ST1.append(config)
    try:
        yield
    finally:
        d.SPAWN_CONFIGS_ST1.remove(config)


def _task(
    task: tuple[
        str,
        int,
        int,
        str,
        dict,
        int | None,
        int | None,
        int | None,
        int | None,
        int | None,
        int | None,
        int | None,
    ],
) -> tuple[str, RunResult]:
    (
        condition,
        seed,
        stage,
        policy,
        config,
        b_feed,
        a_feed,
        a_count,
        b_count,
        c_count,
        c_sword_uses,
        lp_max,
    ) = task
    if condition != "all" and c_sword_uses is not None:
        config = dict(config)
        config["sword_uses"] = c_sword_uses
    if condition != "all" and lp_max is not None:
        config = dict(config)
        config["lp_max"] = lp_max
    tuning = current_tuning(DEFAULT_CONFIG)
    if condition != "all" and (
        a_feed is not None
        or b_feed is not None
        or a_count is not None
        or b_count is not None
        or c_count is not None
    ):
        tuning = type(tuning)(
            tuple(
                (
                    char,
                    a_feed
                    if char == "a" and a_feed is not None
                    else b_feed
                    if char == "b" and b_feed is not None
                    else value,
                )
                for char, value in tuning.feed
            ),
            tuple(
                (
                    stage_num,
                    char,
                    a_count if char == "a" and a_count is not None else value,
                )
                for stage_num, char, value in tuning.spawn
            ),
        )
        if b_count is not None:
            tuning = type(tuning)(
                tuning.feed,
                tuple(
                    (stage_num, char, b_count if char == "b" else value)
                    for stage_num, char, value in tuning.spawn
                ),
            )
        if c_count is not None:
            tuning = type(tuning)(
                tuning.feed,
                tuple(
                    (stage_num, char, value)
                    for stage_num, char, value in tuning.spawn
                    if not (char == "C" and stage_num in (1, 2))
                )
                + ((1, "C", c_count), (2, "C", c_count)),
            )
    if stage == 1 and config.get("stage1_c_count") is not None and c_count is None:
        tuning = type(tuning)(
            tuning.feed,
            tuning.spawn + ((1, "C", config["stage1_c_count"]),),
        )
    stage1_c_count = (
        c_count
        if condition != "all" and c_count is not None
        else config.get("stage1_c_count")
    )
    with temporary_stage1_c(stage1_c_count):
        return condition, simulate(
            tuning, "respawn-compare", stage, seed, policy, config
        )


def _summary(rows: list[dict]) -> dict[str, dict]:
    summary: dict[str, dict] = {}
    for condition in CONDITIONS:
        for stage in (1, 2):
            for policy in ("discovery", "nearest", "situational"):
                group = [
                    row
                    for row in rows
                    if row["condition"] == condition
                    and row["stage"] == stage
                    and row["policy"] == policy
                ]
                if not group:
                    continue
                key = f"{condition}:stage{stage}:{policy}"
                summary[key] = {
                    "runs": len(group),
                    "wins": sum(row["won"] for row in group),
                    "clear_rate": sum(row["won"] for row in group) / len(group),
                    "end_reasons": dict(Counter(row["end_reason"] for row in group)),
                    "early_starvation_rate": sum(
                        row["end_reason"] == "lp_depleted" and row["steps"] <= 150
                        for row in group
                    )
                    / len(group),
                }
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare monster respawn rules on the same small seed set."
    )
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--seed-start", type=int, default=1)
    parser.add_argument("--max-steps", type=int, default=1000)
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument(
        "--stages",
        nargs="+",
        type=int,
        choices=(1, 2),
        default=(1, 2),
        help="Stages to evaluate (default: 1 2).",
    )
    parser.add_argument("--output", type=Path, default=Path("respawn-comparison"))
    parser.add_argument(
        "--conditions", nargs="+", choices=tuple(CONDITIONS), default=list(CONDITIONS)
    )
    parser.add_argument(
        "--b-feed", type=int, help="Food supplied by b in selected non-all conditions."
    )
    parser.add_argument(
        "--a-feed", type=int, help="Food supplied by a in selected non-all conditions."
    )
    parser.add_argument(
        "--a-count",
        type=int,
        help="Initial a count in both stages for selected non-all conditions.",
    )
    parser.add_argument(
        "--b-count",
        type=int,
        help="Initial b count in both stages for selected non-all conditions.",
    )
    parser.add_argument(
        "--c-count",
        type=int,
        help="Initial C count in both stages for selected non-all conditions.",
    )
    parser.add_argument(
        "--c-sword-uses",
        type=int,
        help="Wall breaks per c/C sword in selected non-all conditions.",
    )
    parser.add_argument(
        "--lp-max",
        type=int,
        help="Maximum LP in selected non-all conditions.",
    )
    parser.add_argument(
        "--stage1-c-count",
        type=int,
        help="Temporarily add this many C monsters to Stage 1 in every condition.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.seeds <= 0 or args.jobs <= 0:
        raise SystemExit("--seeds and --jobs must be positive")
    if args.c_sword_uses is not None and args.c_sword_uses < 0:
        raise SystemExit("--c-sword-uses must not be negative")
    if args.lp_max is not None and args.lp_max <= 0:
        raise SystemExit("--lp-max must be positive")
    base = dict(DEFAULT_CONFIG)
    base["max_steps"] = args.max_steps
    base["stalled_steps"] = 200
    base["early_turn"] = 150
    base["stage1_c_count"] = args.stage1_c_count
    policies = ("discovery", "nearest", "situational")
    tasks = [
        (
            condition,
            seed,
            stage,
            policy,
            condition_config(condition, base),
            args.b_feed,
            args.a_feed,
            args.a_count,
            args.b_count,
            args.c_count,
            args.c_sword_uses,
            args.lp_max,
        )
        for condition in args.conditions
        for seed in range(args.seed_start, args.seed_start + args.seeds)
        for stage in args.stages
        for policy in policies
    ]
    rows: list[dict] = []
    print(
        f"starting {len(tasks)} plays, conditions={len(args.conditions)}, jobs={args.jobs}",
        file=sys.stderr,
        flush=True,
    )
    if args.jobs == 1:
        results = [_task(task) for task in tasks]
    else:
        with ProcessPoolExecutor(max_workers=args.jobs) as executor:
            futures = [executor.submit(_task, task) for task in tasks]
            results = [future.result() for future in as_completed(futures)]
    for condition, result in results:
        rows.append({"condition": condition, **asdict(result)})
    rows.sort(
        key=lambda row: (row["condition"], row["seed"], row["stage"], row["policy"])
    )
    summary = _summary(rows)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "runs.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = [
        "# Respawn rule comparison",
        "",
        f"Seeds: `{args.seed_start}..{args.seed_start + args.seeds - 1}`; policies: discovery, nearest, situational.",
        f"Selected non-all conditions use a feed={args.a_feed}, b feed={args.b_feed}, a count={args.a_count}, b count={args.b_count}, C count={args.c_count}, c/C sword uses={args.c_sword_uses}, and LP max={args.lp_max} when specified."
        if args.a_feed is not None
        or args.b_feed is not None
        or args.a_count is not None
        or args.b_count is not None
        or args.c_count is not None
        or args.c_sword_uses is not None
        or args.lp_max is not None
        else "The default b feed, a count, and b count are used in every condition.",
        "All conditions use the same seeds. `all` keeps the current respawn rule; the other conditions disable respawn for the named weak monsters. Companions remain unchanged.",
        "",
        "| Condition | Stage | Policy | Clear rate | Early starvation | End reasons |",
        "| --- | ---: | --- | ---: | ---: | --- |",
    ]
    for key, metric in sorted(summary.items()):
        condition, stage, policy = key.split(":")
        lines.append(
            f"| {condition} | {stage.removeprefix('stage')} | {policy} | {metric['clear_rate']:.3f} | {metric['early_starvation_rate']:.3f} | {metric['end_reasons']} |"
        )
    (args.output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"report: {args.output / 'report.md'}")


if __name__ == "__main__":
    main()
