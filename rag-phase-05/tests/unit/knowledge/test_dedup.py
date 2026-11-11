"""Exact / near / overlap duplicate rules and bilingual exclusion (Phase 5)."""

import pytest

from rag_core.knowledge.domain.dedup import DedupConfig, DuplicateFinder
from tests.fixtures.knowledge.factories import LOREM_EN, LOREM_FA, record

pytestmark = [pytest.mark.knowledge, pytest.mark.dedup]


def test_exact_duplicate_survives_rendering_differences() -> None:
    a = record("a", LOREM_FA, doc="AR-HW-012", lang="fa")
    b = record("b", LOREM_FA.replace("\u200c", " ").replace("ی", "ي"), doc="AR-HR-004", lang="fa")
    rep = DuplicateFinder().find([a, b])
    assert len(rep.exact_groups) == 1
    assert rep.exact_groups[0].members == ("a", "b")
    assert rep.exact_groups[0].scope == "cross_document"
    assert rep.near_pairs == []


def test_short_texts_are_not_exact_duplicates() -> None:
    rep = DuplicateFinder().find([record("a", "Purpose and scope"), record("b", "Purpose and scope", doc="AR-Y-002")])
    assert rep.exact_groups == []


def test_same_source_pairs_are_never_compared() -> None:
    a = record("f#c1", LOREM_EN, source="f")
    b = record("f#c2", LOREM_EN, source="f")
    rep = DuplicateFinder().find([a, b])
    assert rep.exact_groups == [] and rep.near_pairs == [] and rep.overlap_pairs == []


def test_rendition_of_same_document_is_labelled() -> None:
    a = record("docx", LOREM_EN, doc="AR-SW-022", source="x.docx")
    b = record("pdf", LOREM_EN, doc="AR-SW-022", source="x.pdf")
    assert DuplicateFinder().find([a, b]).exact_groups[0].scope == "rendition"


def test_near_duplicate_detected_after_small_edit() -> None:
    edited = LOREM_EN.replace("written approval", "signed approval")
    rep = DuplicateFinder().find([record("a", LOREM_EN, doc="AR-A-001"), record("b", edited, doc="AR-B-002")])
    assert len(rep.near_pairs) == 1
    pair = rep.near_pairs[0]
    assert pair.jaccard >= 0.80 and pair.kind == "near"
    assert rep.exact_groups == []


def test_unrelated_texts_are_distinct() -> None:
    other = " ".join(f"token{i}" for i in range(80))
    rep = DuplicateFinder().find([record("a", LOREM_EN, doc="AR-A-001"), record("b", other, doc="AR-B-002")])
    assert rep.near_pairs == [] and rep.overlap_pairs == [] and rep.exact_groups == []


def test_containment_overlap_when_short_chunk_is_inside_long_one() -> None:
    extra = " ".join(f"extra{i}" for i in range(120))
    long_text = LOREM_EN + " " + extra
    rep = DuplicateFinder().find([record("short", LOREM_EN, doc="AR-A-001"), record("long", long_text, doc="AR-B-002")])
    assert len(rep.overlap_pairs) == 1
    pair = rep.overlap_pairs[0]
    assert pair.contained == "short" and pair.containment >= 0.95 and pair.jaccard < 0.80


def test_fa_en_translation_pair_is_not_a_duplicate() -> None:
    fa = record("fa", LOREM_FA, doc="AR-HW-012", lang="fa")
    en = record("en", LOREM_EN, doc="AR-HW-012", lang="en")
    rep = DuplicateFinder().find([fa, en])
    assert rep.exact_groups == [] and rep.near_pairs == [] and rep.overlap_pairs == []


def test_bilingual_numeric_table_is_excluded_even_when_hashes_match() -> None:
    # Persian digits normalize to Latin, so a numbers-only table is identical
    # in both language versions. Same document + different language = pair, not duplicate.
    rows_fa = " ".join(f"۱۴۰{i} ۲۵۰۰{i} ۳۱{i}" for i in range(10))
    rows_en = " ".join(f"140{i} 2500{i} 31{i}" for i in range(10))
    fa = record("fa", rows_fa, doc="AR-FIN-008", lang="fa")
    en = record("en", rows_en, doc="AR-FIN-008", lang="en")
    rep = DuplicateFinder().find([fa, en])
    assert rep.exact_groups == []
    assert rep.bilingual_pairs_excluded == 1
    assert rep.bilingual_excluded_by_rule["exact"] == 1


def test_same_numbers_in_different_documents_are_still_flagged() -> None:
    rows = " ".join(f"140{i} 2500{i} 31{i}" for i in range(10))
    rep = DuplicateFinder().find([record("a", rows, doc="AR-FIN-008"), record("b", rows, doc="AR-FIN-009", lang="fa")])
    assert len(rep.exact_groups) == 1


def test_boilerplate_shingles_are_ignored_for_overlap_candidates() -> None:
    header = "Document ID controlled copy approved by the board internal use only revision record"
    recs = [record(f"d{i}", header + " " + " ".join(f"u{i}x{j}" for j in range(60)), doc=f"AR-D-{i:03d}") for i in range(12)]
    rep = DuplicateFinder(DedupConfig(boilerplate_min_sources=3, boilerplate_source_fraction=0.1)).find(recs)
    assert rep.overlap_pairs == []


def test_lsh_recall_matches_reference_on_small_set() -> None:
    texts = [LOREM_EN, LOREM_EN.replace("laptop", "notebook"), LOREM_EN.replace("month", "quarter")]
    recs = [record(f"k{i}", t, doc=f"AR-K-{i:03d}") for i, t in enumerate(texts)]
    rep = DuplicateFinder().find(recs)
    assert rep.reference_near_pairs == len(rep.near_pairs) == 3
    assert rep.lsh_recall == 1.0


def test_duplicate_keys_are_rejected() -> None:
    with pytest.raises(ValueError):
        DuplicateFinder().find([record("a", "x"), record("a", "y")])


def test_report_serializes_to_plain_dict() -> None:
    d = DuplicateFinder().find([record("a", LOREM_EN, doc="AR-A-001"), record("b", LOREM_EN, doc="AR-B-002")]).to_dict()
    assert d["exact_group_count"] == 1 and d["by_scope"]["exact_groups"]["cross_document"] == 1
    assert set(d["timings_s"]) >= {"exact", "near_minhash_lsh", "overlap_index", "total"}
