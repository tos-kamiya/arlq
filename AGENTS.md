# AGENTS.md

This file gives repository-specific guidance to coding agents working in this project.

## Project Summary

- Project name: `arlq`
- Type: small Python game package
- Runtime: Python 3.10+
- Main dependency: `pygame`
- Alternate UI: terminal mode via `curses`
- Packaging: `hatchling`
- Source root: `src/arlq`

ARLQ is a compact rogue-like game. Most gameplay logic lives in a small number of modules, so changes in one file often affect overall behavior.

## Repository Layout

- `src/arlq/arlq.py`: main game loop, maze generation, spawning, field creation, visibility handling, CLI entry flow
- `src/arlq/defs.py`: constants, entity classes, tribe definitions, spawn tables
- `src/arlq/pygame_funcs.py`: Pygame rendering and input handling
- `src/arlq/curses_funcs.py`: curses rendering and input handling
- `src/arlq/utils.py`: shared helpers
- `src/arlq/__init__.py`: public package entrypoints
- `src/arlq/__about__.py`: version source for packaging
- `README.md` and `README.ja_JP.md`: user-facing documentation in English and Japanese
- `pyproject.toml`: package metadata and script entrypoints

## Entry Points And Local Run Commands

Use the local virtualenv when available.

- GUI mode: `uv run -p .venv/bin/python python -m arlq`
- CLI script mode: `uv run -p .venv/bin/python arlq-cli`
- curses mode: `uv run -p .venv/bin/python python -m arlq --curses`

If `python -m arlq` does not work in the current environment, fall back to:

- `uv run -p .venv/bin/python python -c "import arlq; arlq.main()"`

## Working Rules For This Repo

- Preserve the current architecture. Do not introduce heavy abstractions for a small codebase unless they remove clear duplication.
- Keep gameplay constants and tribe/spawn definitions centralized in `src/arlq/defs.py`.
- Keep renderer-specific behavior in `pygame_funcs.py` or `curses_funcs.py`; avoid pushing UI-specific logic into shared game logic unless both frontends need it.
- When changing gameplay behavior, verify whether README text also needs to change.
- Prefer small, local edits. This project is easier to maintain when the control flow stays explicit.
- Maintain compatibility with both GUI and curses modes unless the task explicitly targets only one frontend.
- Avoid adding new dependencies unless they are clearly necessary.

## Validation Expectations

There is currently no dedicated test suite in the repository. For most changes, validate with targeted local checks:

- Syntax/import check: `uv run -p .venv/bin/python python -m compileall src`
- Basic import check: `uv run -p .venv/bin/python python -c "import arlq"`
- For gameplay or rendering changes, run the game manually in the affected mode when feasible.

When working in a headless or non-interactive environment:

- Prefer `python -m compileall src` and import checks first.
- State clearly if GUI or curses runtime validation could not be performed.

## Documentation Expectations

Update documentation when behavior visible to players changes:

- `README.md` for English docs
- `README.ja_JP.md` for Japanese docs
- `README-pypi.md` only when package summary or install-facing text changes

Keep English and Japanese gameplay descriptions reasonably aligned.

## Editing Notes

- Follow existing plain Python style; the codebase is simple and mostly procedural.
- Keep comments sparse and practical.
- Do not rewrite large files just to modernize style.
- Be careful with balancing constants across stages and monster tables; small numeric changes can materially change difficulty.

## Commit Message Convention

- Use semantic commit messages.
- Prefer Conventional Commits style such as `feat: ...`, `fix: ...`, `docs: ...`, `refactor: ...`, `test: ...`, or `chore: ...`.
- For documentation-only changes like this file or README updates, use `docs: ...`.
