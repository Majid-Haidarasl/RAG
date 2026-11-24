"""config/transfer.yaml loading and validation."""

from pathlib import Path

import pytest

from rag_core.shared_kernel.errors import InvariantError
from rag_core.transfer.infrastructure.config import (
    load_transfer_settings,
    transfer_settings_from_dict,
)

pytestmark = [pytest.mark.transfer, pytest.mark.transfer_pkg]

ROOT = Path(__file__).resolve().parents[3]


def test_repo_config_loads() -> None:
    s = load_transfer_settings(ROOT / "config" / "transfer.yaml")
    assert s.config_version == "0.11.0" and s.case == "AR-ISS-024"
    assert (s.cycle.id, s.cycle.period_start, s.cycle.period_end) == (
        "1403-Q2",
        "1403-04-01",
        "1403-06-31",
    )
    assert s.storage.db == "exports/transfer-packages/transfer-packages.sqlite"
    assert (s.model.model, s.model.think, s.model.format) == ("qwen3:8b", False, "json")
    assert s.model.options["num_ctx"] == 8192
    assert (s.live.languages, s.live.max_packages, s.live.llm_judge) == (
        ("fa", "en"),
        6,
        True,
    )
    assert (s.update_check.node, s.update_check.item, s.update_check.status) == (
        "N-HW-REP",
        "AR-ISS-024/HW",
        "resolved",
    )


def test_defaults_from_empty_mapping() -> None:
    s = transfer_settings_from_dict({})
    assert s.cycle.id == "1403-Q2" and s.live.max_packages == 6


@pytest.mark.parametrize(
    "data",
    [
        {"bogus": {}},
        {"cycle": {"idd": "x"}},
        {"live": {"languages": ["de"]}},
        {"live": {"max_packages": -1}},
        {"storage": "db.sqlite"},
    ],
    ids=["section", "key", "language", "max_packages", "not_mapping"],
)
def test_invalid_config(data: dict) -> None:
    with pytest.raises(InvariantError):
        transfer_settings_from_dict(data)


def test_numeric_cycle_id_is_text() -> None:
    assert transfer_settings_from_dict({"cycle": {"id": 1403}}).cycle.id == "1403"
