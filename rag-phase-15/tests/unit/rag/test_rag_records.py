"""Index records, source references and metadata filters."""

import pytest

from rag_core.rag.domain.records import ChunkRecord, SearchFilters, SourceRef, record_key
from rag_core.shared_kernel.errors import InvariantError
from tests.fixtures.rag.fakes import rec, sample_records

pytestmark = [pytest.mark.rag, pytest.mark.retrieval]


def test_record_key_separates_language_and_version() -> None:
    assert record_key("AR-HR-005", "1.0", "fa", 12) == "AR-HR-005@1.0/fa#c0012"
    assert record_key("AR-HR-005", "1.0", "fa", 12) != record_key("AR-HR-005", "1.0", "en", 12)
    assert record_key("AR-HR-005", "1.0", "fa", 12) != record_key("AR-HR-005", "1.1", "fa", 12)


def test_source_ref_label_and_description() -> None:
    src = SourceRef("AR-HR-005", "1.0", "fa", 12, heading_path="۵. مرخصی ساعتی", paragraph=40, page=3)
    assert src.label == "AR-HR-005 §12"
    text = src.describe()
    for part in ("AR-HR-005 v1.0 (fa)", "§12", "p.3", "¶40", "۵. مرخصی ساعتی"):
        assert part in text
    assert src.to_dict()["label"] == "AR-HR-005 §12"


def test_source_ref_without_optional_anchors() -> None:
    src = SourceRef("AR-SW-022", "1.0", "en", 3)
    assert src.describe() == "AR-SW-022 v1.0 (en) · §3"
    assert "page" not in src.to_dict()


def test_table_anchor_described() -> None:
    assert "table 2" in SourceRef("AR-FIN-008", "1.0", "fa", 1, table=2).describe()


@pytest.mark.parametrize("field,value", [("language", "de"), ("status", "deleted"), ("key", "")])
def test_record_validation(field: str, value: str) -> None:
    data = rec("AR-HR-005", 1, "متن").to_dict()
    data[field] = value
    with pytest.raises(InvariantError):
        ChunkRecord.from_dict(data)


def test_record_round_trip_and_source() -> None:
    r = rec("AR-HR-005", 1, "متن", paragraph=7, heading="H")
    assert ChunkRecord.from_dict(r.to_dict()) == r
    assert r.source.paragraph == 7 and r.source.heading_path == "H"


@pytest.mark.parametrize(
    "status,version_status,active",
    [("active", "active", True), ("stale", "active", False), ("retired", "superseded", False),
     ("active", "superseded", False), ("active", "archived", False)],
)
def test_is_active_needs_active_chunk_and_version(status: str, version_status: str, active: bool) -> None:
    assert rec("AR-HR-005", 1, "x", status=status, version_status=version_status).is_active is active


def test_default_filter_keeps_only_active_versions() -> None:
    kept = [r for r in sample_records() if SearchFilters().admits(r)]
    assert all(r.is_active for r in kept)
    assert not any(r.version == "0.9" for r in kept)


def test_filter_can_include_inactive_for_audits() -> None:
    f = SearchFilters(active_only=False)
    assert all(f.admits(r) for r in sample_records())


def test_language_filter() -> None:
    f = SearchFilters.of(languages=["en"])
    assert {r.language for r in sample_records() if f.admits(r)} == {"en"}


def test_document_filter_is_case_insensitive_on_input() -> None:
    f = SearchFilters.of(document_ids=["ar-hr-005"])
    assert {r.document_id for r in sample_records() if f.admits(r)} == {"AR-HR-005"}


def test_layer_filter() -> None:
    f = SearchFilters.of(layers=[4])
    assert {r.document_id for r in sample_records() if f.admits(r)} == {"AR-ISS-024"}


def test_knowledge_class_filter() -> None:
    f = SearchFilters.of(knowledge_classes=["sla", "hr_policy"])
    assert {r.document_id for r in sample_records() if f.admits(r)} == {"AR-SW-022", "AR-HR-005"}


def test_combined_filters_are_conjunctive() -> None:
    f = SearchFilters.of(languages=["fa"], knowledge_classes=["hr_policy"])
    kept = [r for r in sample_records() if f.admits(r)]
    assert kept and all(r.language == "fa" and r.document_id == "AR-HR-005" for r in kept)


def test_filters_to_dict_sorted() -> None:
    d = SearchFilters.of(languages=["fa", "en"], layers=[3, 1]).to_dict()
    assert d["languages"] == ["en", "fa"] and d["layers"] == [1, 3] and d["active_only"] is True
