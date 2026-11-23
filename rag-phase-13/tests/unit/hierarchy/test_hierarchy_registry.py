"""Loader + validator on the shipped registry and on deliberately broken rows."""

import pytest

from rag_core.hierarchy.application.workflows import catalog_index
from rag_core.hierarchy.domain.model import NodeType
from rag_core.hierarchy.domain.validation import RegistryValidator
from rag_core.hierarchy.infrastructure.registry_csv import CsvRegistryLoader
from rag_core.shared_kernel.confidentiality import Confidentiality
from rag_core.shared_kernel.identifiers import NodeIdentifier
from tests.fixtures.hierarchy.registry import REGISTRY_DIR, layer_row, node_row, shipped_registry, shipped_rows

pytestmark = [pytest.mark.hierarchy, pytest.mark.registry]


def _codes(rows) -> set[str]:
    report = RegistryValidator(catalog_index()).validate(rows.layers, rows.nodes, rows.doc_map)
    return {i.code for i in report.errors}


def test_shipped_registry_is_valid_and_builds_the_aggregate() -> None:
    loaded = shipped_registry()
    assert loaded.report.errors == []
    org = loaded.organization
    assert org is not None
    assert [len(org.nodes_on_layer(i)) for i in range(5)] == [1, 1, 3, 15, 1]
    assert len(org.leaves()) == 16
    assert org.max_depth() == 3
    assert org.root().identifier == NodeIdentifier("N-BRD")


def test_q3_library_reports_to_ceo_in_shipped_data() -> None:
    org = shipped_registry().organization
    lib = org.get(NodeIdentifier("N-LIB"))
    assert lib.node_type == NodeType.KNOWLEDGE_REPOSITORY
    assert lib.parent_id == NodeIdentifier("N-CEO")
    assert org.depth(lib.identifier) == 2 and lib.layer.value == 4


def test_every_layer_has_a_complete_transfer_requirement() -> None:
    org = shipped_registry().organization
    for layer in org.layers.values():
        assert layer.transfer is not None, layer.code
        assert layer.transfer.is_complete, (layer.code, layer.transfer.gaps())
    assert org.layers[0].transfer.direction.value == "down"
    assert org.layers[3].transfer.target.value == 2


def test_document_map_has_one_owner_per_corpus_document_matching_the_catalog() -> None:
    ownership = shipped_registry().ownership
    catalog = catalog_index()
    assert len(ownership.documents()) == len(catalog) == 26
    for doc_id, (owner, _) in catalog.items():
        assert str(ownership.owner_of(next(d for d in ownership.documents() if d.value == doc_id))) == owner


def test_per_item_written_with_a_space_is_accepted() -> None:
    rows = shipped_rows()
    node_row(rows, "N-LIB")["confidentiality"] = "per item"
    assert _codes(rows) == set()
    org = CsvRegistryLoader(REGISTRY_DIR).build_organization(rows)
    assert org.get(NodeIdentifier("N-LIB")).confidentiality is Confidentiality.PER_ITEM


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (lambda r: r.nodes.append(dict(node_row(r, "N-SW-WEB"))), "N-DUP"),
        (lambda r: node_row(r, "N-SW-WEB").update(parent_node_id="N-XYZ"), "N-PARENT"),
        (lambda r: node_row(r, "N-CEO").update(parent_node_id="N-SW"), "N-CYCLE"),
        (lambda r: node_row(r, "N-SW-WEB").update(parent_node_id="N-CEO"), "N-ADJ"),
        (lambda r: node_row(r, "N-LIB").update(parent_node_id="N-SW"), "N-ADJ"),
        (lambda r: node_row(r, "N-SW").update(is_leaf="true"), "N-LEAF"),
        (lambda r: node_row(r, "N-SW-WEB").update(node_name_en="React"), "N-TECHNAME"),
        (lambda r: node_row(r, "N-SW-WEB").update(node_type="deputy"), "N-TYPE-LAYER"),
        (lambda r: node_row(r, "N-SW-WEB").update(transfer_detail_level_to_parent="executive"), "N-DETAIL"),
        (lambda r: node_row(r, "N-SW-WEB").update(escalation_node_id="N-HW"), "N-ESCALATION"),
        (lambda r: node_row(r, "N-SW-WEB").update(source_docs="AR-SW-099"), "N-SOURCE"),
        (lambda r: node_row(r, "N-SW").update(status="retired"), "N-RETIRED-PARENT"),
        (lambda r: node_row(r, "N-BRD").update(parent_node_id="N-CEO"), "N-ROOT"),
        (lambda r: layer_row(r, 3).update(min_artefacts="only one"), "T-ARTEFACTS"),
        (lambda r: layer_row(r, 2).update(approvals_required=""), "T-APPROVALS"),
        (lambda r: layer_row(r, 3).update(transfer_target="L1"), "T-TARGET"),
        (lambda r: layer_row(r, 1).update(transfer_direction=""), "T-MISSING"),
        (lambda r: layer_row(r, 4).update(layer_code="L7"), "L-CODE"),
        (lambda r: layer_row(r, 2).update(min_judge_score="25"), "L-SCORE"),
        (lambda r: r.layers.remove(layer_row(r, 2)), "L-GAP"),
        (lambda r: r.doc_map.append({"document_id": "AR-SW-017", "node_id": "N-SW-MOB", "role": "owner", "source": "x"}), "M-OWNERS"),
        (lambda r: next(m for m in r.doc_map if m["role"] == "owner").update(node_id="N-HW"), "M-OWNER"),
        (lambda r: r.doc_map.append({"document_id": "AR-SW-017", "node_id": "N-NOPE", "role": "co_owner", "source": "x"}), "M-NODE"),
        (lambda r: r.doc_map.append({"document_id": "AR-SW-017", "node_id": "N-HW", "role": "reader", "source": "x"}), "M-ROLE"),
    ],
)
def test_broken_rows_are_reported(mutate, code: str) -> None:
    rows = shipped_rows()
    mutate(rows)
    assert code in _codes(rows)


def test_validator_collects_all_errors_instead_of_stopping_at_the_first() -> None:
    rows = shipped_rows()
    node_row(rows, "N-SW-WEB")["parent_node_id"] = "N-CEO"
    node_row(rows, "N-HW-REP")["node_name_en"] = "Flutter"
    layer_row(rows, 2)["required_feedback"] = ""
    assert {"N-ADJ", "N-TECHNAME", "T-FEEDBACK"} <= _codes(rows)


def test_missing_cost_center_is_only_a_warning() -> None:
    report = shipped_registry().report
    assert report.ok
    assert {w.code for w in report.warnings} <= {"N-COSTCENTER", "N-LEAF-FLAG", "M-UNMAPPED"}


def test_unmapped_corpus_document_is_reported() -> None:
    rows = shipped_rows()
    rows.doc_map[:] = [m for m in rows.doc_map if m["document_id"] != "AR-TRN-026"]
    report = RegistryValidator(catalog_index()).validate(rows.layers, rows.nodes, rows.doc_map)
    assert any(w.code == "M-UNMAPPED" and w.subject == "AR-TRN-026" for w in report.warnings)
