"""Basic fact check: ids and numbers must appear in the cited chunks."""

import pytest

from rag_core.qa.domain.fact_check import (
    CitedFactValidator,
    extract_identifiers,
    extract_numbers,
    flagged,
    source_numbers,
)
from rag_core.shared_kernel.fact_ports import FactKind, FactValidator, FactVerdict
from rag_core.shared_kernel.identifiers import DocumentId

pytestmark = [pytest.mark.qa]


def verdicts(report):  # noqa: ANN001, ANN201
    return {r.claim.raw_text: r.verdict for r in report.results}


def test_implements_shared_kernel_port() -> None:
    validator: FactValidator = CitedFactValidator()
    assert validator.validate("x", ["x"]).results == ()


def test_identifier_extraction_kinds() -> None:
    claims = extract_identifiers("طبق AR-LEG-009 و قرارداد AR-CNT-1402-118، زیرمسئله AR-ISS-024/WIN با N-SW-WIN و PRJ-AZP-118")
    kinds = {c.raw_text: c.kind for c in claims}
    assert kinds["AR-LEG-009"] is FactKind.DOCUMENT_ID
    assert kinds["AR-CNT-1402-118"] is FactKind.DOCUMENT_ID
    assert kinds["AR-ISS-024/WIN"] is FactKind.ISSUE_ID
    assert kinds["N-SW-WIN"] is FactKind.NODE_ID
    assert "PRJ-AZP-118" in kinds
    assert "AR-ISS-024" not in kinds, "the issue id is not counted twice"


def test_number_extraction_normalizes_digits_and_separators() -> None:
    values = {c.normalized for c in extract_numbers("۱٬۴۸۰ میلیون و 2,180 و ۷۸٫۸ و 30%")}
    assert values == {"1480", "2180", "78.8", "30"}


def test_numbers_inside_ids_and_labels_ignored() -> None:
    values = {c.normalized for c in extract_numbers("AR-HR-005 P1 L4 qwen3 v1.0 گزارش")}
    assert values == set()


def test_source_numbers_include_number_words() -> None:
    nums = source_numbers(["Level 1 repair within four working hours", "سه روز کاری"])
    assert {1, 4, 3} <= {int(n) for n in nums}


def test_confirmed_when_in_cited_chunk() -> None:
    report = CitedFactValidator().validate(
        "مرخصی ساعتی ۴ ساعت در روز و ۱۶ ساعت در ماه است [AR-HR-005 §5].",
        ["Hourly leave is limited to 4 hours per day and 16 hours per month."],
    )
    assert report.all_supported and set(verdicts(report).values()) == {FactVerdict.CONFIRMED}


def test_number_word_in_source_confirms_digit_in_answer() -> None:
    report = CitedFactValidator().validate("Level 1 takes 4 working hours.", ["Level 1 repair within four working hours"])
    assert report.all_supported


def test_unsupported_number_flagged() -> None:
    report = CitedFactValidator().validate("Unpaid leave up to 45 days [AR-HR-005 §3].", ["up to 30 days"])
    assert verdicts(report)["45"] is FactVerdict.UNSUPPORTED
    assert [r.claim.raw_text for r in flagged(report)] == ["45"]
    assert not report.all_supported and len(report.unsupported) == 1


def test_number_only_in_uncited_context_is_flagged_not_unsupported() -> None:
    report = CitedFactValidator().validate("It is 654 million.", ["advance 30 percent"], context_texts=["654 million toman"])
    assert verdicts(report)["654"] is FactVerdict.FLAGGED


def test_document_id_confirmed_by_cited_document_itself() -> None:
    report = CitedFactValidator().validate("AR-SW-022 sets 30 minutes.", ["30 minutes"],
                                           source_document_ids=[DocumentId("AR-SW-022")])
    assert report.all_supported


def test_unknown_document_id_unsupported() -> None:
    report = CitedFactValidator().validate("See AR-HR-099.", ["nothing"])
    assert verdicts(report)["AR-HR-099"] is FactVerdict.UNSUPPORTED


def test_citation_brackets_not_checked_as_claims() -> None:
    report = CitedFactValidator().validate("Thirty minutes [AR-SW-022 §12].", ["thirty minutes"])
    assert report.results == ()


def test_persian_thousands_in_source_match_latin_answer() -> None:
    report = CitedFactValidator().validate("Operating expense was 1480 million toman.", ["هزینهٔ عملیاتی ۱٬۴۸۰ میلیون تومان"])
    assert report.all_supported
