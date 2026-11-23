"""Phase 12 shipped project registry (data/projects/project-registry.json)."""

import pytest

from rag_core.ingestion.domain.catalog import CATALOG
from rag_core.projects.domain.validation import RegistryValidator
from rag_core.projects.infrastructure.issues_acl import issue_facts
from rag_core.projects.infrastructure.registry_json import JsonProjectRegistry, registry_from_dict
from rag_core.shared_kernel.errors import InvariantError
from tests.fixtures.hierarchy.registry import shipped_registry
from tests.fixtures.issues.seed import seed_issues
from tests.fixtures.projects.samples import PROJECTS_DIR, raw_registry

pytestmark = [pytest.mark.projects]


def shipped():  # noqa: ANN201
    return JsonProjectRegistry(PROJECTS_DIR).load()


def test_shipped_registry_counts() -> None:
    reg = shipped()
    assert reg.cycle == "1403-Q2" and reg.cutoff == "1403-06-31"
    assert [p.project_id for p in reg.projects] == ["PRJ-AZP-118", "PRJ-RHS-PORTAL", "PRJ-DSP-VISITOR"]
    assert reg.counts_by_kind() == {"research": 2, "achievement": 5, "challenge": 4, "unsolved_issue": 4}
    assert [d.dimension_id for d in reg.scorecard] == ["SC-REF", "SC-CAP", "SC-REP", "SC-MGT", "SC-RRQ"]


def test_shipped_project_facts_follow_the_corpus() -> None:
    reg = shipped()
    azp = reg.project("PRJ-AZP-118")
    assert azp is not None and azp.numbers() == {"progress_percent": 62, "remaining_mtoman": 1240,
                                                 "contract_value_mtoman": 2180}
    assert azp.contract_ref == "AR-CNT-1402-118" and azp.primary_issue == "AR-ISS-024"
    rhs, dsp = reg.project("PRJ-RHS-PORTAL"), reg.project("PRJ-DSP-VISITOR")
    assert rhs is not None and (rhs.progress_percent, rhs.remaining_mtoman) == (78, 410)
    assert dsp is not None and (dsp.progress_percent, dsp.remaining_mtoman) == (45, 225)


def test_shipped_registry_is_valid_against_shipped_data() -> None:
    loaded = shipped_registry()
    assert loaded.organization is not None
    nodes = {str(n.identifier) for n in loaded.organization.all_nodes()}
    validator = RegistryValidator(nodes, set(CATALOG), issue_facts(seed_issues()))
    assert validator.validate(shipped()) == []


def test_research_records_keep_their_limits() -> None:
    for r in shipped().records_of("research"):
        assert r.state.value == "open" and r.validated_result is False
        assert r.people and r.risks and r.evidence_needed and r.conditions


def test_ids_have_no_digits_except_corpus_codes() -> None:
    reg = shipped()
    ids = [r.record_id for r in reg.records] + [d.dimension_id for d in reg.scorecard]
    assert not any(ch.isdigit() for i in ids for ch in i)


def test_unknown_keys_are_rejected() -> None:
    data = raw_registry()
    data["records"][0]["score"] = 5
    with pytest.raises(InvariantError, match="unknown keys"):
        registry_from_dict(data)


def test_bad_enum_value_is_rejected() -> None:
    data = raw_registry()
    data["records"][0]["state"] = "proven"
    with pytest.raises(ValueError):
        registry_from_dict(data)


def test_issue_facts_acl_counts_blocked_subissues() -> None:
    facts = issue_facts(seed_issues())
    assert facts["AR-ISS-024"].blocked_subissues == 2 and facts["AR-ISS-024"].risk == 8
    assert facts["AR-ISS-034"].is_open is False and facts["AR-ISS-031"].is_open is True
