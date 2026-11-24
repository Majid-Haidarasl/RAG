"""RFP blueprint: requirements, evaluation criteria and knowledge links of one solicitation.

A blueprint is the reviewed, evidence-backed content of an RFP (Phase 13). The
generator turns it, together with the Phase 12 key issues and gaps, into an
RFP draft in Persian and English. Every statement cites corpus documents and
may only use numbers and identifiers found there (checked by ``evidence``).

Requirement, criterion and link ids contain no digits on purpose, so the fact
checker never reads a number out of an id.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

from rag_core.shared_kernel.errors import InvariantError

WEIGHT_TOTAL = Decimal("1")


class Section(StrEnum):
    NEED = "need"
    SCOPE = "scope"
    DELIVERABLES = "deliverables"
    EXCLUSIONS = "exclusions"
    ARCHITECTURE = "architecture"
    SECURITY = "security"
    TESTING = "testing"
    RESPONSE_FORMAT = "response_format"
    EVALUATION = "evaluation"
    ACCEPTANCE = "acceptance"
    KNOWLEDGE = "knowledge"


SECTION_ORDER: tuple[str, ...] = tuple(s.value for s in Section)
MANDATORY_SECTIONS: frozenset[str] = frozenset(
    {
        "need",
        "scope",
        "deliverables",
        "exclusions",
        "response_format",
        "evaluation",
        "acceptance",
    }
)
RESPONSE_SECTIONS: tuple[str, ...] = (
    "problem_understanding",
    "architecture",
    "work_plan",
    "team_roles",
    "employer_dependencies",
    "test_plan",
    "pricing",
)


def _text(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise InvariantError(f"{name} is required")
    return text


@dataclass(frozen=True)
class Requirement:
    requirement_id: str
    section: Section
    statement_en: str
    statement_fa: str
    mandatory: bool = True
    answered_in: str = ""
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _text(self.requirement_id, "requirement id")
        if not isinstance(self.section, Section):
            object.__setattr__(self, "section", Section(self.section))
        if self.answered_in and self.answered_in not in RESPONSE_SECTIONS:
            raise InvariantError(
                f"{self.requirement_id}: unknown response section {self.answered_in!r}"
            )
        object.__setattr__(self, "evidence", tuple(self.evidence))

    def statement(self, language: str) -> str:
        return self.statement_fa if language == "fa" else self.statement_en


@dataclass(frozen=True)
class Criterion:
    criterion_id: str
    name_en: str
    name_fa: str
    weight: Decimal
    considers_en: str = ""
    considers_fa: str = ""
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _text(self.criterion_id, "criterion id")
        amount = (
            self.weight
            if isinstance(self.weight, Decimal)
            else Decimal(str(self.weight))
        )
        if amount <= 0 or amount > 1:
            raise InvariantError(
                f"{self.criterion_id}: weight must be in (0, 1], got {amount}"
            )
        object.__setattr__(self, "weight", amount)
        object.__setattr__(self, "evidence", tuple(self.evidence))

    @property
    def percent(self) -> int:
        return int((self.weight * 100).to_integral_value())

    def name(self, language: str) -> str:
        return self.name_fa if language == "fa" else self.name_en

    def considers(self, language: str) -> str:
        return self.considers_fa if language == "fa" else self.considers_en


@dataclass(frozen=True)
class KnowledgeLink:
    """Where the RFP and its evaluation result are recorded in the organization's node knowledge."""

    link_id: str
    node: str
    role_en: str
    role_fa: str
    executor: str = ""
    requirements: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _text(self.link_id, "link id")
        _text(self.node, f"{self.link_id}: node")
        object.__setattr__(self, "requirements", tuple(self.requirements))
        object.__setattr__(self, "evidence", tuple(self.evidence))

    def role(self, language: str) -> str:
        return self.role_fa if language == "fa" else self.role_en


@dataclass(frozen=True)
class Blueprint:
    blueprint_id: str
    rfp_id: str
    title_en: str
    title_fa: str
    owner_node: str
    issues: tuple[str, ...]
    requirements: tuple[Requirement, ...]
    criteria: tuple[Criterion, ...]
    item: str = ""
    reference_document: str = ""
    response_sections: tuple[str, ...] = RESPONSE_SECTIONS
    links: tuple[KnowledgeLink, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _text(self.blueprint_id, "blueprint id")
        _text(self.rfp_id, f"{self.blueprint_id}: rfp id")
        _text(self.title_en, f"{self.blueprint_id}: English title")
        _text(self.title_fa, f"{self.blueprint_id}: Persian title")
        for name in (
            "issues",
            "requirements",
            "criteria",
            "response_sections",
            "links",
        ):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        if not self.issues:
            raise InvariantError(f"{self.blueprint_id}: at least one issue is required")
        if self.item and self.item.split("/", 1)[0] not in self.issues:
            raise InvariantError(
                f"{self.blueprint_id}: item {self.item} is not under its issues"
            )
        if not self.criteria:
            raise InvariantError(
                f"{self.blueprint_id}: an RFP without evaluation criteria fails validation"
            )
        unknown = [s for s in self.response_sections if s not in RESPONSE_SECTIONS]
        if unknown:
            raise InvariantError(
                f"{self.blueprint_id}: unknown response sections {', '.join(unknown)}"
            )

    @property
    def weight_total(self) -> Decimal:
        return sum((c.weight for c in self.criteria), Decimal(0))

    def sections(self) -> tuple[str, ...]:
        present = {r.section.value for r in self.requirements}
        return tuple(s for s in SECTION_ORDER if s in present)

    def missing_mandatory(self) -> tuple[str, ...]:
        present = {r.section.value for r in self.requirements if r.mandatory}
        return tuple(
            s for s in SECTION_ORDER if s in MANDATORY_SECTIONS and s not in present
        )

    def requirement(self, requirement_id: str) -> Requirement | None:
        return next(
            (r for r in self.requirements if r.requirement_id == requirement_id), None
        )

    def criterion(self, criterion_id: str) -> Criterion | None:
        return next((c for c in self.criteria if c.criterion_id == criterion_id), None)

    def mandatory_ids(self) -> tuple[str, ...]:
        return tuple(r.requirement_id for r in self.requirements if r.mandatory)

    def linked_ids(self) -> tuple[str, ...]:
        """The RFP id, the item and the issues the RFP serves (what an RFP text must name)."""
        return tuple(
            dict.fromkeys(
                [self.rfp_id, *([self.item] if self.item else []), *self.issues]
            )
        )

    def title(self, language: str) -> str:
        return self.title_fa if language == "fa" else self.title_en
