#!/usr/bin/env bash
# Phase 6 (0.6.0) — create a local virtualenv, install rag_core, run unit tests, ingest the corpus,
# run the knowledge lifecycle + duplicate detection (Phase 5), then validate the
# layer / node registry, document ownership and retrieval scopes (Phase 6).
# Ubuntu 24.04 / Python 3.12. The first pip install needs internet. Tests and ingest
# do not call Ollama, the GPU or the public internet.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VENV_HINT="sudo apt install -y python3.12-venv"
SOFFICE_HINT="sudo apt install -y libreoffice-writer --no-install-recommends"
POPPLER_HINT="sudo apt install -y poppler-utils"

separator_start="======== PHASE 6 SUMMARY (paste this block) ========"
separator_end="======== END PHASE 6 SUMMARY ========"

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
  fail_summary "pyproject.toml not found. Extract the zip into the repo root (e.g. ~/Desktop/RAG) and run this script from there."
fi

# LibreOffice is optional for unit tests (the .doc test is skipped) but required
# to ingest derived .doc samples. Always say how to install it when missing.
if command -v soffice >/dev/null 2>&1 || command -v libreoffice >/dev/null 2>&1; then
  echo "LibreOffice: $(soffice --version 2>/dev/null | head -n 1 || libreoffice --version 2>/dev/null | head -n 1)"
else
  echo "NOTE: LibreOffice (soffice) is not installed."
  echo "Legacy .doc conversion will fail and the DOC unit test will be skipped."
  echo "Install it with:"
  echo "  $SOFFICE_HINT"
fi

# poppler's pdftotext is the primary PDF text engine (correct Persian order).
# Without it the adapter falls back to pdfplumber and Persian PDFs fail as garbled.
if command -v pdftotext >/dev/null 2>&1; then
  echo "pdftotext: $(pdftotext -v 2>&1 | head -n 1)"
else
  echo "NOTE: poppler (pdftotext) is not installed."
  echo "Persian PDF text will be rejected as garbled and the pdftotext unit tests will be skipped."
  echo "Install it with:"
  echo "  $POPPLER_HINT"
fi

VENV="$ROOT/.venv"
if [[ ! -d "$VENV" ]]; then
  set +e
  VENV_ERR="$(python3 -m venv "$VENV" 2>&1)"
  VENV_EXIT=$?
  set -e
  if [[ "$VENV_EXIT" -ne 0 ]]; then
    echo "$VENV_ERR"
    if echo "$VENV_ERR" | grep -Eqi 'ensurepip|venv|No module named'; then
      echo
      echo "This system is missing the Python venv package."
      echo "On Ubuntu 24.04 run:"
      echo "  $VENV_HINT"
      echo "then re-run this script."
    fi
    fail_summary "python3 -m venv failed (see the hint above if the venv module is missing)"
  fi
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"

python -m pip install --upgrade pip >/tmp/rag-phase-06-pip.log 2>&1 || fail_summary "pip upgrade failed (see /tmp/rag-phase-06-pip.log)"
python -m pip install -e ".[dev]" >>/tmp/rag-phase-06-pip.log 2>&1 || fail_summary "pip install -e .[dev] failed (see /tmp/rag-phase-06-pip.log)"

set +e
pytest --strict-markers --tb=short | tee /tmp/rag-phase-06-pytest.log
PYTEST_EXIT=${PIPESTATUS[0]}
set -e

RESULT_LINE="$(grep -E 'passed|failed|error' /tmp/rag-phase-06-pytest.log | tail -n 1 | sed 's/^[[:space:]]*//' || true)"
PASSED="$(grep -Eo '[0-9]+ passed' /tmp/rag-phase-06-pytest.log | tail -n 1 | awk '{print $1}' || true)"
FAILED="$(grep -Eo '[0-9]+ failed' /tmp/rag-phase-06-pytest.log | tail -n 1 | awk '{print $1}' || true)"
ERRORS="$(grep -Eo '[0-9]+ error[s]?' /tmp/rag-phase-06-pytest.log | tail -n 1 | awk '{print $1}' || true)"
PASSED="${PASSED:-0}"
FAILED="${FAILED:-0}"
ERRORS="${ERRORS:-0}"

set +e
python scripts/run_corpus_ingest.py \
  --root "$ROOT" \
  --python-version "$PY_VER" \
  --pytest-exit "$PYTEST_EXIT" \
  --pytest-passed "$PASSED" \
  --pytest-failed "$FAILED" \
  --pytest-errors "$ERRORS" \
  --pytest-line "$RESULT_LINE"
INGEST_EXIT=$?

python scripts/run_corpus_dedup.py \
  --root "$ROOT" \
  --python-version "$PY_VER" \
  --pytest-exit "$PYTEST_EXIT" \
  --pytest-passed "$PASSED" \
  --pytest-failed "$FAILED" \
  --pytest-errors "$ERRORS" \
  --pytest-line "$RESULT_LINE"
DEDUP_EXIT=$?

python scripts/run_hierarchy_check.py \
  --root "$ROOT" \
  --python-version "$PY_VER" \
  --pytest-exit "$PYTEST_EXIT" \
  --pytest-passed "$PASSED" \
  --pytest-failed "$FAILED" \
  --pytest-errors "$ERRORS" \
  --pytest-line "$RESULT_LINE"
HIERARCHY_EXIT=$?
set -e

if [[ "$PYTEST_EXIT" -ne 0 ]]; then
  exit "$PYTEST_EXIT"
fi
if [[ "$INGEST_EXIT" -ne 0 ]]; then
  exit "$INGEST_EXIT"
fi
if [[ "$DEDUP_EXIT" -ne 0 ]]; then
  exit "$DEDUP_EXIT"
fi
exit "$HIERARCHY_EXIT"
