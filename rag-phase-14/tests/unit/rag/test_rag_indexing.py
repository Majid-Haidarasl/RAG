"""Index records from the Phase 5 lifecycle and the persistent SQLite index."""

from datetime import date
from pathlib import Path

import pytest

from rag_core.ingestion.domain.model import (
    FileFormat,
    IngestedDocument,
    SourceAnchor,
    TextChunk,
)
from rag_core.knowledge.application.lifecycle import KnowledgeLifecycleService
from rag_core.rag.application.indexing import (
    IndexBuilder,
    build_retriever,
    mark_exact_duplicates,
    records_from_lifecycle,
)
from rag_core.rag.infrastructure.sqlite_store import SqliteIndexStore
from rag_core.shared_kernel.language import LanguageCode
from tests.fixtures.rag.fakes import FakeEmbedder, rec, sample_records

pytestmark = [pytest.mark.rag, pytest.mark.retrieval]


def doc(doc_id: str, lang: str, sha: str, texts: list[str]) -> IngestedDocument:
    chunks = tuple(
        TextChunk(
            f"{doc_id}#c{i:04d}",
            i,
            t,
            "بخش ۱",
            (
                SourceAnchor(
                    doc_id, i, 0, len(t), paragraph_index=10 + i, heading_path="بخش ۱"
                ),
            ),
        )
        for i, t in enumerate(texts)
    )
    return IngestedDocument(
        path=Path(f"corpus/{lang}/{doc_id}.docx"),
        file_format=FileFormat.DOCX,
        document_id=doc_id,
        language=LanguageCode(lang),
        text="\n".join(texts),
        blocks=(),
        headings=(),
        page_count=0,
        file_sha256=sha,
        byte_size=100,
        chunks=chunks,
    )


def lifecycle_with_update() -> tuple[KnowledgeLifecycleService, list[IngestedDocument]]:
    svc = KnowledgeLifecycleService()
    v1 = doc(
        "AR-HW-012", "fa", "sha-1", ["تعمیر سطح ۱ ظرف سه روز کاری.", "قطعات انبار."]
    )
    en = doc(
        "AR-HW-012",
        "en",
        "sha-en",
        ["Level 1 repair within four working hours.", "Workshop stock."],
    )
    v2 = doc(
        "AR-HW-012", "fa", "sha-2", ["تعمیر سطح ۱ ظرف دو روز کاری.", "قطعات انبار."]
    )
    for d in (v1, en):
        svc.ingest(d, effective_from=date(2024, 10, 1))
    svc.ingest(v2, effective_from=date(2026, 11, 11))
    return svc, [v1, en, v2]


def test_records_cover_all_versions_with_lifecycle_status() -> None:
    svc, docs = lifecycle_with_update()
    records = records_from_lifecycle(
        svc.items(), docs, owner_of=lambda d: "N-HW-REP", layer_of=lambda n: 3
    )
    by_version = {(r.language, r.version, r.version_status) for r in records}
    assert ("fa", "1.0", "superseded") in by_version and (
        "fa",
        "1.1",
        "active",
    ) in by_version
    assert ("en", "1.0", "active") in by_version
    retired = [r for r in records if r.version == "1.0" and r.language == "fa"]
    assert retired and all(not r.is_active for r in retired)
    assert all(r.owner_node == "N-HW-REP" and r.layer == 3 for r in records)
    assert all(r.knowledge_class for r in records)


def test_paragraph_anchor_attached_from_phase4_chunk() -> None:
    svc, docs = lifecycle_with_update()
    records = records_from_lifecycle(svc.items(), docs)
    active_fa = [r for r in records if r.is_active and r.language == "fa"]
    assert {r.paragraph for r in active_fa} == {10, 11}
    assert all(r.heading_path == "بخش ۱" for r in active_fa)


def test_owner_falls_back_to_catalog_owner() -> None:
    svc, docs = lifecycle_with_update()
    records = records_from_lifecycle(svc.items(), docs)
    assert {r.owner_node for r in records} == {str(svc.items()[0].owning_node)}


def test_stale_version_never_retrieved() -> None:
    svc, docs = lifecycle_with_update()
    retriever = build_retriever(records_from_lifecycle(svc.items(), docs))
    res = retriever.retrieve("تعمیر سطح ۱ روز کاری", None)
    assert res.hits and all(
        h.record.version == "1.1" for h in res.hits if h.record.language == "fa"
    )


