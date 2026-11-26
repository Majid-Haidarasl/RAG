"""Citation parsing and verification against the assembled context."""

import pytest

from rag_core.qa.domain.citations import (
    cited_blocks,
    parse_citations,
    strip_citations,
    verify_citations,
)
from rag_core.rag.domain.context import ContextAssembler
from rag_core.rag.domain.retriever import Hit
from tests.fixtures.rag.fakes import rec

pytestmark = [pytest.mark.qa]


def ctx(*records):
    return ContextAssembler().assemble(
        [Hit(r, i + 1, 1.0) for i, r in enumerate(records)]
    )


def test_parse_basic_label() -> None:
    [c] = parse_citations("زمان پاسخ ۳۰ دقیقه است [AR-SW-022 §3].")
    assert (c.document_id, c.order, c.language) == ("AR-SW-022", 3, None)
    assert c.label == "AR-SW-022 §3"


def test_parse_persian_digits_and_spacing() -> None:
    [c] = parse_citations("[AR-SW-۰۲۲ § ۱۲]")
    assert c.document_id == "AR-SW-022" and c.order == 12


def test_parse_multiple_refs_and_separators() -> None:
    cits = parse_citations(
        "x [AR-HR-005 §1; AR-HR-004 §3، AR-SW-022 §2] y [AR-ISS-024 §5/en]"
    )
    assert [c.label for c in cits] == [
        "AR-HR-005 §1",
        "AR-HR-004 §3",
        "AR-SW-022 §2",
        "AR-ISS-024 §5/en",
    ]


def test_parse_chunk_id_form_and_document_level() -> None:
    cits = parse_citations("a [AR-HR-005#c0012] b [AR-FIN-010]")
    assert (
        cits[0].order == 12 and cits[1].order is None and cits[1].label == "AR-FIN-010"
    )


def test_parse_lowercase_and_contract_like_ids() -> None:
    [c] = parse_citations("[ar-hr-005 §2]")
    assert c.document_id == "AR-HR-005"


def test_non_reference_brackets_ignored_and_duplicates_merged() -> None:
    assert parse_citations("[…] [note] [1] text") == []
    assert len(parse_citations("[AR-HR-005 §1] and again [AR-HR-005 §1]")) == 1


def test_strip_citations() -> None:
    assert "AR-HR-005" not in strip_citations("مرخصی ۲۶ روز است [AR-HR-005 §3].")


def test_valid_chunk_citation() -> None:
    c = ctx(rec("AR-HR-005", 3, "۲۶ روز"))
    [v] = verify_citations(parse_citations("[AR-HR-005 §3]"), c)
    assert v.valid and v.granularity == "chunk" and v.block_labels == ("AR-HR-005 §3",)


def test_invalid_section_and_document() -> None:
    c = ctx(rec("AR-HR-005", 3, "۲۶ روز"))
    sec, doc = verify_citations(parse_citations("[AR-HR-005 §9] [AR-BRD-003 §1]"), c)
    assert not sec.valid and sec.reason == "section not in retrieved context"
    assert not doc.valid and doc.reason == "document not in retrieved context"


def test_document_level_citation_valid_if_document_retrieved() -> None:
    c = ctx(rec("AR-HR-005", 3, "x"), rec("AR-HR-005", 4, "y"))
    [v] = verify_citations(parse_citations("[AR-HR-005]"), c)
    assert v.valid and v.granularity == "document" and len(v.block_labels) == 2


def test_language_suffix_disambiguates() -> None:
    c = ctx(rec("AR-ISS-024", 5, "فارسی"), rec("AR-ISS-024", 5, "english", lang="en"))
    [en] = verify_citations(parse_citations("[AR-ISS-024 §5/en]"), c)
    assert en.valid and en.block_labels == ("AR-ISS-024 §5/en",)
    [both] = verify_citations(parse_citations("[AR-ISS-024 §5]"), c)
    assert both.valid and len(both.block_labels) == 2


def test_cited_blocks_only_valid_ones() -> None:
    c = ctx(rec("AR-HR-005", 3, "x"), rec("AR-SW-022", 1, "y"))
    verified = verify_citations(parse_citations("[AR-HR-005 §3] [AR-SW-022 §9]"), c)
    assert [b.label for b in cited_blocks(verified, c)] == ["AR-HR-005 §3"]
    assert verified[1].to_dict()["valid"] is False
