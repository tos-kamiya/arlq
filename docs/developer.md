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
- `-F`, `-T`, `-t`, `-n`: same field and visibility modifiers used by the game

The solver prints aggregate metrics including win count, win rate, and average ending stats.

## Branch Analyzer

The repository also includes a branch-based analyzer at [src/arlq/branch_analyzer.py](/home/toshihiro/playground/arlq/src/arlq/branch_analyzer.py).

This tool assumes the whole map is visible from the start, takes the nearest `K` contact targets, branches on each choice, and continues expanding the contact tree until terminal states or the configured search budget is exhausted.

For tractability, its path search uses an approximation: monsters and companions are treated as pass-through for routing purposes.
Distance maps are therefore reusable until a structural event changes the field or encounter state, such as wall breaking, rock or caltrop spread, or treasure unlock state changes.

Run via the script entrypoint:

```bash
uv run -p .venv/bin/python arlq-branch-analyzer --stage 1 --seeds 10 --seed-start 1
```

Run via module execution:

```bash
uv run -p .venv/bin/python python -m arlq.branch_analyzer --stage 2 --seeds 10 --seed-start 1001
```

Useful options:

- `--top-k`: number of nearest targets to branch on at each decision
- `--max-depth`: maximum contact depth in the branch tree
- `--node-budget`: maximum expanded branch nodes per seed
- `--max-travel-steps`: movement cap while advancing to a chosen target

The output includes aggregate win rate plus per-type statistics for root choices and all explored choices.

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
