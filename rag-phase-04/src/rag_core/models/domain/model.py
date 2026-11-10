"""Model registry entries, prompt templates and prompt assembly."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from string import Template
from typing import Any

from rag_core.knowledge.domain.services import Citation
from rag_core.shared_kernel.errors import InvariantError, NotFoundError
from rag_core.shared_kernel.events import DomainEvent


class TaskType(StrEnum):
    QUESTION_ANSWERING = "question_answering"
    TECHNICAL_SUMMARY = "technical_summary"
    MANAGERIAL_SUMMARY = "managerial_summary"
    ISSUE_DECOMPOSITION = "issue_decomposition"
    LLM_AS_JUDGE = "llm_as_judge"
    KNOWLEDGE_INDEXING = "knowledge_indexing"
    VISUAL_LAYOUT = "visual_layout"


class ModelRole(StrEnum):
    EMBEDDING = "embedding"
    LLM = "llm"
    LVM = "lvm"


@dataclass(frozen=True)
class OutputSchema:
    name: str
    schema: dict[str, Any]

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise InvariantError("schema name is required")


@dataclass
class ModelRegistryEntry:
    model_id: str
    role: ModelRole
    ollama_name: str
    task_types: tuple[TaskType, ...]
    embedding_dim: int | None = None
    status: str = "selected-baseline"

    def __post_init__(self) -> None:
        if not self.model_id or not self.ollama_name:
            raise InvariantError("model id and ollama_name are required")
        if self.role is ModelRole.EMBEDDING and not self.embedding_dim:
            raise InvariantError("embedding models must declare embedding_dim")


@dataclass
class PromptVersion:
    version: str
    template: str
    status: str = "published"

    def __post_init__(self) -> None:
        if not self.version.strip():
            raise InvariantError("prompt version is required")
        if "${" not in self.template and "{" not in self.template:
            # A literal template is allowed, but unusual.
            pass


@dataclass
class PromptTemplate:
    prompt_id: str
    task_type: TaskType
    versions: list[PromptVersion] = field(default_factory=list)
    events: list[DomainEvent] = field(default_factory=list)

    def publish(self, version: PromptVersion) -> None:
        if any(v.version == version.version for v in self.versions):
            raise InvariantError(f"prompt version {version.version} already exists")
        self.versions.append(version)
        self.events.append(
            DomainEvent("PromptVersionPublished", {"prompt_id": self.prompt_id, "version": version.version})
        )

    def get(self, version: str) -> PromptVersion:
        for item in self.versions:
            if item.version == version:
                return item
        raise NotFoundError(f"{self.prompt_id}@{version}")


class PromptAssembler:
    """Deterministic substitution of template variables, including citations."""

    def assemble(
        self,
        template: PromptTemplate,
        version: str,
        variables: dict[str, str],
        citations: list[Citation] | None = None,
    ) -> str:
        prompt = template.get(version)
        payload = dict(variables)
        if citations is not None:
            payload.setdefault("citations", "; ".join(str(c) for c in citations))
        # Safe substitution: missing keys stay as placeholders and we reject them.
        try:
            text = Template(prompt.template).substitute(payload)
        except KeyError as exc:
            raise InvariantError(f"missing prompt variable: {exc}") from exc
        if "citations" in prompt.template and not payload.get("citations"):
            raise InvariantError("prompt requires citations")
        return text


# Phase 2 baseline entries (config/model-registry.yaml 0.3.0), recorded as
# domain defaults so tests can assert the selected models without I/O.
PHASE2_BASELINE = (
    ModelRegistryEntry(
        model_id="emb-bge-m3",
        role=ModelRole.EMBEDDING,
        ollama_name="bge-m3:latest",
        task_types=(TaskType.KNOWLEDGE_INDEXING,),
        embedding_dim=1024,
    ),
    ModelRegistryEntry(
        model_id="llm-qwen3-8b",
        role=ModelRole.LLM,
        ollama_name="qwen3:8b",
        task_types=(TaskType.QUESTION_ANSWERING, TaskType.ISSUE_DECOMPOSITION, TaskType.LLM_AS_JUDGE),
    ),
    ModelRegistryEntry(
        model_id="lvm-qwen2.5vl-3b",
        role=ModelRole.LVM,
        ollama_name="qwen2.5vl:3b",
        task_types=(TaskType.VISUAL_LAYOUT,),
    ),
)
