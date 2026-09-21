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

```bash
# Play normally (GUI or --terminal) while recording inputs/results:
uv run -p .venv/bin/python python -m arlq --trace-record trace.json

# Replay headlessly and write trace.replay.json; diff the two to spot
# behavior changes after a code change:
uv run -p .venv/bin/python python -m arlq --trace-replay trace.json

# Same, but also render the replay to the real UI as it runs:
uv run -p .venv/bin/python python -m arlq --trace-replay trace.json --trace-replay-watch

# Compare the recorded trace against the replayed one to spot behavior
# changes (e.g. after a code change). "recorded_at" always differs (it is a
# timestamp), so ignore that line; any other diff means behavior changed.
diff trace.json trace.replay.json
```

`--trace-replay` writes its output next to the input trace by default
(`trace.json` -> `trace.replay.json`; see `--trace-replay-output` to pick a
different path).

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
