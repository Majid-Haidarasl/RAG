"""Q&A prompt set, rendered with the Phase 3 ``PromptAssembler``.

Templates use ``string.Template`` placeholders (``${question}``). The
wording must not contain the literal word that makes the Phase 3 assembler
demand a citation list, because labels come with the context instead.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from string import Template

from rag_core.models.domain.model import (
    PromptAssembler,
    PromptTemplate,
    PromptVersion,
    TaskType,
)
from rag_core.shared_kernel.errors import InvariantError

REQUIRED_SYSTEM_VARS = ("answer_language", "refusal_token")
REQUIRED_USER_VARS = ("context", "question")
MESSAGE_KINDS = ("not_found", "insufficient", "out_of_scope")


@dataclass(frozen=True)
class QaPromptSet:
    prompt_id: str
    version: str
    system: str
    user: str
    refusal_token: str = "INSUFFICIENT_CONTEXT"
    language_names: dict[str, str] = field(
        default_factory=lambda: {"fa": "Persian (فارسی)", "en": "English"}
    )
    messages: dict[str, dict[str, str]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for var in REQUIRED_SYSTEM_VARS:
            if "${" + var + "}" not in self.system:
                raise InvariantError(f"system prompt must use ${{{var}}}")
        for var in REQUIRED_USER_VARS:
            if "${" + var + "}" not in self.user:
                raise InvariantError(f"user prompt must use ${{{var}}}")
        for kind in MESSAGE_KINDS:
            for lang in ("fa", "en"):
                if not self.messages.get(kind, {}).get(lang):
                    raise InvariantError(f"missing message {kind}/{lang}")

    def _template(self, part: str, text: str) -> PromptTemplate:
        tpl = PromptTemplate(f"{self.prompt_id}.{part}", TaskType.QUESTION_ANSWERING)
        tpl.publish(PromptVersion(self.version, text))
        return tpl

    def render(
        self, *, question: str, context: str, language: str, node: str
    ) -> tuple[str, str]:
        variables = {
            "answer_language": self.language_names.get(language, language),
            "refusal_token": self.refusal_token,
            "node": node,
            "question": question.strip(),
            "context": context,
        }
        assembler = PromptAssembler()
        system = assembler.assemble(
            self._template("system", self.system), self.version, variables
        )
        user = assembler.assemble(
            self._template("user", self.user), self.version, variables
        )
        return system, user

    def message(self, kind: str, language: str, **values: str) -> str:
        text = self.messages[kind].get(language) or self.messages[kind]["en"]
        return Template(text).safe_substitute(values)

    def is_refusal(self, text: str) -> bool:
        return (
            self.refusal_token in (text or "")[:200].upper().replace(" ", "_")
            or not (text or "").strip()
        )
