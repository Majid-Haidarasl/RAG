"""Phase 14 test helpers: the shipped gold set and config, small hand-made gold items, fakes."""

from __future__ import annotations

from dataclasses import replace
from functools import lru_cache
from pathlib import Path

from rag_core.tuning.domain.gold import Evidence, GoldItem
from rag_core.tuning.infrastructure.gold_jsonl import load_gold

REPO = Path(__file__).resolve().parents[3]
DATASET = REPO / "eval" / "datasets" / "armanrayan-qa.jsonl"
CONFIG = REPO / "config" / "eval.yaml"
CALIBRATION = REPO / "data" / "judge" / "calibration-set.json"
STRICT_DIR = REPO / "config" / "prompts" / "judge_strict"
JUDGE_DIR = REPO / "config" / "prompts" / "judge"
RUBRIC = REPO / "config" / "prompts" / "judge" / "rubric.yaml"
QA_DIR = REPO / "config" / "prompts" / "qa"
RFP_DIR = REPO / "config" / "prompts" / "rfp"
IDS_DIR = REPO / "config" / "prompts" / "rfp_ids"


@lru_cache(maxsize=1)
def shipped_items() -> tuple[GoldItem, ...]:
    return tuple(load_gold(DATASET))


def by_id(item_id: str) -> GoldItem:
    return next(i for i in shipped_items() if i.id == item_id)


def simple_found(text: str, groups: tuple[tuple[str, ...], ...]) -> tuple[int, int]:
    """Plain substring stand-in for ``facts_found`` (keeps domain tests free of other contexts)."""
    low = (text or "").lower()
    return sum(1 for g in groups if any(alt.lower() in low for alt in g)), len(groups)


def simple_language(text: str, language: str) -> bool | None:
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return None
    arabic = sum(1 for ch in letters if "\u0600" <= ch <= "\u06ff") / len(letters)
    return arabic >= 0.35 if language == "fa" else arabic <= 0.65


def answered_item(language: str = "en", **changes: object) -> GoldItem:
    quote_en = "Priority 1 is complete service outage: response within 30 minutes and temporary restoration within 4 hours."
    quote_fa = "اولویت ۱ قطع کامل سرویس است: پاسخ ۳۰ دقیقه و رفع موقت ۴ ساعت."
    if language == "fa":
        item = GoldItem(
            id="T-P01-fa",
            pair="P01",
            language="fa",
            node="N-SW-SUP",
            question="زمان پاسخ اولویت ۱ چقدر است؟",
            expected_status="answered",
            expected_docs=("AR-SW-022",),
            expected_facts=(("30", "۳۰"), ("4", "۴")),
            evidence=(Evidence("AR-SW-022", "fa", quote_fa),),
            reference_answer="پاسخ ظرف ۳۰ دقیقه و رفع موقت ظرف ۴ ساعت است [AR-SW-022 §1].",
            partial_answer="پاسخ ظرف ۳۰ دقیقه است [AR-SW-022 §1].",
            origin="phase8:Q01",
        )
    else:
        item = GoldItem(
            id="T-P01-en",
            pair="P01",
            language="en",
            node="N-SW-SUP",
            question="What is the Priority 1 response time?",
            expected_status="answered",
            expected_docs=("AR-SW-022",),
            expected_facts=(("30",), ("4",)),
            evidence=(Evidence("AR-SW-022", "en", quote_en),),
            reference_answer="Response within 30 minutes and temporary restoration within 4 hours [AR-SW-022 §1].",
            partial_answer="Response within 30 minutes [AR-SW-022 §1].",
            origin="phase8:Q01",
        )
    return replace(item, **changes)  # type: ignore[arg-type]


def refusal_item(language: str = "en", **changes: object) -> GoldItem:
    text = (
        "INSUFFICIENT_CONTEXT No document in this scope covers unpaid leave."
        if language == "en"
        else "INSUFFICIENT_CONTEXT در دامنهٔ این تیم سندی دربارهٔ مرخصی بدون حقوق نیست."
    )
    question = (
        "How many days of unpaid leave?"
        if language == "en"
        else "سقف مرخصی بدون حقوق چند روز است؟"
    )
    item = GoldItem(
        id=f"T-P09-{language}",
        pair="P09",
        language=language,
        node="N-SW-WEB",
        question=question,
        expected_status="out_of_scope",
        expected_outside_docs=("AR-HR-005",),
        expected_escalation="N-CEO",
        reference_answer=text,
        detail="refusal",
        origin="phase8:Q09",
    )
    return replace(item, **changes)  # type: ignore[arg-type]


class FakeScope:
    """``ScopePort`` stand-in: node -> visible documents, document -> owner, fixed escalation target."""

    def __init__(
        self,
        visible: dict[str, set[str]],
        owners: dict[str, str],
        target: str = "N-CEO",
    ) -> None:
        self.visible = {k: frozenset(v) for k, v in visible.items()}
        self.owners = owners
        self.target = target

    def exists(self, node: str) -> bool:
        return node in self.visible

    def visible_documents(self, node: str) -> frozenset[str]:
        return self.visible[node]

    def owner_of(self, document_id: str) -> str | None:
        return self.owners.get(document_id)

    def route(self, asking: str, evidence_owners: list[str]):  # noqa: ANN201
        from rag_core.rag.domain.ports import EscalationRoute

        return EscalationRoute("escalate", self.target, "common ancestor")


class CountingEmbedder:
    def __init__(self) -> None:
        self.seen: list[list[str]] = []
        self.batch_size = 16

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.seen.append(list(texts))
        return [[float(len(t)), 1.0] for t in texts]
