"""IKE ACLs: Phase 7 issues → views, executor plans → referrals, Phase 8 retriever → search port."""

import pytest

from rag_core.executors.application.services import ExecutorMatchingService
from rag_core.executors.infrastructure.issues_acl import referral_requests
from rag_core.executors.infrastructure.memory import InMemoryExecutorRepository
from rag_core.ike.infrastructure.executors_acl import executor_names, referrals_by_item
from rag_core.ike.infrastructure.issues_acl import issue_view, recorded_progress
from rag_core.ike.infrastructure.retrieval_acl import RetrieverKnowledgeSearch
from rag_core.rag.application.indexing import build_retriever
from tests.fixtures.executors.registry import shipped_executors
from tests.fixtures.issues.seed import azarpakhsh
from tests.fixtures.rag.fakes import sample_records, sample_scope

pytestmark = [pytest.mark.ike, pytest.mark.ike_model]


def test_issue_view_of_azarpakhsh() -> None:
    view = issue_view(azarpakhsh())
    assert view.issue_id == "AR-ISS-024" and view.owner_node == "N-LIB"
    assert view.progress_percent == 62 == recorded_progress(azarpakhsh())
    assert view.contract_ref == "AR-CNT-1402-118"
    assert [s.code for s in view.sub_items] == ["HW", "WIN", "WEB", "LEG"]
    assert (
        view.sub_item("WIN").depends_on == ("HW",)
        and view.sub_item("WIN").status == "blocked"
    )
    assert view.sub_item("LEG").reserved_decision
    assert view.sub_item("HW").supporting_nodes == ("N-HW-ADV", "N-HW-ASM")


def test_referral_views_mark_one_lead_per_item() -> None:
    executors = shipped_executors()
    plans = ExecutorMatchingService(InMemoryExecutorRepository(executors)).plans(
        referral_requests(azarpakhsh())
    )
    refs = referrals_by_item(plans, executors)
    assert set(refs) == {
        "AR-ISS-024/HW",
        "AR-ISS-024/WIN",
        "AR-ISS-024/WEB",
        "AR-ISS-024/LEG",
    }
    for item, views in refs.items():
        assert sum(1 for v in views if v.role == "lead") == 1, item
    saeed = next(v for v in refs["AR-ISS-024/HW"] if v.executor_id == "EX-SAEED-AKBARI")
    assert saeed.knowledge_documents == ("AR-HW-012", "AR-HW-015") and saeed.name_fa
    names = executor_names(executors)
    assert names["EX-ROOZBEH-MOHSENI"][0] == "Roozbeh Mohseni"


def test_retriever_search_port_is_node_scoped_and_text_free() -> None:
    scope = sample_scope()
    search = RetrieverKnowledgeSearch(build_retriever(sample_records(), scope=scope))
    result = search.search("Azarpakhsh RAID controller", "N-REP", 5)
    assert result.mode == "lexical" and result.node == "N-REP"
    assert result.visible_documents == frozenset({"AR-HW-012", "AR-ISS-024"})
    assert "AR-ISS-024" in result.documents()
    assert all(h.document_id in result.visible_documents for h in result.hits)
    assert set(result.outside_owners) <= {"N-HR", "N-SUP"}
    assert not hasattr(result.hits[0], "text")
