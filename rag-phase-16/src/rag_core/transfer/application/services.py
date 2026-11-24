"""Phase 11 transfer use cases.

* ``TransferService`` — builds and reviews one node's package for one cycle
  step (the cycle processor of the ``processing`` context calls it once per
  node, bottom-up).
* ``SuggestionService`` — optional AI transfer suggestions through a chat port
  (qwen3:8b via Ollama in production, a fake in tests).
"""

from __future__ import annotations

from collections.abc import Mapping
import time
from typing import Any, Protocol

from rag_core.models.domain.ports import LlmResult
from rag_core.shared_kernel.errors import InvariantError
from rag_core.shared_kernel.fact_ports import FactValidator
from rag_core.transfer.domain.builder import PackageDraft, TransferPackageBuilder
from rag_core.transfer.domain.items import NodeKnowledge
from rag_core.transfer.domain.levels import RuleBook
from rag_core.transfer.domain.review import (
    BuiltPackage,
    PackageJudgePort,
    PackageReviewer,
)
from rag_core.transfer.domain.suggestions import (
    SuggestionParseError,
    TransferSuggestion,
    check_suggestion,
    parse_suggestion,
    suggestion_prompt,
)


class StepLike(Protocol):
    source_node: str
    target_node: str
    target_layer: int


class TransferService:
    def __init__(
        self,
        knowledge: Mapping[str, NodeKnowledge],
        rules: RuleBook,
        builder: TransferPackageBuilder,
        reviewer: PackageReviewer,
    ) -> None:
        self.knowledge = dict(knowledge)
        self.rules = rules
        self.builder = builder
        self.reviewer = reviewer

    def knowledge_of(self, node_id: str, layer: int) -> NodeKnowledge:
        found = self.knowledge.get(node_id)
        return found if found is not None else NodeKnowledge(node_id, layer, node_id)

    def draft(
        self,
        cycle_id: str,
        step: StepLike,
        received: list[Any],
        expected_children: int = 0,
    ) -> PackageDraft:
        rule = self.rules.for_layer(step.target_layer)
        sender = self.knowledge_of(step.source_node, step.target_layer + 1)
        return self.builder.build(
            cycle_id,
            sender,
            step.target_node,
            rule,
            received,
            expected_children=expected_children,
        )

    def transfer(
        self,
        cycle_id: str,
        step: StepLike,
        received: list[Any],
        expected_children: int = 0,
    ) -> BuiltPackage:
        return self.reviewer.review(
            self.draft(cycle_id, step, received, expected_children)
        )


class SuggestionChatPort(Protocol):
    def generate(self, system: str, user: str) -> LlmResult: ...


class SuggestionService:
    def __init__(
        self,
        chat: SuggestionChatPort,
        validator: FactValidator,
        judge: PackageJudgePort | None = None,
    ) -> None:
        self.chat = chat
        self.validator = validator
        self.judge = judge

    def suggest(self, draft: PackageDraft, language: str) -> TransferSuggestion:
        if language not in {"fa", "en"}:
            raise InvariantError(f"unsupported suggestion language {language!r}")
        system, user = suggestion_prompt(draft, language)
        out = TransferSuggestion(
            draft.cycle_id,
            draft.source_node,
            draft.target_node,
            language,
            status="error",
        )
        t0 = time.perf_counter()
        try:
            result = self.chat.generate(system, user)
        except Exception as exc:  # noqa: BLE001 - a failed model call is a reported error, not a crash
            out.seconds = time.perf_counter() - t0
            out.error = f"{type(exc).__name__}: {exc}"
            return out
        out.seconds = time.perf_counter() - t0
        out.raw = result.text
        out.prompt_tokens = result.prompt_tokens
        out.completion_tokens = result.completion_tokens
        try:
            out.parsed = parse_suggestion(result.text)
        except SuggestionParseError as exc:
            out.error = str(exc)
            return out
        out.check = check_suggestion(out.parsed, draft, self.validator)
        accepted = out.check.ok
        if self.judge is not None:
            verdicts = self.judge.judge_package(draft, language, out.parsed.summary)
            out.verdicts = [v.to_dict() for v in verdicts]
            accepted = accepted and all(v.accepted for v in verdicts)
        out.status = "accepted" if accepted else "rejected"
        return out
