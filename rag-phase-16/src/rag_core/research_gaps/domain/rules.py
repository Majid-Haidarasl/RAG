"""Research-gap rules.

Each rule reads ``GapInputs`` and returns gaps. Rules can be switched off and
their base severity changed in ``config/projects.yaml``; they never call a
model and never touch files.

======  =====================  ==============================================================
code    name                   fires when
======  =====================  ==============================================================
RG      research_open          a research record is still open or conditional
KL      knowledge_lack         an active sub-issue has IKE knowledge lacks (high if blocked)
EX      missing_executor       an active sub-issue has no IKE lead and no registry executor
DEP     blocked_dependency     a blocked sub-issue waits for a sibling that is not resolved
CH      unlinked_challenge     a challenge record is not linked to any registered issue
SC      scorecard_open         a scorecard dimension is open (or only conditional: low)
ST      stale_unsolved         an unsolved-issue record whose linked issues are all closed
EV      unevidenced_record     a record cites no evidence document
OD      knowledge_outdated     knowledge age_days exceeds gap_thresholds.outdated_days
CF      sources_conflict       flagged conflicting source pair on a subject
JT      judge_below_threshold  judge total < rubric accept_total (GapThresholds.judge_min_total)
LC      low_confidence         confidence < gap_thresholds.confidence_min
======  =====================  ==============================================================
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from rag_core.research_gaps.domain.model import (
    CLOSED_STATUSES,
    SEVERITY_ORDER,
    Gap,
    GapInputs,
    GapKind,
    Severity,
)
from rag_core.shared_kernel.errors import InvariantError


@dataclass(frozen=True)
class RuleSetting:
    enabled: bool = True
    severity: str = "medium"

    def __post_init__(self) -> None:
        Severity(self.severity)  # raises ValueError for an unknown severity


RULE_NAMES: dict[str, str] = {
    "RG": "research_open",
    "KL": "knowledge_lack",
    "EX": "missing_executor",
    "DEP": "blocked_dependency",
    "CH": "unlinked_challenge",
    "SC": "scorecard_open",
    "ST": "stale_unsolved",
    "EV": "unevidenced_record",
    "OD": "knowledge_outdated",
    "CF": "sources_conflict",
    "JT": "judge_below_threshold",
    "LC": "low_confidence",
}
DEFAULT_SEVERITY: dict[str, str] = {
    "RG": "medium",
    "KL": "medium",
    "EX": "high",
    "DEP": "high",
    "CH": "medium",
    "SC": "medium",
    "ST": "low",
    "EV": "high",
    "OD": "medium",
    "CF": "high",
    "JT": "high",
    "LC": "medium",
}
RULE_ORDER = tuple(RULE_NAMES)


def _gid(code: str, subject: str) -> str:
    return f"{code}:{subject}"


def _raise(sev: Severity) -> Severity:
    return (
        Severity.HIGH
        if sev is Severity.MEDIUM
        else (Severity.MEDIUM if sev is Severity.LOW else sev)
    )


def _lower(sev: Severity) -> Severity:
    return (
        Severity.LOW
        if sev is Severity.MEDIUM
        else (Severity.MEDIUM if sev is Severity.HIGH else sev)
    )


def research_open(inputs: GapInputs, sev: Severity) -> list[Gap]:
    out: list[Gap] = []
    for r in inputs.records:
        if r.kind != "research" or r.state == "recorded":
            continue
        linked = [inputs.issue(i) for i in r.issues]
        linked_open = any(i is not None and i.active for i in linked)
        out.append(
            Gap(
                _gid("RG", r.record_id),
                "RG",
                GapKind.RESEARCH,
                _raise(sev) if linked_open else sev,
                r.record_id,
                r.title_en,
                r.title_fa,
                nodes=r.nodes,
                documents=r.evidence,
                detail=f"state={r.state}; people={len(r.people)}",
            )
        )
    return out


def knowledge_lack(inputs: GapInputs, sev: Severity) -> list[Gap]:
    out: list[Gap] = []
    for s in inputs.subissues:
        if not s.active or not s.lacks:
            continue
        severity = _raise(sev) if s.status == "blocked" else sev
        out.append(
            Gap(
                _gid("KL", s.item_id),
                "KL",
                GapKind.KNOWLEDGE,
                severity,
                s.item_id,
                f"Knowledge lack on {s.item_id}: {', '.join(s.lacks)}",
                f"کمبود دانش در {s.item_id}: {', '.join(s.lacks)}",
                issue_id=s.issue_id,
                nodes=(s.owner_node,) if s.owner_node else (),
                documents=s.lacks,
                detail=f"lacks={len(s.lacks)}; status={s.status}",
            )
        )
    return out


def missing_executor(inputs: GapInputs, sev: Severity) -> list[Gap]:
    out: list[Gap] = []
    for s in inputs.subissues:
        if not s.active or s.lead or s.executors:
            continue
        out.append(
            Gap(
                _gid("EX", s.item_id),
                "EX",
                GapKind.EXECUTOR,
                sev,
                s.item_id,
                f"No lead or executor for {s.item_id}",
                f"بدون مجری یا مسئول برای {s.item_id}",
                issue_id=s.issue_id,
                nodes=(s.owner_node,) if s.owner_node else (),
            )
        )
    return out


def blocked_dependency(inputs: GapInputs, sev: Severity) -> list[Gap]:
    out: list[Gap] = []
    for s in inputs.subissues:
        if s.status != "blocked":
            continue
        waiting = []
        for dep_id in s.depends_on:
            dep = inputs.subissue(dep_id)
            if dep is None or dep.status not in CLOSED_STATUSES:
                waiting.append(dep_id)
        if not waiting:
            continue
        out.append(
            Gap(
                _gid("DEP", s.item_id),
                "DEP",
                GapKind.DEPENDENCY,
                sev,
                s.item_id,
                f"{s.item_id} waits for {', '.join(waiting)}",
                f"{s.item_id} منتظر {', '.join(waiting)} است",
                issue_id=s.issue_id,
                nodes=(s.owner_node,) if s.owner_node else (),
                detail="waits_for=" + ",".join(waiting),
            )
        )
    return out


def unlinked_challenge(inputs: GapInputs, sev: Severity) -> list[Gap]:
    out: list[Gap] = []
    for r in inputs.records:
        if r.kind != "challenge" or r.state == "recorded":
            continue
        if any(inputs.issue(i) is not None for i in r.issues):
            continue
        out.append(
            Gap(
                _gid("CH", r.record_id),
                "CH",
                GapKind.CHALLENGE,
                sev,
                r.record_id,
                r.title_en,
                r.title_fa,
                nodes=r.nodes,
                documents=r.evidence,
                detail="no registered issue tracks this challenge",
            )
        )
    return out


def scorecard_open(inputs: GapInputs, sev: Severity) -> list[Gap]:
    out: list[Gap] = []
    for d in inputs.scorecard:
        if d.state == "recorded":
            continue
        severity = sev if d.state == "open" else _lower(sev)
        out.append(
            Gap(
                _gid("SC", d.dimension_id),
                "SC",
                GapKind.MEASUREMENT,
                severity,
                d.dimension_id,
                d.name_en,
                d.name_fa,
                documents=d.evidence,
                detail=f"state={d.state}"
                + (f"; research={d.research}" if d.research else ""),
            )
        )
    return out


def stale_unsolved(inputs: GapInputs, sev: Severity) -> list[Gap]:
    out: list[Gap] = []
    for r in inputs.records:
        if r.kind != "unsolved_issue" or not r.issues:
            continue
        linked = [inputs.issue(i) for i in r.issues]
        if all(i is not None and not i.active for i in linked):
            out.append(
                Gap(
                    _gid("ST", r.record_id),
                    "ST",
                    GapKind.STALE,
                    sev,
                    r.record_id,
                    r.title_en,
                    r.title_fa,
                    nodes=r.nodes,
                    documents=r.evidence,
                    detail="all linked issues are closed",
                )
            )
    return out


def unevidenced_record(inputs: GapInputs, sev: Severity) -> list[Gap]:
    return [
        Gap(
            _gid("EV", r.record_id),
            "EV",
            GapKind.EVIDENCE,
            sev,
            r.record_id,
            r.title_en,
            r.title_fa,
            nodes=r.nodes,
            detail="no evidence document",
        )
        for r in inputs.records
        if not r.evidence
    ]


def knowledge_outdated(inputs: GapInputs, sev: Severity) -> list[Gap]:
    limit = inputs.thresholds.outdated_days
    out: list[Gap] = []
    for k in inputs.knowledge_ages:
        if k.age_days <= limit:
            continue
        title_en = k.title_en or f"Outdated knowledge {k.document_id} ({k.age_days}d)"
        title_fa = k.title_fa or f"دانش قدیمی {k.document_id} ({k.age_days} روز)"
        out.append(
            Gap(
                _gid("OD", k.document_id),
                "OD",
                GapKind.OUTDATED,
                sev,
                k.document_id,
                title_en,
                title_fa,
                issue_id=k.issue_id,
                nodes=k.nodes,
                documents=(k.document_id,),
                detail=f"age_days={k.age_days}; limit={limit}",
            )
        )
    return out


def sources_conflict(inputs: GapInputs, sev: Severity) -> list[Gap]:
    out: list[Gap] = []
    for c in inputs.conflicts:
        docs = ", ".join(c.documents) if c.documents else c.subject
        out.append(
            Gap(
                _gid("CF", c.subject),
                "CF",
                GapKind.CONFLICT,
                sev,
                c.subject,
                f"Conflicting sources on {c.subject}: {docs}",
                f"تعارض منابع در {c.subject}: {docs}",
                issue_id=c.issue_id,
                nodes=c.nodes,
                documents=c.documents,
                detail=c.detail or "sources conflict",
            )
        )
    return out


def judge_below_threshold(inputs: GapInputs, sev: Severity) -> list[Gap]:
    min_total = inputs.thresholds.judge_min_total
    out_of = inputs.thresholds.judge_out_of
    out: list[Gap] = []
    for j in inputs.judge_scores:
        if j.total >= min_total:
            continue
        out.append(
            Gap(
                _gid("JT", j.subject),
                "JT",
                GapKind.JUDGE,
                sev,
                j.subject,
                f"Judge total {j.total}/{j.out_of} below {min_total}/{out_of} for {j.subject}",
                f"نمرهٔ داور {j.total}/{j.out_of} کمتر از {min_total}/{out_of} برای {j.subject}",
                issue_id=j.issue_id,
                nodes=j.nodes,
                detail=f"total={j.total}; min={min_total}; out_of={j.out_of}",
            )
        )
    return out


def low_confidence(inputs: GapInputs, sev: Severity) -> list[Gap]:
    floor = inputs.thresholds.confidence_min
    out: list[Gap] = []
    for c in inputs.confidences:
        if c.confidence >= floor:
            continue
        out.append(
            Gap(
                _gid("LC", c.subject),
                "LC",
                GapKind.CONFIDENCE,
                sev,
                c.subject,
                f"Low confidence {c.confidence:.2f} < {floor:.2f} for {c.subject}",
                f"اعتماد پایین {c.confidence:.2f} کمتر از {floor:.2f} برای {c.subject}",
                issue_id=c.issue_id,
                nodes=c.nodes,
                detail=f"confidence={c.confidence}; min={floor}",
            )
        )
    return out


RULES: dict[str, Callable[[GapInputs, Severity], list[Gap]]] = {
    "RG": research_open,
    "KL": knowledge_lack,
    "EX": missing_executor,
    "DEP": blocked_dependency,
    "CH": unlinked_challenge,
    "SC": scorecard_open,
    "ST": stale_unsolved,
    "EV": unevidenced_record,
    "OD": knowledge_outdated,
    "CF": sources_conflict,
    "JT": judge_below_threshold,
    "LC": low_confidence,
}


class GapRuleBook:
    def __init__(self, settings: Mapping[str, RuleSetting] | None = None) -> None:
        settings = dict(settings or {})
        unknown = sorted(set(settings) - set(RULES))
        if unknown:
            raise InvariantError(f"unknown gap rules: {', '.join(unknown)}")
        self.settings = {
            code: settings.get(code, RuleSetting(True, DEFAULT_SEVERITY[code]))
            for code in RULE_ORDER
        }

    @property
    def enabled(self) -> tuple[str, ...]:
        return tuple(code for code in RULE_ORDER if self.settings[code].enabled)

    def detect(self, inputs: GapInputs) -> list[Gap]:
        gaps: list[Gap] = []
        seen: set[str] = set()
        for code in self.enabled:
            for g in RULES[code](inputs, Severity(self.settings[code].severity)):
                if g.gap_id not in seen:
                    seen.add(g.gap_id)
                    gaps.append(g)
        return sort_gaps(gaps)


def sort_gaps(gaps: list[Gap]) -> list[Gap]:
    """Most severe first, then rule order, then subject (stable and deterministic)."""
    order = {code: i for i, code in enumerate(RULE_ORDER)}
    return sorted(
        gaps,
        key=lambda g: (SEVERITY_ORDER[g.severity], order.get(g.rule, 99), g.subject),
    )
