# Developer Notes

## Environment

This project assumes a local `uv`-managed virtual environment at `.venv`.

Typical setup:

```bash
uv sync
```

All commands below assume that `.venv` already exists and should be run from the repository root.

## Running The Game

Pygame UI:

```bash
uv run -p .venv/bin/python python -m arlq
```

curses UI:

```bash
uv run -p .venv/bin/python python -m arlq --curses
```

CLI entrypoint:

```bash
uv run -p .venv/bin/python arlq-cli
```

## Solver

The repository includes a heuristic solver for balance experiments at [src/arlq/solver.py](/home/toshihiro/playground/arlq/src/arlq/solver.py).

It is not intended to mimic human play. Instead, it uses full game-state information and a fixed strategy to simulate many runs and estimate clear rates.

Run via the script entrypoint:

```bash
uv run -p .venv/bin/python arlq-solver --stage 1 --games 100 --seed-start 1
```

Run via module execution:

```bash
uv run -p .venv/bin/python python -m arlq.solver --stage 2 --games 100 --seed-start 1001
```

Useful options:

- `--stage`: target stage to simulate
- `--games`: number of runs
- `--seed-start`: first seed value in the batch
- `--max-steps`: cap per-run turns
- `--print-winning-seeds`: print only the seed values that ended in a win
- `--print-winning-seeds-only`: print only winning seed values, one per line, with no summary
- `-F`, `-T`, `-t`, `-n`: same field and visibility modifiers used by the game

The solver prints aggregate metrics including win count, win rate, and average ending stats.

## Branch Analyzer

The repository also includes a beam-search based analyzer at [src/arlq/branch_analyzer.py](/home/toshihiro/playground/arlq/src/arlq/branch_analyzer.py).

This tool assumes the whole map is visible from the start.
At each depth it expands the nearest `K` contact targets from each beam state, evaluates the resulting states, and keeps only the top-scoring states for the next depth.

For tractability, its path search uses an approximation: monsters and companions are treated as pass-through for routing purposes.
Distance maps are therefore reusable until a structural event changes the field or encounter state, such as wall breaking, rock or caltrop spread, or treasure unlock state changes.
It also prunes branches that would intentionally re-contact the same monster and lose a second time without first becoming strong enough to beat it.

Run via the script entrypoint:

```bash
uv run -p .venv/bin/python arlq-branch-analyzer --stage 1 --seeds 10 --seed-start 1
```

Run via module execution:

```bash
uv run -p .venv/bin/python python -m arlq.branch_analyzer --stage 2 --seeds 10 --seed-start 1001
```

Useful options:

- `--seed-file`: read explicit seed values from a file instead of using `--seeds` and `--seed-start`
- `--top-k`: number of nearest targets to expand from each beam state
- `--max-depth`: maximum beam-search depth
- `--beam-width`: maximum number of states kept at each depth
- `--node-budget`: maximum expanded child states per seed
- `--max-travel-steps`: movement cap while advancing to a chosen target
- `--lp-weight`: weight of LP in the pool evaluation score
- `--level-weight`: weight of level in the pool evaluation score
- `--jobs`: number of worker processes to use across seeds

The output includes aggregate win rate.
When wins are found, the analyzer also replays each winning path from the initial seed state and aggregates which monster kinds were preferred over other visible monster candidates, reported as `preference_score = (preferred - deferred) / (preferred + deferred)`, as well as which distance-rank among visible monster candidates was chosen.

Typical workflow:

```bash
uv run -p .venv/bin/python python -m arlq.solver --stage 1 --games 100 --seed-start 1 --print-winning-seeds-only > winning_seeds.txt
uv run -p .venv/bin/python python -m arlq.branch_analyzer --stage 1 --seed-file winning_seeds.txt
```

## Balance Search

The repository also includes a balance-search helper at [src/arlq/balance_search.py](/home/toshihiro/playground/arlq/src/arlq/balance_search.py).

This command performs a small hill-climb around the current constants.

For Stage 1 it adjusts:

- `b` LP recovery
- `SPAWN_CONFIGS_ST1` counts for `a`, `A`, `b`, `c`, and `d`

The default Stage 1 flattening targets are `b`, `d`, `a`, and `c`.

For Stage 2 it adjusts:

- `SPAWN_CONFIGS_ST2` counts for `a`, `A`, `b`, `c`, `C`, and `d`

The default Stage 2 flattening targets are `a`, `A`, `b`, `c`, `C`, and `d`.

At each round it tests `+/- step` neighbors of the current best setting and adopts the best improvement.
The optimization target is the variance of the same `preference_score` metric across the selected monster set.

Run via the script entrypoint:

```bash
uv run -p .venv/bin/python arlq-balance-search --stage 1 --seeds 10 --seed-start 1
```

Useful options:

- `--seed-file`: read explicit seed values from a file
- `--targets`: override the default flattened monster set
- `--top-k`, `--max-depth`, `--beam-width`, `--node-budget`: analyzer settings reused for each evaluation
- `--jobs`: number of worker processes to use across seeds inside each evaluation
- `--rounds`: maximum hill-climb rounds
- `--feed-step`: step size for `b` LP recovery where supported
- `--spawn-step`: step size for spawn counts

Typical workflow:

```bash
uv run -p .venv/bin/python python -m arlq.solver --stage 1 --games 100 --seed-start 1 --print-winning-seeds-only > winning_seeds.txt
uv run -p .venv/bin/python arlq-balance-search --stage 1 --seed-file winning_seeds.txt --top-k 4 --beam-width 110 --node-budget 10000 --max-depth 30 --jobs 4
```

Stage 2 example:

```bash
uv run -p .venv/bin/python python -m arlq.solver --stage 2 --games 100 --seed-start 1001 --print-winning-seeds-only > winning_seeds_st2.txt
uv run -p .venv/bin/python arlq-balance-search --stage 2 --seed-file winning_seeds_st2.txt --top-k 4 --beam-width 110 --node-budget 10000 --max-depth 30 --jobs 4
```

## Validation

Lightweight validation:

```bash
uv run -p .venv/bin/python python -m compileall src
uv run -p .venv/bin/python python -c "import arlq"
```

If solver logic changes, rerun a small batch first:

```bash
uv run -p .venv/bin/python python -m arlq.solver --stage 1 --games 20 --seed-start 1
uv run -p .venv/bin/python python -m arlq.solver --stage 2 --games 20 --seed-start 1001
uv run -p .venv/bin/python python -m arlq.branch_analyzer --stage 1 --seeds 3 --seed-start 1 --node-budget 500
```
