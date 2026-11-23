"""Evidence grounding: registry facts must be found in the cited corpus documents.

* project numbers (physical progress, remaining value, contract value) must
  occur in the text of the project's evidence documents, in Persian and in
  English;
* every record statement is checked with the shared-kernel
  ``FactValidator`` (Phase 8 ``CitedFactValidator``) against the text of the
  record's evidence documents: each number and identifier must be supported.

The corpus text arrives through the ``DocumentTexts`` port (a mapping
``(document_id, language) -> list of chunk texts``).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal

from rag_core.projects.domain.model import Project, ProjectRegistry, TrackRecord
from rag_core.shared_kernel.fact_ports import FactValidator

DocumentTexts = Mapping[tuple[str, str], list[str]]
NumberExtractor = Callable[[list[str]], set[Decimal]]
LANGUAGES = ("fa", "en")


def texts_for(documents: Iterable[str], language: str, texts: DocumentTexts) -> list[str]:
    out: list[str] = []
    for d in documents:
        out.extend(texts.get((d, language), []))
    return out


@dataclass(frozen=True)
class GroundingResult:
    ref: str
    language: str
    grounded: bool
    missing: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {"ref": self.ref, "language": self.language, "grounded": self.grounded, "missing": list(self.missing)}


@dataclass
class EvidenceReport:
    projects: list[GroundingResult] = field(default_factory=list)
    records: list[GroundingResult] = field(default_factory=list)

    def grounded(self, kind: str, language: str) -> int:
        rows = self.projects if kind == "projects" else self.records
        return sum(1 for r in rows if r.language == language and r.grounded)

    def failures(self) -> list[GroundingResult]:
        return [r for r in [*self.projects, *self.records] if not r.grounded]

    @property
    def ok(self) -> bool:
        return bool(self.projects or self.records) and not self.failures()

    def to_dict(self) -> dict[str, object]:
        return {"projects": [r.to_dict() for r in self.projects], "records": [r.to_dict() for r in self.records]}


def ground_project(project: Project, language: str, texts: DocumentTexts,
                   numbers_in: NumberExtractor) -> GroundingResult:
    sources = texts_for(project.evidence, language, texts)
    if not sources:
        return GroundingResult(project.project_id, language, False, ("no evidence text",))
    found = numbers_in(sources)
    missing = tuple(f"{name}={value}" for name, value in project.numbers().items()
                    if Decimal(value).normalize() not in found)
    return GroundingResult(project.project_id, language, not missing, missing)


def ground_record(record: TrackRecord, language: str, texts: DocumentTexts,
                  validator: FactValidator) -> GroundingResult:
    statement = record.statement(language)
    if not statement.strip():
        return GroundingResult(record.record_id, language, False, ("no statement",))
    sources = texts_for(record.evidence, language, texts)
    if not sources:
        return GroundingResult(record.record_id, language, False, ("no evidence text",))
    report = validator.validate(statement, sources)
    missing = tuple(r.claim.raw_text for r in report.results if r.verdict.value not in {"confirmed", "corrected"})
    return GroundingResult(record.record_id, language, not missing, missing)


def ground_registry(registry: ProjectRegistry, texts: DocumentTexts, validator: FactValidator,
                    numbers_in: NumberExtractor, languages: tuple[str, ...] = LANGUAGES) -> EvidenceReport:
    report = EvidenceReport()
    for lang in languages:
        report.projects.extend(ground_project(p, lang, texts, numbers_in) for p in registry.projects)
        report.records.extend(ground_record(r, lang, texts, validator) for r in registry.records)
    return report
