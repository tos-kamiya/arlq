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

Blessed terminal UI:

```bash
uv run -p .venv/bin/python python -m arlq --terminal
```

CLI entrypoint:

```bash
uv run -p .venv/bin/python arlq-cli
```

## Gameplay Trace Record/Replay (Internal Only)

A CLI feature for system/integration testing: recording a played session's
inputs and results to a JSON trace file, and replaying a trace file headlessly to
reproduce a session and detect behavior changes by diffing the resulting trace
against the original. These CLI options are internal developer/testing tooling and
are intentionally not documented in `README.md`/`README-ja_JP.md`.

See [`gameplay-trace-spec.md`](gameplay-trace-spec.md) for the full specification
(including an "Implementation Notes" section on where the implementation
resolved details the spec had left open).

Every normal play writes a timestamped trace to the application cache and
updates `last-trace.json` there. `--output PATH` also exports the same trace to
an explicit path. `--trace PATH` replays a trace in the real UI and does not
write a new trace. `--trace auto` reads the cached `last-trace.json`; `--trace`
always requires an argument.

Add `--continue` to ignore recorded `Q` inputs and switch to live input when
the replay inputs run out. This records the replay and continued play as a new
session trace, saved to the cache. `--output PATH` can export that trace too.
`--rewind INDEX` instead replays through the selected checkpoint update, then
switches to live input. Positive indexes start at 1; negative indexes count
backward, so `-1` selects the latest checkpoint. Rewind also saves a new trace.

```bash
# Play normally; the latest trace is saved automatically.
uv run -p .venv/bin/python python -m arlq

# Replay the latest cached trace without creating a new trace.
uv run -p .venv/bin/python python -m arlq --trace auto

# Ignore a recorded quit, continue playing, and export the resulting trace.
uv run -p .venv/bin/python python -m arlq --trace trace.json --continue --output continued.json

# Resume immediately after the most recent checkpoint update.
uv run -p .venv/bin/python python -m arlq --trace auto --rewind -1
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
