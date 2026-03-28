#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PY_VERSIONS=("3.10" "3.11" "3.12" "3.13")
RUN_IMPORT=1
RUN_COMPILEALL=1
RUN_SOLVER_SMOKE=1
SKIP_INSTALL=0

usage() {
  cat <<'EOF'
Usage:
  scripts/run_python_matrix.sh [options]

Options:
  --import-only      Run only `import arlq` across 3.10/3.11/3.12/3.13
  --compileall-only  Run only compileall across 3.10/3.11/3.12/3.13
  --solver-only      Run only a small solver smoke test across 3.10/3.11/3.12/3.13
  --skip-install     Reuse existing venvs without reinstalling the package
  -h, --help         Show this help

Default:
  Create/update .venv-3.10 .. .venv-3.13, install the package with .[dev], then run:
  - import arlq
  - compileall on src
  - a small solver smoke test
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --import-only)
      RUN_IMPORT=1
      RUN_COMPILEALL=0
      RUN_SOLVER_SMOKE=0
      ;;
    --compileall-only)
      RUN_IMPORT=0
      RUN_COMPILEALL=1
      RUN_SOLVER_SMOKE=0
      ;;
    --solver-only)
      RUN_IMPORT=0
      RUN_COMPILEALL=0
      RUN_SOLVER_SMOKE=1
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

  if [[ "$RUN_IMPORT" -eq 1 ]]; then
    echo "==> [$py] import arlq"
    "$pybin" -c "import arlq"
  fi

  if [[ "$RUN_COMPILEALL" -eq 1 ]]; then
    echo "==> [$py] compileall"
    "$pybin" -m compileall src
  fi

  if [[ "$RUN_SOLVER_SMOKE" -eq 1 ]]; then
    echo "==> [$py] solver smoke test"
    "$pybin" -m arlq.solver --stage 1 --games 1 --seed-start 1
  fi
done

echo
echo "Matrix run completed."
