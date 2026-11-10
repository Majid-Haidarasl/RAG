#!/usr/bin/env bash
# Phase 3 — create a local virtualenv, install rag_core in editable mode, run unit tests.
# Intended for Ubuntu 24.04 with Python 3.12. No network is required after pip packages
# are present; the first pip install needs internet (or a wheel cache) for pytest only.
# Tests themselves do not call Ollama, the GPU or the network.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

separator_start="======== PHASE 3 SUMMARY (paste this block) ========"
separator_end="======== END PHASE 3 SUMMARY ========"

fail_summary() {
  local reason="$1"
  echo
  echo "$separator_start"
  echo "status: FAIL"
  echo "reason: $reason"
  echo "workdir: $ROOT"
  echo "python: $(command -v python3 || true) $(python3 --version 2>/dev/null || true)"
  echo "$separator_end"
  exit 1
}

if ! command -v python3 >/dev/null 2>&1; then
  fail_summary "python3 not found"
fi

PY_VER="$(python3 -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])')"
PY_OK="$(python3 -c 'import sys; print("yes" if sys.version_info >= (3, 12) else "no")')"
if [[ "$PY_OK" != "yes" ]]; then
  fail_summary "Python 3.12+ required, found $PY_VER"
fi

if [[ ! -f "$ROOT/pyproject.toml" ]]; then
  fail_summary "pyproject.toml not found. Extract the zip into the repo root (e.g. ~/RAG) and run this script from there."
fi

VENV="$ROOT/.venv"
if [[ ! -d "$VENV" ]]; then
  python3 -m venv "$VENV"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"

python -m pip install --upgrade pip >/tmp/rag-phase-03-pip.log 2>&1 || fail_summary "pip upgrade failed (see /tmp/rag-phase-03-pip.log)"
python -m pip install -e ".[dev]" >>/tmp/rag-phase-03-pip.log 2>&1 || fail_summary "pip install -e .[dev] failed (see /tmp/rag-phase-03-pip.log)"

START_NS="$(date +%s%N)"
set +e
pytest --strict-markers --tb=short | tee /tmp/rag-phase-03-pytest.log
PYTEST_EXIT=${PIPESTATUS[0]}
set -e
END_NS="$(date +%s%N)"
DURATION="$(python3 -c "print(round((int('$END_NS')-int('$START_NS'))/1e9, 2))")"

# Last non-empty line usually looks like "58 passed in 0.25s".
RESULT_LINE="$(grep -E 'passed|failed|error' /tmp/rag-phase-03-pytest.log | tail -n 1 | sed 's/^[[:space:]]*//' || true)"
PASSED="$(grep -Eo '[0-9]+ passed' /tmp/rag-phase-03-pytest.log | tail -n 1 | awk '{print $1}' || true)"
FAILED="$(grep -Eo '[0-9]+ failed' /tmp/rag-phase-03-pytest.log | tail -n 1 | awk '{print $1}' || true)"
ERRORS="$(grep -Eo '[0-9]+ error[s]?' /tmp/rag-phase-03-pytest.log | tail -n 1 | awk '{print $1}' || true)"
PASSED="${PASSED:-0}"
FAILED="${FAILED:-0}"
ERRORS="${ERRORS:-0}"

HOST="$(hostname 2>/dev/null || echo unknown)"
OS_LINE="$(. /etc/os-release 2>/dev/null && echo "${PRETTY_NAME:-unknown}" || uname -s)"

echo
echo "$separator_start"
if [[ "$PYTEST_EXIT" -eq 0 ]]; then
  echo "status: PASS"
else
  echo "status: FAIL"
fi
echo "kit: rag-core 0.3.0 (phase 3)"
echo "host: $HOST"
echo "os: $OS_LINE"
echo "python: $PY_VER"
echo "venv: $VENV"
echo "workdir: $ROOT"
echo "pytest_exit: $PYTEST_EXIT"
echo "passed: $PASSED"
echo "failed: $FAILED"
echo "errors: $ERRORS"
echo "duration_s: $DURATION"
echo "result_line: $RESULT_LINE"
echo "pytest_log: /tmp/rag-phase-03-pytest.log"
echo "$separator_end"

exit "$PYTEST_EXIT"
