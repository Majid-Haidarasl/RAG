"""Judge prompt set: ``string.Template`` placeholders (``${output}``).

Variables available to every judge prompt:

``criteria``      rubric guidance lines for the output kind
``reply_format``  the JSON skeleton the judge must return
``out_of``        rubric total (20)          ``accept_total``  acceptance bar (18)
``language_name`` required output language  ``task``          the question / summary task
``sources``       the source blocks (chunks or IKE facts), cut to a character budget
``output``        the text being judged       ``node``          asking node (Q&A)
``status_note``   what the system did (answered / refused / escalated)
``scope_note``    the expected behaviour for this kind of question
``reference``     reference key facts, if any ``items``         sub-issue ids a summary must name
"""

from __future__ import annotations

from dataclasses import dataclass, field
from string import Template

from rag_core.judging.domain.cases import NOT_FOUND_STATUSES, JudgeCase, SourceBlock
from rag_core.judging.domain.rubric import Rubric
from rag_core.shared_kernel.errors import InvariantError

LANGUAGE_NAMES = {"fa": "Persian (فارسی)", "en": "English"}
DEFAULT_RETRY_NOTE = (
    "Your previous reply could not be read. Reply again with ONLY the JSON object."
)
REQUIRED_USER_VARS = ("output", "sources")
REQUIRED_ANY_VARS = ("criteria", "reply_format")
DEFAULT_SCOPE_NOTES = {
    "answered": "In-scope evidence was retrieved (SOURCES). The right behaviour is a short answer grounded in the "
    "SOURCES with bracket labels.",
    "out_of_scope": "The asking node has no evidence in its own scope; the evidence belongs to another node. The "
    "right behaviour is to decline and suggest escalation to ${expected_escalation}.",
    "not_found": "No document in the node's scope answers this question. The right behaviour is to decline briefly "
    "and say what is missing, without inventing an answer.",
    "summary": "The summary must use only the FACTS.",
}


def render_sources(blocks: tuple[SourceBlock, ...], budget: int) -> str:
    out: list[str] = []
    used = 0
    for block in blocks:
        remaining = budget - used
        if out and remaining < 200:
            out.append(f"[... {len(blocks) - len(out)} more source block(s) omitted]")
            break
        body = block.text.strip()
        if len(body) > remaining:
            body = body[: max(200, remaining)].rstrip() + " …"
        out.append(f"[{block.label}]\n{body}")
        used += len(body)
    return "\n\n".join(out) if out else "(no sources were retrieved)"


def status_note(case: JudgeCase) -> str:
    if case.status == "out_of_scope":
        return f"declined as out of scope; suggested escalation: {case.escalation or 'none'}"
    if case.status in NOT_FOUND_STATUSES:
        return "declined: not enough evidence in scope"
    if case.status == "summary":
        return "summary"
    return "answered"


def reference_text(case: JudgeCase) -> str:
    facts = case.expectation.facts
    if not facts:
        return "(no reference facts; judge against the SOURCES only)"
    lines = ["Reference key facts (each line lists acceptable alternatives):"]
    lines += [f"- {' | '.join(group)}" for group in facts]
    return "\n".join(lines)


@dataclass(frozen=True)
class JudgePromptSet:
    prompt_id: str
    version: str
    kinds: tuple[str, ...]
    system: str
    user: str
    retry_note: str = DEFAULT_RETRY_NOTE
    scope_notes: dict[str, str] = field(
        default_factory=lambda: dict(DEFAULT_SCOPE_NOTES)
    )
    language_names: dict[str, str] = field(default_factory=lambda: dict(LANGUAGE_NAMES))

    def __post_init__(self) -> None:
        if not self.prompt_id.strip() or not self.version.strip():
            raise InvariantError("prompt id and version are required")
        if not self.kinds:
            raise InvariantError(
                f"{self.prompt_id}: at least one output kind is required"
            )
        for var in REQUIRED_USER_VARS:
            if "${" + var + "}" not in self.user:
                raise InvariantError(
                    f"{self.prompt_id}: user prompt must use ${{{var}}}"
                )
        for var in REQUIRED_ANY_VARS:
            if "${" + var + "}" not in self.system + self.user:
                raise InvariantError(f"{self.prompt_id}: prompt must use ${{{var}}}")

    @property
    def label(self) -> str:
        return f"{self.prompt_id}@{self.version}"

    def variables(
        self, case: JudgeCase, rubric: Rubric, sources_char_budget: int
    ) -> dict[str, str]:
        scope_key = (
            case.expectation.status
            if case.expectation.status in self.scope_notes
            else "answered"
        )
        scope = Template(self.scope_notes.get(scope_key, "")).safe_substitute(
            expected_escalation=case.expectation.escalation
            or "the node that owns the evidence"
        )
        return {
            "criteria": "\n".join(rubric.guidance_lines(case.kind.value)),
            "reply_format": rubric.reply_skeleton(),
            "out_of": str(rubric.out_of),
            "accept_total": str(rubric.accept_total),
            "language_name": self.language_names.get(case.language, case.language),
            "task": case.task.strip(),
            "sources": render_sources(case.sources, sources_char_budget),
            "output": case.output.strip() or "(empty output)",
            "node": case.node or "-",
            "status_note": status_note(case),
            "scope_note": scope,
            "reference": reference_text(case),
            "items": ", ".join(case.expectation.items) or "(not given)",
        }

    def render(
        self, case: JudgeCase, rubric: Rubric, *, sources_char_budget: int = 6000
    ) -> tuple[str, str]:
        values = self.variables(case, rubric, sources_char_budget)
        try:
            return Template(self.system).substitute(values), Template(
                self.user
            ).substitute(values)
        except (KeyError, ValueError) as exc:
            raise InvariantError(
                f"{self.prompt_id}: bad prompt variable {exc}"
            ) from exc
