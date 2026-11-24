"""Phase 13 blueprint file reader: unknown keys and versions are rejected."""

from decimal import Decimal

import pytest

from rag_core.rfp.infrastructure.blueprint_json import (
    blueprints_from_dict,
    load_blueprints,
)
from rag_core.shared_kernel.errors import InvariantError
from tests.fixtures.rfp.samples import BLUEPRINT_DIR, raw_blueprints

pytestmark = [pytest.mark.rfp_gen]


def test_load_from_folder() -> None:
    bps = load_blueprints(BLUEPRINT_DIR)
    assert [b.blueprint_id for b in bps] == ["BP-WEB-REPORTING"]


def test_weights_are_read_as_exact_decimals() -> None:
    bp = blueprints_from_dict(raw_blueprints())[0]
    assert [c.weight for c in bp.criteria] == [Decimal("0.6"), Decimal("0.4")]


def test_link_without_executor_reads_as_empty() -> None:
    bp = blueprints_from_dict(raw_blueprints())[0]
    library = next(x for x in bp.links if x.link_id == "LNK-LIBRARY")
    assert library.executor == "" and library.node == "N-LIB"
    assert library.requirements == ("REQ-RESPONSE", "REQ-EVALUATION")


def test_unknown_top_key() -> None:
    raw = raw_blueprints()
    raw["extra"] = 1
    with pytest.raises(InvariantError, match="unknown keys"):
        blueprints_from_dict(raw)


def test_unknown_nested_key() -> None:
    for where in ("blueprint", "requirement", "criterion", "link"):
        raw = raw_blueprints()
        bp = raw["blueprints"][0]
        target = {
            "blueprint": bp,
            "requirement": bp["requirements"][0],
            "criterion": bp["criteria"][0],
            "link": bp["links"][0],
        }[where]
        target["score_hint"] = "x"
        with pytest.raises(InvariantError, match="unknown keys score_hint"):
            blueprints_from_dict(raw)


def test_unsupported_schema_version() -> None:
    raw = raw_blueprints()
    raw["schema_version"] = 2
    with pytest.raises(InvariantError, match="schema_version"):
        blueprints_from_dict(raw)
