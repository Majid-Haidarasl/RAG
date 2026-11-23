"""Phase 13 config/rfp.yaml: shipped values and rejected keys."""

import pytest

from rag_core.rfp.infrastructure.config import load_rfp_settings, rfp_settings_from_dict
from rag_core.shared_kernel.errors import InvariantError
from tests.fixtures.rfp.samples import CONFIG

pytestmark = [pytest.mark.rfp_gen]


def test_shipped_config() -> None:
    s = load_rfp_settings(CONFIG)
    assert s.config_version == "0.13.0" and (s.cycle.id, s.cycle.cutoff) == ("1403-Q2", "1403-06-31")
    assert s.candidates.categories == ("procurement",) and s.candidates.targets == {"AR-ISS-024": "AR-ISS-024/WEB"}
    assert s.judging.max_rfp_chars == 6000
    assert (s.model.model, s.model.think, s.model.format) == ("qwen3:8b", False, "json")
    assert s.live.languages == ("fa", "en") and s.live.tasks == ("rfp_summary", "feedback") and s.live.llm_judge
    assert s.storage.blueprint_dir == "data/rfp" and s.storage.csv_dir == "exports/rfp"


def test_defaults_from_an_empty_file() -> None:
    s = rfp_settings_from_dict({})
    assert s.config_version == "0.13.0" and s.candidates.targets == {"AR-ISS-024": "AR-ISS-024/WEB"}


REJECTED = [
    ({"extras": {}}, "unknown rfp config sections"),
    ({"candidates": {"limit": 3}}, "unknown keys"),
    ({"candidates": {"targets": {"AR-ISS-024": "AR-ISS-031/WEB"}}}, "not a sub-issue"),
    ({"live": {"languages": ["de"]}}, "languages"),
    ({"live": {"tasks": ["slides"]}}, "tasks"),
    ({"judging": {"max_rfp_chars": 200}}, "max_rfp_chars"),
    ({"model": "qwen3:8b"}, "mapping"),
]


def test_rejected() -> None:
    for data, message in REJECTED:
        with pytest.raises(InvariantError, match=message):
            rfp_settings_from_dict(data)
