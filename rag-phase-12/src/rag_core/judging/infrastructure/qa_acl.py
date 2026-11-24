"""Anti-corruption layer: Phase 8 Q&A results → judge cases.

The only module of the judging context that knows the Phase 8 answer layout
(``results/phase-08/rag-demo-*.json`` → ``live.answers``) and the sample
question file. Source text comes from index records (``ChunkRecord``) looked
up by document, language and section order.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from rag_core.judging.domain.cases import Expectation, JudgeCase, SourceBlock
from rag_core.judging.domain.rubric import OutputKind
from rag_core.qa.application.evaluation import SampleQuestion, load_samples
from rag_core.rag.domain.records import ChunkRecord

ChunkKey = tuple[str, str, int]


def chunk_texts(records: Iterable[ChunkRecord]) -> dict[ChunkKey, str]:
    out: dict[ChunkKey, str] = {}
    for r in records:
        if r.is_active:
            out.setdefault((r.document_id, r.language, int(r.order)), r.text)
    return out


def samples_by_id(path: Path) -> dict[str, SampleQuestion]:
    return {s.id: s for s in load_samples(path)}


def _cited_documents(answer: dict[str, Any]) -> set[str]:
    docs: set[str] = set()
    for c in answer.get("citations") or []:
        if not c.get("valid"):
            continue
        for label in list(c.get("blocks") or []) + [c.get("label", "")]:
            head = str(label).split(" ", 1)[0].split("/", 1)[0].strip()
            if head:
                docs.add(head.upper())
    return docs


def answer_sources(
    answer: dict[str, Any], texts: dict[ChunkKey, str]
) -> tuple[tuple[SourceBlock, ...], int]:
    """Source blocks for one answer (cited documents first) and the number of chunks not found."""
    used = [
        u
        for u in answer.get("used_chunks") or []
        if "document_id" in u and "order" in u
    ]
    counts: dict[tuple[str, int], int] = {}
    for u in used:
        key = (str(u["document_id"]), int(u["order"]))
        counts[key] = counts.get(key, 0) + 1
    cited = _cited_documents(answer)
    blocks: list[SourceBlock] = []
    missing = 0
    for u in sorted(
        used, key=lambda u: 0 if str(u["document_id"]).upper() in cited else 1
    ):
        doc, lang, order = (
            str(u["document_id"]),
            str(u.get("language", "")),
            int(u["order"]),
        )
        text = texts.get((doc, lang, order))
        if text is None:
            missing += 1
            continue
        label = f"{doc} §{order}" + (f"/{lang}" if counts[(doc, order)] > 1 else "")
        blocks.append(SourceBlock(label, text, doc, order, lang or None))
    return tuple(blocks), missing


def phase8_cases(
    answers: list[dict[str, Any]],
    samples: dict[str, SampleQuestion],
    texts: dict[ChunkKey, str],
) -> tuple[list[JudgeCase], int]:
    cases: list[JudgeCase] = []
    missing_total = 0
    for a in answers:
        sid = str(a.get("id", ""))
        sample = samples.get(sid)
        expected = str(
            a.get("expected_status")
            or (sample.expected_status if sample else "answered")
        )
        kind = OutputKind.QA_ANSWER if expected == "answered" else OutputKind.QA_REFUSAL
        sources, missing = answer_sources(a, texts)
        missing_total += missing
        status = str(a.get("status", "answered"))
        escalation = a.get("escalation") or {}
        language = str(a.get("language") or (sample.language if sample else "en"))
        cases.append(
            JudgeCase(
                case_id=f"P8-{sid}",
                kind=kind,
                language=language if language in {"fa", "en"} else "en",
                task=str(a.get("question", "")),
                output=str(a.get("text", "")),
                sources=sources,
                expectation=Expectation(
                    status=expected,
                    facts=sample.expected_facts if sample else (),
                    escalation=sample.expected_escalation if sample else "",
                ),
                status=status,
                escalation=str(escalation.get("target", ""))
                if status == "out_of_scope"
                else "",
                node=str(a.get("node", "")),
                origin="phase8-live",
            )
        )
    return cases, missing_total
