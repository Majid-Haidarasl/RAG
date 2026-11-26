"""IKE summary generation: graph → digest → facts → template or LLM text.

* ``digest`` reads one issue's IKE graph back into a per-sub-issue view
  (lead, collaborators, cited / suggested knowledge, dependencies, lacks).
* ``facts_lines`` turns the digest into plain English fact lines. These lines
  are the only source a generated summary may use.
* ``template_summary`` renders a deterministic Persian or English summary
  from the same digest (always available, no model).
* ``summary_prompt`` builds the system / user prompt for the local chat
  model (qwen3:8b, think off).
* ``check_summary`` runs the shared-kernel ``FactValidator`` (Phase 8
  ``CitedFactValidator``): every identifier and number in the summary must
  occur in the facts; it also counts which sub-issue ids are mentioned.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rag_core.ike.domain.builder import NOTE_CITED
from rag_core.ike.domain.model import IkeGraph, RelationType
from rag_core.ike.domain.views import IssueView
from rag_core.ike.infrastructure.prompt_yaml import (
    IkeSummaryPromptSet,
    load_ike_summary_prompts,
)
from rag_core.shared_kernel.fact_ports import FactValidator, FactVerdict
from rag_core.shared_kernel.numerals import normalize_digits

STATUS_FA = {
    "open": "باز",
    "triaged": "بررسی‌شده",
    "in_progress": "در جریان",
    "blocked": "مسدود",
    "resolved": "حل‌شده",
    "closed": "بسته",
    "reopened": "بازگشایی‌شده",
}

_PROMPTS_DIR = Path(__file__).resolve().parents[4] / "config" / "prompts" / "ike"
_DEFAULT_PROMPTS: IkeSummaryPromptSet | None = None


def default_ike_summary_prompts() -> IkeSummaryPromptSet:
    global _DEFAULT_PROMPTS
    if _DEFAULT_PROMPTS is None:
        _DEFAULT_PROMPTS = load_ike_summary_prompts(_PROMPTS_DIR)
    return _DEFAULT_PROMPTS


def __getattr__(name: str) -> Any:
    prompts = default_ike_summary_prompts()
    if name == "SYSTEM_EN":
        return prompts.system_en
    if name == "SYSTEM_FA":
        return prompts.system_fa
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


@dataclass(frozen=True)
class SubItemDigest:
    item_id: str
    title: str
    title_fa: str
    owner_node: str
    status: str
    lead: str | None
    collaborators: tuple[str, ...]
    knowledge: tuple[str, ...]
    suggested: tuple[str, ...]
    depends_on: tuple[str, ...]
    lacks: tuple[tuple[str, str], ...]
    acceptance: str


@dataclass(frozen=True)
class IssueDigest:
    issue: IssueView
    items: tuple[SubItemDigest, ...]

    @property
    def item_ids(self) -> tuple[str, ...]:
        return tuple(i.item_id for i in self.items)

    @property
    def lacks(self) -> list[tuple[str, str, str]]:
        return [
            (i.item_id, target, note) for i in self.items for target, note in i.lacks
        ]


def digest(issue: IssueView, graph: IkeGraph) -> IssueDigest:
    items: list[SubItemDigest] = []
    for sub in issue.sub_items:
        can = sorted(
            graph.incoming(sub.item_id, RelationType.CAN_HANDLE),
            key=lambda r: -r.confidence.value,
        )
        lead = next(
            (r.source_id for r in can if r.source_note.startswith("lead")), None
        )
        collaborators = tuple(
            r.source_id for r in can if r.source_note.startswith("collaborator")
        )
        rel = graph.outgoing(sub.item_id, RelationType.RELATES_TO)
        items.append(
            SubItemDigest(
                item_id=sub.item_id,
                title=sub.title,
                title_fa=sub.title_fa,
                owner_node=sub.owner_node,
                status=sub.status,
                lead=lead,
                collaborators=collaborators,
                knowledge=tuple(
                    r.target_id for r in rel if r.source_note.startswith(NOTE_CITED)
                ),
                suggested=tuple(
                    r.target_id for r in rel if not r.source_note.startswith(NOTE_CITED)
                ),
                depends_on=tuple(
                    r.target_id
                    for r in graph.outgoing(sub.item_id, RelationType.DEPENDS_ON)
                ),
                lacks=tuple(
                    (r.target_id, r.source_note)
                    for r in graph.outgoing(sub.item_id, RelationType.KNOWLEDGE_LACK)
                ),
                acceptance="board"
                if sub.reserved_decision
                else f"team_owner:{sub.owner_node}",
            )
        )
    return IssueDigest(issue, tuple(items))


def _join(
    values: tuple[str, ...] | list[str], sep: str = ", ", empty: str = "none"
) -> str:
    return sep.join(values) if values else empty


def _name(
    names: dict[str, tuple[str, str]], executor_id: str | None, fa: bool = False
) -> str:
    if executor_id is None:
        return "-" if fa else "none"
    en, fa_name = names.get(executor_id, (executor_id, ""))
    return (fa_name or en) if fa else en


def facts_lines(d: IssueDigest, names: dict[str, tuple[str, str]]) -> list[str]:
    i = d.issue
    head = f"issue {i.issue_id}: {i.title} | owner {i.owner_node} | status {i.status} | progress {i.progress_percent}%"
    if i.contract_ref:
        head += f" | contract {i.contract_ref}"
    if i.customer:
        head += f" | customer {i.customer}"
    lines = [head, f"sub-issues: {_join(list(d.item_ids))}"]
    for it in d.items:
        lines.append(
            f"sub-issue {it.item_id}: {it.title} | owner {it.owner_node} | status {it.status} | "
            f"lead {_name(names, it.lead)} | collaborators {_join([_name(names, c) for c in it.collaborators])} | "
            f"knowledge {_join(it.knowledge)} | depends on {_join(it.depends_on)} | acceptance {it.acceptance}"
        )
        if it.suggested:
            lines.append(f"suggested knowledge {it.item_id}: {_join(it.suggested)}")
    for item_id, target, note in d.lacks:
        lines.append(f"knowledge lack {item_id}: {target} ({note})")
    return lines


def template_summary(
    d: IssueDigest, names: dict[str, tuple[str, str]], language: str
) -> str:
    i = d.issue
    if language == "fa":
        out = [
            (
                f"خلاصهٔ مسئله {i.issue_id}: {i.title_fa or i.title}. مالک {i.owner_node}، وضعیت "
                f"{STATUS_FA.get(i.status, i.status)}، پیشرفت {i.progress_percent}٪."
            )
        ]
        for it in d.items:
            collab = _join(
                [_name(names, c, fa=True) for c in it.collaborators], "، ", "-"
            )
            out.append(
                f"- {it.item_id} ({it.title_fa or it.title}؛ مالک {it.owner_node}؛ {STATUS_FA.get(it.status, it.status)}): "
                f"مجری اصلی {_name(names, it.lead, fa=True)}؛ همکاران {collab}؛ دانش {_join(it.knowledge, '، ', '-')}؛ "
                f"وابسته به {_join(it.depends_on, '، ', '-')}؛ پذیرش {it.acceptance}."
            )
        if d.lacks:
            out.append(
                "کمبودهای دانش: "
                + "؛ ".join(f"{item} ← {target}" for item, target, _ in d.lacks)
                + "."
            )
        else:
            out.append("کمبود دانش ثبت نشد.")
        return "\n".join(out)
    out = [
        f"Issue {i.issue_id}: {i.title}. Owner {i.owner_node}, status {i.status}, progress {i.progress_percent}%."
    ]
    for it in d.items:
        out.append(
            f"- {it.item_id} ({it.title}; owner {it.owner_node}; {it.status}): lead {_name(names, it.lead)}; "
            f"collaborators {_join([_name(names, c) for c in it.collaborators])}; knowledge {_join(it.knowledge)}; "
            f"depends on {_join(it.depends_on)}; acceptance {it.acceptance}."
        )
    if d.lacks:
        out.append(
            "Knowledge gaps: "
            + "; ".join(
                f"{item} -> {target} ({note})" for item, target, note in d.lacks
            )
            + "."
        )
    else:
        out.append("No knowledge gap recorded.")
    return "\n".join(out)


def summary_prompt(
    facts: list[str],
    language: str,
    prompts: IkeSummaryPromptSet | None = None,
) -> tuple[str, str]:
    prompts = prompts or default_ike_summary_prompts()
    return prompts.render(language, facts="\n".join(facts))


@dataclass(frozen=True)
class SummaryCheck:
    grounded: bool
    unsupported: tuple[str, ...]
    flagged: tuple[str, ...]
    mentioned: tuple[str, ...]
    total_items: int
    claims: int = 0

    @property
    def coverage(self) -> str:
        return f"{len(self.mentioned)}/{self.total_items}"

    def to_dict(self) -> dict[str, object]:
        return {
            "grounded": self.grounded,
            "unsupported": list(self.unsupported),
            "flagged": list(self.flagged),
            "mentioned": list(self.mentioned),
            "coverage": self.coverage,
            "claims": self.claims,
        }


def check_summary(
    text: str, facts: list[str], item_ids: tuple[str, ...], validator: FactValidator
) -> SummaryCheck:
    report = validator.validate(text, ["\n".join(facts)])
    unsupported = tuple(
        r.claim.raw_text for r in report.results if r.verdict is FactVerdict.UNSUPPORTED
    )
    flagged = tuple(
        r.claim.raw_text for r in report.results if r.verdict is FactVerdict.FLAGGED
    )
    upper = normalize_digits(text).upper()
    mentioned = tuple(i for i in item_ids if i.upper() in upper)
    return SummaryCheck(
        not unsupported and not flagged,
        unsupported,
        flagged,
        mentioned,
        len(item_ids),
        len(report.results),
    )
