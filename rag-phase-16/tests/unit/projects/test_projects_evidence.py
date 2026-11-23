"""Phase 12 evidence grounding: registry numbers and statements must be in the cited documents."""

import pytest

from rag_core.projects.domain.evidence import ground_project, ground_record, ground_registry, texts_for
from rag_core.projects.infrastructure.corpus_acl import document_texts
from rag_core.qa.domain.fact_check import CitedFactValidator, source_numbers
from tests.fixtures.projects.samples import project, record, registry
from tests.fixtures.rag.fakes import rec

pytestmark = [pytest.mark.projects]

TEXTS = {
    ("AR-FIN-008", "en"): ["The Azarpakhsh warehouse system has a remaining billable value of 1,240 million toman "
                           "and physical progress of 62 percent; the contract price is 2,180 million toman."],
    ("AR-FIN-008", "fa"): ["سامانه انبار آذرپخش مانده ۱٬۲۴۰ میلیون تومان و پیشرفت فیزیکی ۶۲ درصد دارد؛ "
                           "مبلغ قرارداد ۲٬۱۸۰ میلیون تومان است."],
    ("AR-TRN-026", "en"): ["This cycle's achievement is an explicit issue-knowledge-executor path for AR-ISS-024."],
    ("AR-TRN-026", "fa"): ["دستاورد این چرخه مسیر صریح مسئله، دانش و مجری برای AR-ISS-۰۲۴ است."],
}


def test_project_numbers_found_in_both_languages() -> None:
    for lang in ("fa", "en"):
        r = ground_project(project(), lang, TEXTS, source_numbers)
        assert r.grounded, r


def test_wrong_project_number_is_missing() -> None:
    r = ground_project(project(progress_percent=87), "en", TEXTS, source_numbers)
    assert not r.grounded and r.missing == ("progress_percent=87",)


def test_project_without_evidence_text() -> None:
    r = ground_project(project(evidence=("AR-HW-012",)), "en", TEXTS, source_numbers)
    assert not r.grounded and r.missing == ("no evidence text",)


def test_record_statement_grounded_with_persian_digits() -> None:
    v = CitedFactValidator()
    assert ground_record(record(), "en", TEXTS, v).grounded
    assert ground_record(record(), "fa", TEXTS, v).grounded


def test_record_statement_with_invented_number_or_id() -> None:
    v = CitedFactValidator()
    bad_number = record(statement_en="The path covers 7 teams for AR-ISS-024.")
    bad_id = record(statement_en="The cycle created a path for AR-ISS-031.")
    assert ground_record(bad_number, "en", TEXTS, v).missing == ("7",)
    assert not ground_record(bad_id, "en", TEXTS, v).grounded


def test_empty_statement_is_not_grounded() -> None:
    r = ground_record(record(statement_fa=""), "fa", TEXTS, CitedFactValidator())
    assert not r.grounded and r.missing == ("no statement",)


def test_registry_report_counts_per_language() -> None:
    report = ground_registry(registry(record()), TEXTS, CitedFactValidator(), source_numbers)
    assert report.ok
    assert report.grounded("projects", "fa") == 1 and report.grounded("records", "en") == 1
    assert len(report.to_dict()["records"]) == 2   # one per language


def test_corpus_acl_keeps_only_active_version_chunks() -> None:
    records = [rec("AR-TRN-026", 0, "متن فعال", version="1.1"), rec("AR-TRN-026", 1, "old", version="1.0"),
               rec("AR-TRN-026", 2, "active english", lang="en", version="1.1")]
    texts = document_texts(records, {"AR-TRN-026": "1.1"})
    assert texts[("AR-TRN-026", "fa")] == ["متن فعال"]
    assert texts_for(["AR-TRN-026", "AR-HW-012"], "en", texts) == ["active english"]
