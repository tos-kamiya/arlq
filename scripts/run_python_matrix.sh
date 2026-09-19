#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PY_VERSIONS=("3.10" "3.11" "3.12" "3.13" "3.14")
RUN_PYTEST=1
RUN_COMPILEALL=1
SKIP_INSTALL=0

usage() {
  cat <<'EOF'
Usage:
  scripts/run_python_matrix.sh [options]

Options:
  --pytest-only     Run only pytest across CPython 3.10/3.11/3.12/3.13/3.14
  --compileall-only Run only compileall across CPython 3.10/3.11/3.12/3.13/3.14
  --skip-install    Reuse existing virtual environments without reinstalling .[dev]
  -h, --help        Show this help

Default:
  Create/update .venv-3.10 .. .venv-3.14, install .[dev], then run pytest
  and compileall for each version.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --pytest-only)
      RUN_PYTEST=1
      RUN_COMPILEALL=0
      ;;
    --compileall-only)
      RUN_PYTEST=0
      RUN_COMPILEALL=1
      ;;
    --skip-install)
      SKIP_INSTALL=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

echo "==> Ensuring CPython interpreters are available"
uv python install "${PY_VERSIONS[@]}"

for py in "${PY_VERSIONS[@]}"; do
  venv=".venv-$py"
  pybin="$venv/bin/python"

  echo
  echo "==> Preparing environment for CPython $py"
  if [[ ! -x "$pybin" ]]; then
    uv venv "$venv" --python "$py"
  fi

  if [[ "$SKIP_INSTALL" -eq 0 ]]; then
    uv pip install -p "$pybin" -e ".[dev]"
  fi

  if [[ "$RUN_PYTEST" -eq 1 ]]; then
    echo "==> [$py] pytest"
    "$pybin" -m pytest
  fi

  if [[ "$RUN_COMPILEALL" -eq 1 ]]; then
    echo "==> [$py] compileall"
    "$pybin" -m compileall src
  fi
done

echo
echo "Matrix run completed."
