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
```
