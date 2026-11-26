from __future__ import annotations

from rag_core.ingestion.domain.catalog import lookup
from rag_core.qa.domain.model import QaAnswer
from rag_core.rag.domain.records import SourceRef, record_key
from rag_core.shared_kernel.errors import NotFoundError
from rag_core.shared_kernel.fact_ports import FactCheckResult
from rag_core.shared_kernel.identifiers import NodeIdentifier

from rag_api.runtime import RagRuntime
from rag_api.schemas import (
    AskResponse,
    CitationOut,
    EscalationOut,
    SourceOut,
)

_HEADING_SEP = " > "
_LANG_SUFFIXES = ("/fa", "/en")


def node_name_fa(runtime: RagRuntime, node_id: str) -> str | None:
    try:
        return runtime.scope.org.get(NodeIdentifier(node_id)).name_fa
    except NotFoundError:
        return None


def _strip_lang_suffix(label: str) -> str:
    for suffix in _LANG_SUFFIXES:
        if label.endswith(suffix):
            return label[: -len(suffix)]
    return label


def _heading_parts(heading_path: str) -> list[str]:
    if not heading_path:
        return []
    return heading_path.split(_HEADING_SEP)


def _fact_flag(result: FactCheckResult) -> str:
    return f"{result.claim.kind.value}:{result.claim.raw_text}"


def source_out(
    ref: SourceRef,
    runtime: RagRuntime,
    cited_labels: set[str],
) -> SourceOut:
    key = record_key(ref.document_id, ref.version, ref.language, ref.order)
    try:
        excerpt = runtime.retriever.store.get(key).text[:500]
    except NotFoundError:
        excerpt = ""
    entry = lookup(ref.document_id)
    title_fa = entry.title_fa if entry is not None else ref.document_id
    title_en = entry.title_en if entry is not None else ref.document_id
    return SourceOut(
        label=ref.label,
        key=key,
        document_id=ref.document_id,
        title_fa=title_fa,
        title_en=title_en,
        version=ref.version,
        language=ref.language,
        order=ref.order,
        heading_path=_heading_parts(ref.heading_path),
        page=ref.page,
        paragraph=ref.paragraph,
        excerpt=excerpt,
        cited=ref.label in cited_labels,
    )


def to_ask_response(answer: QaAnswer, runtime: RagRuntime) -> AskResponse:
    cited_labels = {
        _strip_lang_suffix(label)
        for citation in answer.citations
        if citation.valid
        for label in citation.block_labels
    }
    sources = [
        source_out(ref, runtime, cited_labels) for ref in answer.used_chunks
    ]
    sources.sort(key=lambda item: (0 if item.cited else 1))

    escalation: EscalationOut | None = None
    if answer.escalation is not None and answer.escalation.action == "escalate":
        escalation = EscalationOut(
            target=answer.escalation.target,
            target_name_fa=node_name_fa(runtime, answer.escalation.target),
            reason=answer.escalation.reason,
        )

    return AskResponse(
        status=answer.status.value,  # type: ignore[arg-type]
        grounded=answer.grounded,
        text=answer.text,
        language=answer.language,
        node_id=answer.node,
        node_name_fa=node_name_fa(runtime, answer.node),
        citations=[
            CitationOut(
                label=citation.citation.label,
                valid=citation.valid,
                granularity=citation.granularity or None,
                reason=citation.reason or None,
            )
            for citation in answer.citations
        ],
        sources=sources,
        escalation=escalation,
        fact_flags=[_fact_flag(item) for item in answer.fact_check.unsupported],
        model=answer.model or None,
        prompt_version=answer.prompt_version or None,
        timings_s={key: round(value, 3) for key, value in answer.timings_s.items()},
    )
