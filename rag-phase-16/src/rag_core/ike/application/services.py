"""Phase 9 IKE use cases: compare an issue with knowledge, build its graph, summarize it."""

from __future__ import annotations

import time
from dataclasses import dataclass

from rag_core.ike.domain.builder import IkeGraphBuilder
from rag_core.ike.domain.comparison import IssueKnowledgeComparison, compare_knowledge
from rag_core.ike.domain.model import IkeGraph
from rag_core.ike.domain.ports import (
    FactValidator,
    KnowledgeSearchPort,
    SummaryChatPort,
)
from rag_core.ike.domain.summary import (
    IssueDigest,
    SummaryCheck,
    check_summary,
    digest,
    facts_lines,
    summary_prompt,
    template_summary,
)
from rag_core.ike.domain.views import IssueView, ReferralView
from rag_core.shared_kernel.errors import InvariantError

DEFAULT_TOP_K = 8
LANGUAGES = ("fa", "en")


class IkeService:
    """Issue-knowledge comparison (optional search port) and graph building."""

    def __init__(
        self,
        search: KnowledgeSearchPort | None = None,
        *,
        top_k: int = DEFAULT_TOP_K,
        min_lexical: float = 3.0,
        min_vector: float = 0.45,
        builder: IkeGraphBuilder | None = None,
    ) -> None:
        self.search = search
        self.top_k = top_k
        self.min_lexical = min_lexical
        self.min_vector = min_vector
        self.builder = builder or IkeGraphBuilder()

    def compare(self, issue: IssueView) -> dict[str, IssueKnowledgeComparison]:
        if self.search is None:
            return {}
        out: dict[str, IssueKnowledgeComparison] = {}
        for sub in issue.sub_items:
            result = self.search.search(sub.query, sub.owner_node, self.top_k)
            out[sub.item_id] = compare_knowledge(
                sub.item_id,
                sub.related_documents,
                result,
                min_lexical=self.min_lexical,
                min_vector=self.min_vector,
            )
        return out

    def build(
        self,
        issue: IssueView,
        referrals: dict[str, list[ReferralView]],
        comparisons: dict[str, IssueKnowledgeComparison] | None = None,
    ) -> IkeGraph:
        graph = self.builder.build(issue, referrals, comparisons)
        problems = graph.validate()
        if problems:
            raise InvariantError("IKE graph is invalid: " + "; ".join(problems[:5]))
        return graph


@dataclass(frozen=True)
class IkeSummary:
    issue_id: str
    language: str
    source: str  # "template" | "llm"
    text: str
    check: SummaryCheck
    seconds: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "issue_id": self.issue_id,
            "language": self.language,
            "source": self.source,
            "text": self.text,
            "check": self.check.to_dict(),
            "seconds": round(self.seconds, 3),
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
        }


class IkeSummaryService:
    def __init__(
        self, validator: FactValidator, chat: SummaryChatPort | None = None
    ) -> None:
        self.validator = validator
        self.chat = chat

    @staticmethod
    def digest(issue: IssueView, graph: IkeGraph) -> IssueDigest:
        return digest(issue, graph)

    def facts(
        self, issue: IssueView, graph: IkeGraph, names: dict[str, tuple[str, str]]
    ) -> list[str]:
        return facts_lines(digest(issue, graph), names)

    def template(
        self,
        issue: IssueView,
        graph: IkeGraph,
        names: dict[str, tuple[str, str]],
        language: str,
    ) -> IkeSummary:
        if language not in LANGUAGES:
            raise InvariantError(f"unsupported summary language {language!r}")
        d = digest(issue, graph)
        facts = facts_lines(d, names)
        t0 = time.perf_counter()
        text = template_summary(d, names, language)
        return IkeSummary(
            issue.issue_id,
            language,
            "template",
            text,
            check_summary(text, facts, d.item_ids, self.validator),
            time.perf_counter() - t0,
        )

    def generate(
        self,
        issue: IssueView,
        graph: IkeGraph,
        names: dict[str, tuple[str, str]],
        language: str,
    ) -> IkeSummary:
        if self.chat is None:
            raise InvariantError("no chat model configured for LLM summaries")
        if language not in LANGUAGES:
            raise InvariantError(f"unsupported summary language {language!r}")
        d = digest(issue, graph)
        facts = facts_lines(d, names)
        system, user = summary_prompt(facts, language)
        t0 = time.perf_counter()
        result = self.chat.generate(system, user)
        seconds = time.perf_counter() - t0
        text = result.text.strip()
        return IkeSummary(
            issue.issue_id,
            language,
            "llm",
            text,
            check_summary(text, facts, d.item_ids, self.validator),
            seconds,
            result.prompt_tokens,
            result.completion_tokens,
        )
