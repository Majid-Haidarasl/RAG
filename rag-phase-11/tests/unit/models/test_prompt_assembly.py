import pytest

from rag_core.knowledge.domain.services import Citation
from rag_core.models.domain.model import (
    PHASE2_BASELINE,
    ModelRole,
    PromptAssembler,
    PromptTemplate,
    PromptVersion,
    TaskType,
)
from rag_core.models.infrastructure.memory import InMemoryModelRegistry, InMemoryPromptRegistry
from rag_core.shared_kernel.errors import InvariantError
from rag_core.shared_kernel.identifiers import DocumentId
from rag_core.shared_kernel.language import LanguageCode
from tests.fakes.models import FakeEmbeddingModel

pytestmark = pytest.mark.models


def test_template_plus_context_includes_citations() -> None:
    template = PromptTemplate("qa.grounded", TaskType.QUESTION_ANSWERING)
    template.publish(
        PromptVersion("1.0.0", "Question: $question\nContext: $context\nCitations: $citations")
    )
    text = PromptAssembler().assemble(
        template,
        "1.0.0",
        {"question": "زمان پاسخ P1؟", "context": "۳۰ دقیقه"},
        citations=[Citation(DocumentId("AR-SW-022"), "1.0", LanguageCode.FA, section="P1")],
    )
    assert "AR-SW-022@1.0#P1" in text
    assert "۳۰ دقیقه" in text
    assert any(e.name == "PromptVersionPublished" for e in template.events)


def test_missing_variable_is_rejected() -> None:
    template = PromptTemplate("qa.grounded", TaskType.QUESTION_ANSWERING)
    template.publish(PromptVersion("1.0.0", "Q: $question"))
    with pytest.raises(InvariantError, match="missing prompt variable"):
        PromptAssembler().assemble(template, "1.0.0", {})


def test_phase2_baseline_models_are_registered() -> None:
    registry = InMemoryModelRegistry()
    names = {entry.ollama_name for entry in registry.list_baseline()}
    assert names == {"bge-m3:latest", "qwen3:8b", "qwen2.5vl:3b"}
    embed = registry.get("emb-bge-m3")
    assert embed.role is ModelRole.EMBEDDING
    assert embed.embedding_dim == 1024
    assert len(PHASE2_BASELINE) == 3


def test_fake_embedding_is_deterministic_and_fixed_dim() -> None:
    model = FakeEmbeddingModel(8)
    a = model.embed(["مرخصی استحقاقی سالانه"])
    b = model.embed(["مرخصی استحقاقی سالانه"])
    assert a == b
    assert len(a[0]) == 8


def test_prompt_registry_round_trip() -> None:
    registry = InMemoryPromptRegistry()
    template = PromptTemplate("judge.default", TaskType.LLM_AS_JUDGE)
    template.publish(PromptVersion("1.0.0", "Score the text.\n$subject"))
    registry.save(template)
    assert registry.get("judge.default").get("1.0.0").version == "1.0.0"
