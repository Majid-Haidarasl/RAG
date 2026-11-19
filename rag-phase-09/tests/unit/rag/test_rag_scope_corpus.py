"""Phase 6 scope through the ACL, and records from the real corpus."""

from pathlib import Path

import pytest

from rag_core.rag.application.corpus import build_corpus_records, load_scope

pytestmark = [pytest.mark.rag, pytest.mark.retrieval]

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def scope():  # noqa: ANN201
    return load_scope(ROOT / "data" / "registry")


def test_web_team_cannot_see_hr_policy(scope) -> None:  # noqa: ANN001
    visible = scope.visible_documents("N-SW-WEB")
    assert "AR-HR-005" not in visible and "AR-SW-017" in visible and "AR-ISS-024" in visible


def test_ceo_sees_all_documents(scope) -> None:  # noqa: ANN001
    assert len(scope.visible_documents("N-CEO")) == 26


def test_escalation_uses_lowest_common_ancestor(scope) -> None:  # noqa: ANN001
    route = scope.route("N-SW-WEB", ["N-ADM-HR"])
    assert route.action == "escalate" and route.target == "N-CEO"
    sibling = scope.route("N-SW-WEB", ["N-SW-WIN"])
    assert sibling.target == "N-SW"
    assert scope.route("N-SW-WEB", ["N-SW-WEB"]).action == "answer"


def test_owner_layer_and_existence(scope) -> None:  # noqa: ANN001
    assert scope.owner_of("AR-HR-005") == "N-ADM-HR"
    assert scope.layer_of("N-LIB") == 4 and scope.layer_of("N-NOPE") is None
    assert scope.exists("N-SW-WEB") and not scope.exists("N-NOPE") and not scope.exists("bad id")


def test_visible_documents_cached(scope) -> None:  # noqa: ANN001
    assert scope.visible_documents("N-HW-REP") is scope.visible_documents("N-HW-REP")


@pytest.mark.slow
def test_real_corpus_records() -> None:
    corpus = build_corpus_records(ROOT)
    assert corpus.files == 52 and not corpus.failures
    assert len(corpus.records) > 1000 and all(r.is_active for r in corpus.records)
    assert {r.language for r in corpus.records} == {"fa", "en"}
    assert len({r.document_id for r in corpus.records}) == 26
    assert all(r.owner_node and r.layer is not None for r in corpus.records)
    assert sum(1 for r in corpus.records if r.duplicate_of) > 0, "template clauses repeat across documents"
    assert len({r.key for r in corpus.records}) == len(corpus.records)
