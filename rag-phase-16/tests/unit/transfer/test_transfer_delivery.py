"""UC-09: deliver latest accepted package to the parent (no Ollama)."""

from dataclasses import replace
from pathlib import Path

import pytest

from rag_core.hierarchy.domain.model import Node, NodeType
from rag_core.shared_kernel.errors import InvariantError, NotFoundError
from rag_core.shared_kernel.identifiers import NodeIdentifier
from rag_core.shared_kernel.layer import LayerIndex
from rag_core.transfer.application.services import DeliverLatestPackage
from rag_core.transfer.domain.delivery import score_from_payload
from rag_core.transfer.domain.review import PackageRecord, content_hash
from rag_core.transfer.infrastructure.csv_export import DELIVERIES_FILE
from rag_core.transfer.infrastructure.sqlite_store import SqliteTransferStore
from tests.fixtures.armanrayan import board, ceo, seed_organization
from tests.fixtures.transfer.samples import built, hw_item, team_hw

pytestmark = [pytest.mark.transfer, pytest.mark.transfer_pkg]


def _hardware_org():
    hw = Node(
        NodeIdentifier("N-HW"),
        "Hardware deputy",
        "معاونت سخت‌افزار",
        NodeType.DEPUTY,
        LayerIndex(2),
        NodeIdentifier("N-CEO"),
    )
    rep = Node(
        NodeIdentifier("N-HW-REP"),
        "Repair team",
        "تیم تعمیر",
        NodeType.TEAM,
        LayerIndex(3),
        NodeIdentifier("N-HW"),
        is_leaf=True,
    )
    return seed_organization(board(), ceo(), hw, rep)


def _rejected_revision(accepted: PackageRecord) -> PackageRecord:
    payload = dict(accepted.payload)
    payload["status"] = "rejected"
    payload["fields"] = {**dict(payload.get("fields") or {}), "note": "rejected-rev"}
    payload["review"] = {
        "grounding": {},
        "verdicts": [
            {
                "judge": "rule",
                "language": "fa",
                "total": 12,
                "out_of": 20,
                "accepted": False,
                "scores": {},
                "reasons": ["low"],
                "notes": [],
            }
        ],
        "accepted": False,
        "reasons": ["low"],
    }
    return PackageRecord(
        cycle_id=accepted.cycle_id,
        source_node=accepted.source_node,
        target_node=accepted.target_node,
        target_layer=accepted.target_layer,
        detail_level=accepted.detail_level,
        status="rejected",
        words_en=accepted.words_en,
        words_fa=accepted.words_fa,
        items=accepted.items,
        content_hash=content_hash(payload),
        payload=payload,
    )


def test_deliver_accepted_latest(tmp_path: Path) -> None:
    org = _hardware_org()
    with SqliteTransferStore(tmp_path / "t.sqlite") as store:
        pkg = built(team_hw(), "N-HW", 2)
        store.save(pkg)
        result = DeliverLatestPackage(store, org, csv_dir=tmp_path / "csv").deliver(
            "N-HW", "N-HW-REP", "1403-Q2"
        )
        assert result.revision == 1
        assert result.source_node == "N-HW-REP"
        assert result.warning is None
        assert result.score == score_from_payload(pkg.to_record().payload)
        assert result.content_hash == store.latest("1403-Q2", "N-HW-REP")["content_hash"]
        logs = store.list_deliveries("1403-Q2")
        assert len(logs) == 1 and logs[0]["requester"] == "N-HW"
        csv_path = tmp_path / "csv" / "1403-Q2" / DELIVERIES_FILE
        assert csv_path.is_file()
        assert "N-HW-REP" in csv_path.read_text(encoding="utf-8")


def test_rejected_latest_falls_back_with_warning(tmp_path: Path) -> None:
    org = _hardware_org()
    with SqliteTransferStore(tmp_path / "t.sqlite") as store:
        accepted = built(team_hw(), "N-HW", 2).to_record()
        store.save(accepted)
        store.save(_rejected_revision(accepted))
        latest = store.latest("1403-Q2", "N-HW-REP")
        assert latest is not None and latest["status"] == "rejected"
        result = DeliverLatestPackage(store, org).deliver("N-HW", "N-HW-REP", "1403-Q2")
        assert result.revision == 1
        assert result.warning == "latest_rejected_fallback"
        assert result.content_hash == accepted.content_hash
        assert store.list_deliveries("1403-Q2")[0]["warning"] == "latest_rejected_fallback"


def test_none_accepted_raises_not_found(tmp_path: Path) -> None:
    org = _hardware_org()
    with SqliteTransferStore(tmp_path / "t.sqlite") as store:
        accepted = built(team_hw(), "N-HW", 2).to_record()
        store.save(_rejected_revision(accepted))
        with pytest.raises(NotFoundError, match="no accepted package"):
            DeliverLatestPackage(store, org).deliver("N-HW", "N-HW-REP", "1403-Q2")


def test_non_parent_rejected(tmp_path: Path) -> None:
    org = _hardware_org()
    with SqliteTransferStore(tmp_path / "t.sqlite") as store:
        store.save(built(team_hw(), "N-HW", 2))
        with pytest.raises(InvariantError, match="not the parent"):
            DeliverLatestPackage(store, org).deliver("N-CEO", "N-HW-REP", "1403-Q2")


def test_delivery_logged_in_store(tmp_path: Path) -> None:
    org = _hardware_org()
    with SqliteTransferStore(tmp_path / "t.sqlite") as store:
        store.save(built(team_hw(), "N-HW", 2))
        DeliverLatestPackage(store, org).deliver("N-HW", "N-HW-REP", "1403-Q2")
        DeliverLatestPackage(store, org).deliver("N-HW", "N-HW-REP", "1403-Q2")
        assert len(store.list_deliveries("1403-Q2")) == 2


def test_score_uses_final_accepted_verdict() -> None:
    payload = {
        "review": {
            "verdicts": [
                {"judge": "rule", "language": "fa", "total": 18, "accepted": True},
                {"judge": "rule", "language": "en", "total": 19, "accepted": True},
                {"judge": "llm", "language": "fa", "total": 10, "accepted": False},
            ]
        }
    }
    assert score_from_payload(payload) == 19


def test_latest_accepted_store_helper(tmp_path: Path) -> None:
    with SqliteTransferStore(tmp_path / "t.sqlite") as store:
        accepted = built(team_hw(), "N-HW", 2).to_record()
        store.save(accepted)
        changed = team_hw(replace(hw_item(), status="resolved"))
        store.save(built(changed, "N-HW", 2))
        row = store.latest_accepted("1403-Q2", "N-HW-REP")
        assert row is not None and row["revision"] == 2 and row["status"] == "accepted"
        store.save(_rejected_revision(accepted))
        row = store.latest_accepted("1403-Q2", "N-HW-REP")
        assert row is not None and row["revision"] == 2
