#!/usr/bin/env bash
# Phase 13 (0.13.0) — create a local virtualenv, install rag_core, run unit tests, ingest the corpus,
# run the knowledge lifecycle + duplicate detection (Phase 5), validate the
# layer / node registry (Phase 6), check the issue registry (Phase 7), run the
# Phase 8 RAG step, the Phase 9 executor analysis + IKE check, the Phase 10
# judge check, the Phase 11 transfer check and the Phase 12 project check,
# then the Phase 13 RFP check: RFP blueprints validated and grounded in the
# corpus, RFP generation from the Phase 12 key issues and gaps (template,
# judged by the rule judge 18/20), the proposal registry scored with the
# transparent weighted formula, the decision check, automated feedback per
# proposal, links back to node knowledge, negative controls and the CSV
# export; with Ollama also a qwen3:8b RFP summary and bidder feedback judged
# by qwen3:8b + the rule judge.
# Live steps run only when the local Ollama (http://localhost:11434) has the
# models (bge-m3 + qwen3:8b for Phases 8/9, qwen3:8b for Phases 10-13).
# The last block printed is the PHASE 13 SUMMARY. PASS depends on pytest and the
# earlier steps only; the live step is reported separately (ok / skipped / fail).
# Linux (Fedora or Ubuntu) / Python 3.12 or newer. The first pip install needs
# internet. Unit tests never call Ollama, the GPU or the public internet.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if command -v dnf >/dev/null 2>&1; then
  VENV_HINT="sudo dnf install -y python3"
  SOFFICE_HINT="sudo dnf install -y libreoffice-writer"
  POPPLER_HINT="sudo dnf install -y poppler-utils"
else
  VENV_HINT="sudo apt install -y python3-venv"
  SOFFICE_HINT="sudo apt install -y libreoffice-writer --no-install-recommends"
  POPPLER_HINT="sudo apt install -y poppler-utils"
fi
OLLAMA_HINT="ollama pull bge-m3 && ollama pull qwen3:8b"

separator_start="======== PHASE 13 SUMMARY ========"
separator_end="======== END PHASE 13 SUMMARY ========"

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
      echo "Install it with:"
      echo "  $VENV_HINT"
      echo "then re-run this script."
    fi
    fail_summary "python3 -m venv failed (see the hint above if the venv module is missing)"
  fi
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"

python -m pip install --upgrade pip >/tmp/rag-phase-13-pip.log 2>&1 || fail_summary "pip upgrade failed (see /tmp/rag-phase-13-pip.log)"
python -m pip install -e ".[dev]" >>/tmp/rag-phase-13-pip.log 2>&1 || fail_summary "pip install -e .[dev] failed (see /tmp/rag-phase-13-pip.log)"

set +e
pytest --strict-markers --tb=short | tee /tmp/rag-phase-13-pytest.log
PYTEST_EXIT=${PIPESTATUS[0]}
set -e

RESULT_LINE="$(grep -E 'passed|failed|error' /tmp/rag-phase-13-pytest.log | tail -n 1 | sed 's/^[[:space:]]*//' || true)"
PASSED="$(grep -Eo '[0-9]+ passed' /tmp/rag-phase-13-pytest.log | tail -n 1 | awk '{print $1}' || true)"
FAILED="$(grep -Eo '[0-9]+ failed' /tmp/rag-phase-13-pytest.log | tail -n 1 | awk '{print $1}' || true)"
ERRORS="$(grep -Eo '[0-9]+ error[s]?' /tmp/rag-phase-13-pytest.log | tail -n 1 | awk '{print $1}' || true)"
SKIPPED="$(grep -Eo '[0-9]+ skipped' /tmp/rag-phase-13-pytest.log | tail -n 1 | awk '{print $1}' || true)"
PASSED="${PASSED:-0}"
FAILED="${FAILED:-0}"
ERRORS="${ERRORS:-0}"
SKIPPED="${SKIPPED:-0}"

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

python scripts/run_issue_check.py \
  --root "$ROOT" \
  --python-version "$PY_VER" \
  --pytest-exit "$PYTEST_EXIT" \
  --pytest-passed "$PASSED" \
  --pytest-failed "$FAILED" \
  --pytest-errors "$ERRORS" \
  --pytest-skipped "$SKIPPED" \
  --pytest-line "$RESULT_LINE" \
  --prior "ingest=$INGEST_EXIT,dedup=$DEDUP_EXIT,hierarchy=$HIERARCHY_EXIT"
ISSUES_EXIT=$?

# Phase 8: local Ollama is optional. Without it (or without the models) the live
# step is reported as skipped and does not change PASS/FAIL.
if command -v ollama >/dev/null 2>&1; then
  echo "ollama: $(ollama --version 2>/dev/null | head -n 1)"
else
  echo "NOTE: the ollama command was not found. The Phase 8, 9, 10, 11 and 12 live steps will be skipped."
  echo "Install Ollama, then pull the models with:"
  echo "  $OLLAMA_HINT"
fi

