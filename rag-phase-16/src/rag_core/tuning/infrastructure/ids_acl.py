"""Anti-corruption layer to the Phase 13 results (AI texts that must name ids).

The Phase 13 check writes ``results/phase-13/rfp-check-<UTC>.json``. Its RFP
drafts and feedback drafts carry the fact lines and the ids an AI text must
name. ``jobs_from_phase13`` turns them into the same four jobs the Phase 13
live step ran (RFP summary + feedback for the runner-up, Persian and English),
so the id variants are compared on exactly the texts that failed there.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rag_core.rfp.infrastructure.prompts_yaml import PromptSet
from rag_core.shared_kernel.errors import InvariantError
from rag_core.tuning.domain.required_ids import (
    LISTED_VARIANTS,
    IdVariant,
    id_checklist,
    required_ids,
)


@dataclass(frozen=True)
class IdJob:
    task: str  # rfp_summary | feedback
    subject: str  # RFP id or proposal id
    language: str
    facts: tuple[str, ...]
    items: tuple[str, ...]
    gaps: tuple[str, ...] = ()

    @property
    def required(self) -> tuple[str, ...]:
        return required_ids(self.items, self.gaps)

    @property
    def reply_key(self) -> str:
        return "summary" if self.task == "rfp_summary" else "feedback"

    @property
    def label(self) -> str:
        return f"{self.task} {self.subject} {self.language}"


def newest_results(folder: Path) -> Path | None:
    files = sorted(Path(folder).glob("rfp-check-*.json"))
    return files[-1] if files else None


def _strings(value: Any) -> tuple[str, ...]:
    return tuple(str(v) for v in value) if isinstance(value, list) else ()


def jobs_from_phase13(
    payload: dict[str, Any], languages: Sequence[str] = ("fa", "en")
) -> list[IdJob]:
    """Same jobs as the Phase 13 live step: summary gaps are the items after the first one."""
    rfps = ((payload.get("rfp") or {}).get("rfps")) or {}
    if not isinstance(rfps, dict):
        raise InvariantError("phase 13 results: rfp.rfps must be a mapping")
    feedback = payload.get("feedback") or {}
    evaluation = ((payload.get("proposals") or {}).get("evaluation")) or {}
    runner_up = str(evaluation.get("runner_up") or "")
    rid = next(iter(rfps), "")
    jobs: list[IdJob] = []
    for lang in languages:
        d = (rfps.get(rid) or {}).get(lang)
        if isinstance(d, dict) and d.get("facts"):
            items = _strings(d.get("items"))
            jobs.append(
                IdJob(
                    "rfp_summary", rid, lang, _strings(d.get("facts")), items, items[1:]
                )
            )
        f = (feedback.get(runner_up) or {}).get(lang) if runner_up else None
        if isinstance(f, dict) and f.get("facts"):
            jobs.append(
                IdJob(
                    "feedback",
                    runner_up,
                    lang,
                    _strings(f.get("facts")),
                    _strings(f.get("items")),
                    _strings(f.get("gaps")),
                )
            )
    return jobs


def load_jobs(
    folder: Path, languages: Sequence[str] = ("fa", "en")
) -> tuple[list[IdJob], Path | None]:
    path = newest_results(folder)
    if path is None:
        return [], None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return jobs_from_phase13(payload, languages), path


def render_job(
    job: IdJob,
    variant: str,
    baseline: dict[str, PromptSet],
    listed: dict[str, PromptSet],
) -> tuple[str, str]:
    """(system, user) for one job. ``baseline`` / ``listed`` map task -> prompt set."""
    facts = "\n".join(job.facts)
    if variant == IdVariant.BASELINE:
        return baseline[job.task].render(
            job.language, facts=facts, items=", ".join(job.required)
        )
    if variant in LISTED_VARIANTS:
        return listed[job.task].render(
            job.language,
            facts=facts,
            checklist=id_checklist(job.required),
            items=", ".join(job.required),
        )
    raise InvariantError(f"unknown id variant {variant}")
