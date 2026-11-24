"""IssueService: intake with comparison, registration and decomposition."""

import pytest

from rag_core.issues.application.services import IssueService
from rag_core.issues.domain.comparison import MatchLabel
from rag_core.issues.infrastructure.memory import InMemoryIssueRepository
from rag_core.issues.infrastructure.registry_json import issue_from_sample
from rag_core.shared_kernel.errors import InvariantError, NotFoundError
from rag_core.shared_kernel.identifiers import IssueId
from tests.fixtures.issues.seed import org_directory, samples, seed_issues

pytestmark = [pytest.mark.issues, pytest.mark.issue_model]


def _service() -> IssueService:
    return IssueService(InMemoryIssueRepository(seed_issues()), org_directory())


def test_duplicate_is_not_registered() -> None:
    svc = _service()
    out = svc.intake(issue_from_sample(samples()[0]))
    assert out.comparison.label is MatchLabel.DUPLICATE and not out.registered
    assert not svc.repo.exists(IssueId("AR-ISS-041"))
    assert svc.events[-1].name == "DuplicateIssueDetected"
    assert svc.events[-1].payload["duplicate_of"] == "AR-ISS-024"


def test_related_issue_is_registered_and_linked() -> None:
    svc = _service()
    out = svc.intake(issue_from_sample(samples()[1]))
    assert out.registered and out.comparison.label is MatchLabel.RELATED
    assert IssueId("AR-ISS-024") in svc.repo.get(IssueId("AR-ISS-042")).related_issues
    assert out.position.owner == "N-SW-WIN"


def test_new_issue_is_registered_with_its_position() -> None:
    svc = _service()
    out = svc.intake(issue_from_sample(samples()[3]))
    assert out.registered and out.comparison.label is MatchLabel.NEW
    assert out.position.is_local and out.position.escalation_target == "N-SW-VIS"


def test_duplicates_can_be_forced_in() -> None:
    svc = _service()
    assert svc.intake(
        issue_from_sample(samples()[0]), register_duplicates=True
    ).registered


def test_existing_id_is_rejected() -> None:
    svc = _service()
    sample = dict(samples()[3], id="AR-ISS-031")
    with pytest.raises(InvariantError, match="already exists"):
        svc.intake(issue_from_sample(sample))


def test_unknown_node_is_rejected_at_intake() -> None:
    sample = dict(samples()[3], owner_node="N-SW-AI")
    with pytest.raises(NotFoundError):
        _service().intake(issue_from_sample(sample))


def test_service_decomposes_with_registry_owners() -> None:
    svc = _service()
    issue = svc.repo.get(IssueId("AR-ISS-024"))
    issue.subissues = []
    added = svc.decompose(issue)
    assert [str(s.owner_node) for s in added] == [
        "N-HW-REP",
        "N-SW-WIN",
        "N-SW-WEB",
        "N-ADM-LEG",
    ]
    assert svc.position(issue).escalation_target == "N-CEO"
