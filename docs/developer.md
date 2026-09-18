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

## Validation

Automated tests:

```bash
uv run -p .venv/bin/python pytest
```

Lightweight validation:

```bash
uv run -p .venv/bin/python python -m compileall src
uv run -p .venv/bin/python python -c "import arlq"
```