def test_exact_duplicates_marked_within_language_only() -> None:
    a = rec("AR-HR-004", 1, "کنترل مرز", content_hash="same")
    b = rec("AR-HR-006", 1, "کنترل مرز", content_hash="same")
    c = rec("AR-HR-006", 1, "boundary control", lang="en", content_hash="same")
    marked = {r.key: r for r in mark_exact_duplicates([a, b, c])}
    assert marked[b.key].duplicate_of == a.key
    assert marked[a.key].duplicate_of == "" and marked[c.key].duplicate_of == ""


def test_inactive_records_not_grouped() -> None:
    a = rec("AR-HR-004", 1, "x", content_hash="h")
    b = rec(
        "AR-HR-006",
        1,
        "x",
        content_hash="h",
        status="retired",
        version_status="superseded",
    )
    assert all(r.duplicate_of == "" for r in mark_exact_duplicates([a, b]))


def test_sqlite_records_round_trip(tmp_path: Path) -> None:
    with SqliteIndexStore(tmp_path / "ix.sqlite") as store:
        store.replace_records(sample_records())
        assert store.records() == sorted(sample_records(), key=lambda r: r.key)
        store.set_meta("embedding_model", "m")
        assert store.get_meta("embedding_model") == "m" and store.get_meta("x") is None


def test_index_builder_embeds_once_then_reuses(tmp_path: Path) -> None:
    records = sample_records()
    emb = FakeEmbedder()
    path = tmp_path / "ix.sqlite"
    with SqliteIndexStore(path) as store:
        first = IndexBuilder(store, emb, "fake-emb", batch_size=3).refresh(records)
    active = sum(r.is_active for r in records)
    assert (
        first.embedded == active
        and first.reused == 0
        and first.batches == 3
        and first.dim == 64
    )
    assert first.by_language == {"fa": 4, "en": 4}
    with SqliteIndexStore(path) as store:
        second = IndexBuilder(store, emb, "fake-emb").refresh(records)
        index = store.load_vectors("fake-emb")
    assert second.embedded == 0 and second.reused == active and second.dim == 64
    assert len(index) == active and emb.texts == active


def test_changed_and_removed_chunks_refresh(tmp_path: Path) -> None:
    records = sample_records()
    emb = FakeEmbedder()
    with SqliteIndexStore(tmp_path / "ix.sqlite") as store:
        IndexBuilder(store, emb, "fake-emb").refresh(records)
        changed = [
            rec(
                "AR-HR-005",
                1,
                "متن تازه",
                owner="N-HR",
                cls="hr_policy",
                paragraph=12,
                heading="۵. مرخصی ساعتی",
            )
        ] + records[1:-2]
        report = IndexBuilder(store, emb, "fake-emb").refresh(changed)
        assert report.embedded == 1
        assert report.removed == 1  # AR-HW-012 v1.0 active chunk dropped
        assert len(store.load_vectors("fake-emb")) == sum(r.is_active for r in changed)


def test_model_change_drops_old_vectors(tmp_path: Path) -> None:
    records = sample_records()
    with SqliteIndexStore(tmp_path / "ix.sqlite") as store:
        IndexBuilder(store, FakeEmbedder(), "old").refresh(records)
        report = IndexBuilder(store, FakeEmbedder(), "new").refresh(records)
        assert report.removed == sum(r.is_active for r in records)
        assert len(store.load_vectors("old")) == 0
        assert report.to_dict()["model"] == "new"


def test_progress_callback(tmp_path: Path) -> None:
    seen: list[tuple[int, int]] = []
    with SqliteIndexStore(tmp_path / "ix.sqlite") as store:
        IndexBuilder(store, FakeEmbedder(), "m", batch_size=4).refresh(
            sample_records(), lambda d, t: seen.append((d, t))
        )
    assert seen[-1] == (8, 8)


def test_loaded_vectors_drive_hybrid_retrieval(tmp_path: Path) -> None:
    records = sample_records()
    emb = FakeEmbedder()
    with SqliteIndexStore(tmp_path / "ix.sqlite") as store:
        IndexBuilder(store, emb, "m").refresh(records)
        vectors = store.load_vectors("m")
    r = build_retriever(records, vectors=vectors, embedder=emb)
    assert r.retrieve("hourly leave", None).hits[0].record.document_id == "AR-HR-005"
