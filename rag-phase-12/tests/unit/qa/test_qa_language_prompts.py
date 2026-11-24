"""Question language and the YAML prompt set (Phase 3 assembler reused)."""

from pathlib import Path

import pytest
import yaml

from rag_core.qa.domain.language import question_language
from rag_core.qa.domain.prompts import QaPromptSet
from rag_core.qa.infrastructure.prompt_yaml import load_qa_prompts
from rag_core.shared_kernel.errors import InvariantError

pytestmark = [pytest.mark.qa]

ROOT = Path(__file__).resolve().parents[3]
PROMPTS = ROOT / "config" / "prompts" / "qa"


@pytest.mark.parametrize(
    "text,lang",
    [
        ("سقف مرخصی ساعتی چقدر است؟", "fa"),
        ("What is the hourly leave limit?", "en"),
        ("AR-HR-005 مرخصی؟", "fa"),
        ("P1?", "en"),
        ("مرخصی RAM و RAID در AR-ISS-024 چیست؟", "fa"),
    ],
)
def test_question_language(text: str, lang: str) -> None:
    assert question_language(text) == lang


def test_shipped_prompts_load() -> None:
    p = load_qa_prompts(PROMPTS)
    assert (
        p.prompt_id == "qa.answer"
        and p.version == "2.0.0"
        and p.refusal_token == "INSUFFICIENT_CONTEXT"
    )
    for kind in ("not_found", "insufficient", "out_of_scope"):
        assert p.messages[kind]["fa"] and p.messages[kind]["en"]


def test_every_yaml_has_id_and_version() -> None:
    for path in PROMPTS.glob("*.yaml"):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert data["id"] and data["version"]


def test_render_forces_labels_language_and_refusal() -> None:
    p = load_qa_prompts(PROMPTS)
    system, user = p.render(
        question="سقف مرخصی ساعتی؟",
        context="[AR-HR-005 §5] ...\nمتن",
        language="fa",
        node="N-ADM-HR",
    )
    assert "[AR-HR-005 §12]" in system, "the label format is shown to the model"
    assert (
        "Persian" in system
        and "INSUFFICIENT_CONTEXT" in system
        and "N-ADM-HR" in system
    )
    assert "ONLY the CONTEXT" in system
    assert (
        user.startswith("CONTEXT:\n[AR-HR-005 §5]")
        and "QUESTION: سقف مرخصی ساعتی؟" in user
    )


def test_render_english_answer_language() -> None:
    system, _ = load_qa_prompts(PROMPTS).render(
        question="q", context="c", language="en", node="N-CEO"
    )
    assert "Write the answer in English" in system


def test_context_with_dollar_signs_is_safe() -> None:
    _, user = load_qa_prompts(PROMPTS).render(
        question="q", context="cost $100 ${x}", language="en", node="N"
    )
    assert "cost $100 ${x}" in user


def test_messages_fill_values() -> None:
    p = load_qa_prompts(PROMPTS)
    text = p.message("out_of_scope", "fa", node="N-SW-WEB", target="N-CEO", reason="r")
    assert "N-SW-WEB" in text and "N-CEO" in text
    assert "N-CEO" in p.message("not_found", "en", node="N-CEO")


@pytest.mark.parametrize(
    "text,refusal",
    [
        ("INSUFFICIENT_CONTEXT the policy is missing", True),
        ("insufficient context.", True),
        ("", True),
        ("مرخصی ۲۶ روز است [AR-HR-005 §3]", False),
    ],
)
def test_refusal_detection(text: str, refusal: bool) -> None:
    assert load_qa_prompts(PROMPTS).is_refusal(text) is refusal


def _valid_kwargs() -> dict:
    msgs = {
        k: {"fa": "x", "en": "y"} for k in ("not_found", "insufficient", "out_of_scope")
    }
    return dict(
        prompt_id="p",
        version="1",
        system="${answer_language} ${refusal_token}",
        user="${context} ${question}",
        messages=msgs,
    )


def test_prompt_set_validation() -> None:
    QaPromptSet(**_valid_kwargs())
    bad = _valid_kwargs() | {"system": "no vars"}
    with pytest.raises(InvariantError):
        QaPromptSet(**bad)
    bad = _valid_kwargs() | {"user": "${question}"}
    with pytest.raises(InvariantError):
        QaPromptSet(**bad)
    bad = _valid_kwargs() | {"messages": {}}
    with pytest.raises(InvariantError):
        QaPromptSet(**bad)


def test_loader_errors(tmp_path: Path) -> None:
    (tmp_path / "a.yaml").write_text("version: 1\n", encoding="utf-8")
    with pytest.raises(InvariantError, match="missing id"):
        load_qa_prompts(tmp_path)
    (tmp_path / "a.yaml").write_text("id: other\nversion: 1\n", encoding="utf-8")
    with pytest.raises(InvariantError, match="not found"):
        load_qa_prompts(tmp_path)
