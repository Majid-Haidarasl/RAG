"""Seed issue registry: loader and validator (shipped data and broken records)."""

import pytest

from rag_core.issues.application.services import corpus_document_ids
from rag_core.issues.domain.status import IssueStatus
from rag_core.issues.domain.validation import IssueRegistryValidator
from rag_core.issues.infrastructure.registry_json import JsonIssueRegistry, issue_from_record
from rag_core.shared_kernel.errors import InvariantError
from tests.fixtures.issues.seed import ISSUES_DIR, org_directory, raw_records, seed_issues

pytestmark = [pytest.mark.issues, pytest.mark.issue_model]


def _codes(records) -> set[str]:
    return IssueRegistryValidator(org_directory(), corpus_document_ids()).validate(records).codes()


def _rec(records, iid):
    return next(r for r in records if r["id"] == iid)


def test_shipped_registry_is_valid() -> None:
    report = IssueRegistryValidator(org_directory(), corpus_document_ids()).validate(raw_records())
    assert report.ok, report.errors
    assert report.warnings == []


def test_shipped_registry_contents() -> None:
    issues = seed_issues()
    assert [str(i.identifier) for i in issues] == [f"AR-ISS-0{n}" for n in (24, 31, 32, 33, 34, 35, 36)]
    assert sum(len(i.subissues) for i in issues) == 4
    statuses = {str(i.identifier): i.status for i in issues}
    assert statuses["AR-ISS-034"] is IssueStatus.CLOSED and statuses["AR-ISS-024"] is IssueStatus.IN_PROGRESS
    dup = next(i for i in issues if str(i.identifier) == "AR-ISS-036")
    assert str(dup.duplicate_of) == "AR-ISS-024"


def test_samples_file_is_loaded() -> None:
    samples = JsonIssueRegistry(ISSUES_DIR).samples()
    assert {s["expected_label"] for s in samples} == {"duplicate", "related", "new"}


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (lambda r: r.append(dict(_rec(r, "AR-ISS-031"))), "I-DUP"),
        (lambda r: _rec(r, "AR-ISS-031").update(id="ISS-31"), "I-ID"),
        (lambda r: _rec(r, "AR-ISS-031").update(owner_node="N-SW-AI"), "I-NODE"),
        (lambda r: _rec(r, "AR-ISS-031").update(owner_node=None), "I-NODE"),
        (lambda r: _rec(r, "AR-ISS-031").update(affected_nodes=["N-XX"]), "I-NODE"),
        (lambda r: _rec(r, "AR-ISS-031").update(related_documents=["AR-SW-099"]), "I-DOC"),
        (lambda r: _rec(r, "AR-ISS-031").update(related_documents=["SW-018"]), "I-DOC"),
        (lambda r: _rec(r, "AR-ISS-031").update(contract_ref="CNT-118"), "I-CONTRACT"),
        (lambda r: _rec(r, "AR-ISS-031").update(category="weather"), "I-ENUM"),
        (lambda r: _rec(r, "AR-ISS-031").update(priority="P0"), "I-ENUM"),
        (lambda r: _rec(r, "AR-ISS-031").update(status="done"), "I-STATUS"),
        (lambda r: _rec(r, "AR-ISS-031").update(due_on="2024-01-01"), "I-DATE"),
        (lambda r: _rec(r, "AR-ISS-031").update(opened_on="21/09/2024"), "I-DATE"),
        (lambda r: _rec(r, "AR-ISS-034").update(resolution=None), "I-RESOLUTION"),
        (lambda r: _rec(r, "AR-ISS-031").update(resolution="fixed"), "I-RESOLUTION"),
        (lambda r: _rec(r, "AR-ISS-036").update(duplicate_of=None), "I-DUPLICATE-OF"),
        (lambda r: _rec(r, "AR-ISS-036").update(duplicate_of="AR-ISS-099"), "I-DUPLICATE-OF"),
        (lambda r: _rec(r, "AR-ISS-032").update(related_issues=["AR-ISS-098"]), "I-RELATED"),
        (lambda r: _rec(r, "AR-ISS-024").update(duplicate_of="AR-ISS-036"), "I-CYCLE"),
        (lambda r: _rec(r, "AR-ISS-024").update(progress_percent=120), "I-PROGRESS"),
        (lambda r: _rec(r, "AR-ISS-024")["sub_issues"][0].update(id="AR-ISS-031/HW"), "S-PARENT"),
        (lambda r: _rec(r, "AR-ISS-024")["sub_issues"][1].update(position=1), "S-POSITION"),
        (lambda r: _rec(r, "AR-ISS-024")["sub_issues"][1].update(owner_node="N-SW-AI"), "I-NODE"),
        (lambda r: _rec(r, "AR-ISS-024")["sub_issues"][1].update(depends_on=["NET"]), "S-DEPENDS"),
        (lambda r: _rec(r, "AR-ISS-024")["sub_issues"][0].update(depends_on=["WIN"]), "S-CYCLE"),
        (lambda r: _rec(r, "AR-ISS-024")["sub_issues"][1].update(status="resolved"), "S-DEPENDS"),
        (lambda r: _rec(r, "AR-ISS-024").update(status="resolved"), "S-OPEN-UNDER-DONE"),
        (lambda r: _rec(r, "AR-ISS-024")["sub_issues"][2].update(status="??"), "S-STATUS"),
    ],
)
def test_broken_records_are_reported(mutate, code: str) -> None:
    records = raw_records()
    mutate(records)
    assert code in _codes(records)


def test_validator_collects_all_errors() -> None:
    records = raw_records()
    _rec(records, "AR-ISS-031")["owner_node"] = "N-SW-AI"
    _rec(records, "AR-ISS-033")["category"] = "weather"
    assert {"I-NODE", "I-ENUM"} <= _codes(records)


def test_blocked_subissue_without_reason_is_a_warning() -> None:
    records = raw_records()
    _rec(records, "AR-ISS-024")["sub_issues"][1].pop("blocked_reason")
    report = IssueRegistryValidator(org_directory(), corpus_document_ids()).validate(records)
    assert report.ok and {w.code for w in report.warnings} == {"S-BLOCKED"}


def test_legacy_status_values_are_accepted() -> None:
    records = raw_records()
    _rec(records, "AR-ISS-031")["status"] = "analysing"
    assert _codes(records) == set()
    assert issue_from_record(_rec(records, "AR-ISS-031")).status is IssueStatus.TRIAGED


def test_loader_rejects_dependency_cycles() -> None:
    rec = _rec(raw_records(), "AR-ISS-024")
    rec["sub_issues"][0]["depends_on"] = ["WIN"]
    with pytest.raises(InvariantError, match="cycle"):
        issue_from_record(rec)


def test_round_trip_keeps_metadata() -> None:
    rec = _rec(raw_records(), "AR-ISS-024")
    issue = issue_from_record(rec)
    assert issue.title_fa == rec["title_fa"]
    assert [str(n) for n in issue.affected_nodes] == rec["affected_nodes"]
    assert issue.subissue("HW").executors == ("Saeed Akbari", "Farzaneh Javadi", "Ehsan Davari")
    assert issue.opened_on.isoformat() == "2024-08-06" and issue.due_on.isoformat() == "2024-10-11"
