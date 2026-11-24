"""Phase 12 config/projects.yaml loader."""

import pytest

from rag_core.projects.infrastructure.config import (
    load_project_settings,
    project_settings_from_dict,
)
from rag_core.shared_kernel.errors import InvariantError
from tests.fixtures.projects.samples import CONFIG

pytestmark = [pytest.mark.projects, pytest.mark.prioritization]


def test_shipped_config() -> None:
    s = load_project_settings(CONFIG)
    assert s.config_version == "0.12.0" and s.case == "AR-ISS-024"
    assert (s.cycle.id, s.cycle.cutoff) == ("1403-Q2", "1403-06-31")
    assert s.storage.csv_dir == "exports/project-tracking"
    assert (
        s.model.model == "qwen3:8b"
        and s.model.think is False
        and s.model.format == "json"
    )
    assert s.live.languages == ("fa", "en") and s.live.llm_judge is True


def test_shipped_priority_settings() -> None:
    p = load_project_settings(CONFIG).prioritization
    assert abs(sum(p.weights.values.values()) - 1.0) < 1e-9
    assert p.weights["risk"] == pytest.approx(0.15) and p.weights[
        "spread"
    ] == pytest.approx(0.05)
    assert (p.caps.dependents, p.caps.exposure_mtoman, p.caps.gaps, p.caps.spread) == (
        4,
        1000,
        5,
        6,
    )
    assert (p.key_count, p.key_min_score, p.sensitivity_ratios, p.risk_threshold) == (
        3,
        25.0,
        (0.8, 1.2),
        7,
    )


def test_shipped_gap_rules() -> None:
    rules = load_project_settings(CONFIG).gap_rules
    assert list(rules) == ["RG", "KL", "EX", "DEP", "CH", "SC", "ST", "EV"]
    assert all(r.enabled for r in rules.values())
    assert rules["DEP"].severity == "high" and rules["ST"].severity == "low"


def test_defaults_when_empty() -> None:
    s = project_settings_from_dict({})
    assert (
        s.cycle.id == "1403-Q2"
        and s.prioritization.key_count == 3
        and len(s.gap_rules) == 8
    )


@pytest.mark.parametrize(
    "data",
    [
        {"extra": 1},
        {"cycle": {"week": 3}},
        {"gap_rules": {"ZZ": {"enabled": True}}},
        {"gap_rules": {"RG": {"severity": "extreme"}}},
        {"prioritization": {"weights": {"risk": 0.5}}},
        {"prioritization": {"caps": {"height": 3}}},
        {"live": {"languages": ["de"]}},
    ],
)
def test_invalid_config_is_rejected(data: dict) -> None:
    with pytest.raises(InvariantError):
        project_settings_from_dict(data)