python scripts/run_rag_demo.py \
  --root "$ROOT" \
  --python-version "$PY_VER" \
  --pytest-exit "$PYTEST_EXIT" \
  --pytest-passed "$PASSED" \
  --pytest-failed "$FAILED" \
  --pytest-errors "$ERRORS" \
  --pytest-skipped "$SKIPPED" \
  --pytest-line "$RESULT_LINE" \
  --prior "ingest=$INGEST_EXIT,dedup=$DEDUP_EXIT,hierarchy=$HIERARCHY_EXIT,issues=$ISSUES_EXIT" \
  | tee /tmp/rag-phase-13-rag.log
RAG_EXIT=${PIPESTATUS[0]}

python scripts/run_ike_check.py \
  --root "$ROOT" \
  --python-version "$PY_VER" \
  --pytest-exit "$PYTEST_EXIT" \
  --pytest-passed "$PASSED" \
  --pytest-failed "$FAILED" \
  --pytest-errors "$ERRORS" \
  --pytest-skipped "$SKIPPED" \
  --pytest-line "$RESULT_LINE" \
  --prior "ingest=$INGEST_EXIT,dedup=$DEDUP_EXIT,hierarchy=$HIERARCHY_EXIT,issues=$ISSUES_EXIT,rag=$RAG_EXIT" \
  | tee /tmp/rag-phase-13-ike.log
IKE_EXIT=${PIPESTATUS[0]}

python scripts/run_judge_check.py \
  --root "$ROOT" \
  --python-version "$PY_VER" \
  --pytest-exit "$PYTEST_EXIT" \
  --pytest-passed "$PASSED" \
  --pytest-failed "$FAILED" \
  --pytest-errors "$ERRORS" \
  --pytest-skipped "$SKIPPED" \
  --pytest-line "$RESULT_LINE" \
  --prior "ingest=$INGEST_EXIT,dedup=$DEDUP_EXIT,hierarchy=$HIERARCHY_EXIT,issues=$ISSUES_EXIT,rag=$RAG_EXIT,ike=$IKE_EXIT" \
  | tee /tmp/rag-phase-13-judge.log
JUDGE_EXIT=${PIPESTATUS[0]}

python scripts/run_transfer_check.py \
  --root "$ROOT" \
  --python-version "$PY_VER" \
  --pytest-exit "$PYTEST_EXIT" \
  --pytest-passed "$PASSED" \
  --pytest-failed "$FAILED" \
  --pytest-errors "$ERRORS" \
  --pytest-skipped "$SKIPPED" \
  --pytest-line "$RESULT_LINE" \
  --prior "ingest=$INGEST_EXIT,dedup=$DEDUP_EXIT,hierarchy=$HIERARCHY_EXIT,issues=$ISSUES_EXIT,rag=$RAG_EXIT,ike=$IKE_EXIT,judge=$JUDGE_EXIT" \
  | tee /tmp/rag-phase-13-transfer.log
TRANSFER_EXIT=${PIPESTATUS[0]}

python scripts/run_project_check.py \
  --root "$ROOT" \
  --python-version "$PY_VER" \
  --pytest-exit "$PYTEST_EXIT" \
  --pytest-passed "$PASSED" \
  --pytest-failed "$FAILED" \
  --pytest-errors "$ERRORS" \
  --pytest-skipped "$SKIPPED" \
  --pytest-line "$RESULT_LINE" \
  --prior "ingest=$INGEST_EXIT,dedup=$DEDUP_EXIT,hierarchy=$HIERARCHY_EXIT,issues=$ISSUES_EXIT,rag=$RAG_EXIT,ike=$IKE_EXIT,judge=$JUDGE_EXIT,transfer=$TRANSFER_EXIT" \
  | tee /tmp/rag-phase-13-project.log
PROJECT_EXIT=${PIPESTATUS[0]}

python scripts/run_rfp_check.py \
  --root "$ROOT" \
  --python-version "$PY_VER" \
  --pytest-exit "$PYTEST_EXIT" \
  --pytest-passed "$PASSED" \
  --pytest-failed "$FAILED" \
  --pytest-errors "$ERRORS" \
  --pytest-skipped "$SKIPPED" \
  --pytest-line "$RESULT_LINE" \
  --prior "ingest=$INGEST_EXIT,dedup=$DEDUP_EXIT,hierarchy=$HIERARCHY_EXIT,issues=$ISSUES_EXIT,rag=$RAG_EXIT,ike=$IKE_EXIT,judge=$JUDGE_EXIT,transfer=$TRANSFER_EXIT,projects=$PROJECT_EXIT" \
  | tee /tmp/rag-phase-13-rfp.log
RFP_EXIT=${PIPESTATUS[0]}
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
if [[ "$HIERARCHY_EXIT" -ne 0 ]]; then
  exit "$HIERARCHY_EXIT"
fi
if [[ "$ISSUES_EXIT" -ne 0 ]]; then
  exit "$ISSUES_EXIT"
fi
if [[ "$RAG_EXIT" -ne 0 ]]; then
  exit "$RAG_EXIT"
fi
if [[ "$IKE_EXIT" -ne 0 ]]; then
  exit "$IKE_EXIT"
fi
if [[ "$JUDGE_EXIT" -ne 0 ]]; then
  exit "$JUDGE_EXIT"
fi
if [[ "$TRANSFER_EXIT" -ne 0 ]]; then
  exit "$TRANSFER_EXIT"
fi
if [[ "$PROJECT_EXIT" -ne 0 ]]; then
  exit "$PROJECT_EXIT"
fi
exit "$RFP_EXIT"
