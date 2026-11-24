"""Phase 13 prompt files: section headings and the two advisory prompts."""

import pytest
import yaml

from rag_core.rfp.domain.generator import DEFAULT_HEADINGS
from rag_core.rfp.infrastructure.prompts_yaml import (
    headings_from,
    load_rfp_prompts,
    prompt_set,
)
from rag_core.shared_kernel.errors import InvariantError
from tests.fixtures.rfp.samples import PROMPT_DIR

pytestmark = [pytest.mark.rfp_gen]


def raw(name: str) -> dict:
    return yaml.safe_load((PROMPT_DIR / name).read_text(encoding="utf-8"))


def test_shipped_prompts_load() -> None:
    p = load_rfp_prompts(PROMPT_DIR)
    assert set(p.headings) == set(DEFAULT_HEADINGS)
    assert p.rfp_summary is not None and p.rfp_summary.prompt_id == "rfp-summary"
    assert p.feedback is not None and p.feedback.prompt_id == "rfp-feedback"
    assert p.headings["need"] == ("Need", "نیاز")


@pytest.mark.parametrize(
    "name, key", [("rfp_summary.yaml", "summary"), ("feedback.yaml", "feedback")]
)
def test_render_fills_placeholders_and_asks_for_json(name: str, key: str) -> None:
    ps = prompt_set(raw(name), name)
    for lang in ("fa", "en"):
        system, user = ps.render(lang, facts="FACT-LINE", items="AR-RFP-1403-07")
        assert (
            "FACT-LINE" in user and "AR-RFP-1403-07" in user and "{facts}" not in user
        )
        assert f'"{key}"' in user and "JSON" in system


def test_render_picks_the_language() -> None:
    ps = prompt_set(raw("feedback.yaml"), "feedback.yaml")
    assert (
        ps.render("fa", facts="x")[0] == ps.system_fa
        and ps.render("en", facts="x")[0] == ps.system_en
    )


def test_prompt_needs_facts_placeholder_and_every_text() -> None:
    data = raw("feedback.yaml")
    with pytest.raises(InvariantError, match="placeholder"):
        prompt_set({**data, "user_fa": "بدون جای خالی"}, "feedback.yaml")
    with pytest.raises(InvariantError, match="missing system_fa"):
        prompt_set({**data, "system_fa": " "}, "feedback.yaml")
    with pytest.raises(InvariantError, match="unknown keys"):
        prompt_set({**data, "temperature": 0.9}, "feedback.yaml")


def test_headings_reject_unknown_or_half_entries() -> None:
    with pytest.raises(InvariantError, match="unknown headings"):
        headings_from({"headings": {"marketing": {"en": "M", "fa": "م"}}})
    with pytest.raises(InvariantError, match="needs en and fa"):
        headings_from({"headings": {"need": {"en": "Need"}}})
    assert headings_from({}) == DEFAULT_HEADINGS
