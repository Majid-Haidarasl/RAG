#!/usr/bin/env bash
# Phase 2 kit setup: checks Python, optional venv, runs unit tests and the environment check.
# Needs no internet: the kit has no mandatory third-party packages.
set -u
cd "$(dirname "$0")"
PY="${PYTHON:-python3}"

echo "== 1/4 Python"
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "python3 not found -> sudo apt install python3"; exit 1
fi
"$PY" -c 'import sys; assert sys.version_info >= (3, 9), sys.version' \
  || { echo "Python 3.9+ required"; exit 1; }
"$PY" --version

echo "== 2/4 virtualenv (optional)"
if [ ! -d .venv ]; then
  if "$PY" -m venv .venv >/dev/null 2>&1; then
    echo "created .venv"
  else
    echo "venv module missing (sudo apt install python3-venv). Not needed: continuing with system python."
  fi
fi
if [ -f .venv/bin/activate ]; then
  # shellcheck disable=SC1091
  . .venv/bin/activate
  PY=python
  grep -Eq '^[[:space:]]*[A-Za-z]' requirements.txt && pip install -q -r requirements.txt || true
fi

echo "== 3/4 unit tests of the kit logic"
"$PY" -m unittest discover -s experiments/phase-02/tests || { echo "unit tests failed - send me this output"; exit 1; }

echo "== 4/4 environment check (Ollama, models, GPU)"
"$PY" experiments/phase-02/check_env.py
rc=$?
echo
if [ $rc -eq 1 ]; then
  echo "Ollama is not running. Start it:  sudo systemctl start ollama   (or: ollama serve &)"
  exit 1
fi
echo "Next:"
echo "  python3 experiments/phase-02/run_all.py --quick     # ~3-5 min smoke test"
echo "  python3 experiments/phase-02/run_all.py             # full baseline, ~15-20 min"
