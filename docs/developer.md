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
- `--forbid-char`: monster char to exclude from candidate choices; repeat to forbid multiple chars

The output includes aggregate win rate.
When wins are found, the analyzer also replays each winning path from the initial seed state and aggregates which monster kinds were preferred over other visible monster candidates, reported as `preference_score = (preferred - deferred) / (preferred + deferred)`, as well as which distance-rank among visible monster candidates was chosen.

To compare against a world where a specific monster is never chosen, repeat `--forbid-char`:

```bash
uv run -p .venv/bin/python python -m arlq.branch_analyzer --stage 2 --seeds 50 --seed-start 1001 --top-k 5 --beam-width 110 --node-budget 20000 --max-depth 60 --forbid-char C
```

## Validation

Lightweight validation:

```bash
uv run -p .venv/bin/python python -m compileall src
uv run -p .venv/bin/python python -c "import arlq"
```

If analysis logic changes, rerun a small batch first:

```bash
uv run -p .venv/bin/python python -m arlq.branch_analyzer --stage 1 --seeds 3 --seed-start 1 --node-budget 500
```
