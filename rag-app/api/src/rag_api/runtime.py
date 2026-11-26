from __future__ import annotations

import logging
from dataclasses import dataclass

from rag_core.qa.application.service import NodeScopedQaService, QaConfig
from rag_core.qa.domain.ports import ChatModelPort
from rag_core.qa.domain.prompts import QaPromptSet
from rag_core.qa.infrastructure.prompt_yaml import load_qa_prompts
from rag_core.rag.application.corpus import CorpusIndexInput, build_corpus_records
from rag_core.rag.application.indexing import IndexBuilder, IndexBuildReport, build_retriever
from rag_core.rag.domain.context import ContextAssembler
from rag_core.rag.domain.retriever import HybridRetriever
from rag_core.rag.infrastructure.config import RagSettings, load_settings
from rag_core.rag.infrastructure.ollama import (
    OllamaChatModel,
    OllamaClient,
    OllamaEmbedder,
    OllamaError,
)
from rag_core.rag.infrastructure.scope_acl import HierarchyScope
from rag_core.rag.infrastructure.sqlite_store import SqliteIndexStore

from rag_api.fake_models import FakeChatModel
from rag_api.settings import ApiSettings

logger = logging.getLogger(__name__)

_VISION_MODEL = "qwen2.5vl:3b"


@dataclass(frozen=True)
class ModelStatus:
    reachable: bool
    version: str
    base_url: str
    installed: list[str]
    embedding_ok: bool
    generation_ok: bool
    vision_installed: bool
    reason: str

    @property
    def ready(self) -> bool:
        return self.reachable and self.embedding_ok and self.generation_ok


@dataclass
class RagRuntime:
    rag: RagSettings
    scope: HierarchyScope
    retriever: HybridRetriever
    service: NodeScopedQaService | None
    models: ModelStatus
    index: IndexBuildReport | None
    mode: str

    @property
    def can_answer(self) -> bool:
        return self.service is not None


def probe_models(rag: RagSettings) -> tuple[OllamaClient | None, ModelStatus]:
    base_url = rag.ollama.base_url
    try:
        client = OllamaClient(
            base_url,
            timeout_s=rag.ollama.generate_timeout_s,
            retries=rag.ollama.retries,
        )
        version = client.version(timeout=rag.ollama.connect_timeout_s)
        names = client.model_names(timeout=max(5.0, rag.ollama.connect_timeout_s))
    except OllamaError as exc:
        return None, ModelStatus(
            reachable=False,
            version="",
            base_url=base_url,
            installed=[],
            embedding_ok=False,
            generation_ok=False,
            vision_installed=False,
            reason=f"Ollama not reachable at {base_url} ({exc})",
        )

    embedding_ok = OllamaClient.has_model(names, rag.embedding.model)
    generation_ok = OllamaClient.has_model(names, rag.generation.model)
    vision_installed = OllamaClient.has_model(names, _VISION_MODEL)
    missing = [
        model
        for model, ok in (
            (rag.embedding.model, embedding_ok),
            (rag.generation.model, generation_ok),
        )
        if not ok
    ]
    if missing:
        reason = (
            "model(s) not installed: "
            + ", ".join(missing)
            + " (run: ollama pull "
            + " && ollama pull ".join(missing)
            + ")"
        )
        return None, ModelStatus(
            reachable=True,
            version=version,
            base_url=base_url,
            installed=names,
            embedding_ok=embedding_ok,
            generation_ok=generation_ok,
            vision_installed=vision_installed,
            reason=reason,
        )

    return client, ModelStatus(
        reachable=True,
        version=version,
        base_url=base_url,
        installed=names,
        embedding_ok=True,
        generation_ok=True,
        vision_installed=vision_installed,
        reason="",
    )


def _lexical_retriever(corpus: CorpusIndexInput, rag: RagSettings) -> HybridRetriever:
    return build_retriever(corpus.records, scope=corpus.scope, config=rag.retrieval)


def _make_service(
    retriever: HybridRetriever,
    assembler: ContextAssembler,
    chat: ChatModelPort,
    prompts: QaPromptSet,
    qa_config: QaConfig,
    model_name: str,
) -> NodeScopedQaService:
    return NodeScopedQaService(
        retriever,
        assembler,
        chat,
        prompts,
        config=qa_config,
        model_name=model_name,
    )


def build_runtime(settings: ApiSettings) -> RagRuntime:
    root = settings.core_root
    rag = load_settings(settings.rag_config_path)
    corpus = build_corpus_records(root)
    if corpus.failures:
        logger.warning(
            "corpus build reported %d failure(s): %s",
            len(corpus.failures),
            corpus.failures,
        )

    prompts = load_qa_prompts(root / rag.qa.prompt_dir, rag.qa.prompt_id)
    assembler = ContextAssembler(rag.context.budget_tokens, rag.context.max_block_tokens)
    qa_config = QaConfig(
        rag.qa.evidence_min_vector,
        rag.qa.evidence_min_lexical,
        rag.qa.escalate_margin,
    )

    index: IndexBuildReport | None = None

    if settings.model_mode == "fake":
        retriever = _lexical_retriever(corpus, rag)
        models = ModelStatus(
            reachable=True,
            version="fake",
            base_url=rag.ollama.base_url,
            installed=[],
            embedding_ok=True,
            generation_ok=True,
            vision_installed=False,
            reason="fake models",
        )
        service = _make_service(
            retriever,
            assembler,
            FakeChatModel(),
            prompts,
            qa_config,
            "fake",
        )
    else:
        client, models = probe_models(rag)
        if not models.ready:
            retriever = _lexical_retriever(corpus, rag)
            service = None
        else:
            assert client is not None
            embedder = OllamaEmbedder(
                client,
                rag.embedding.model,
                rag.embedding.batch_size,
                rag.embedding.num_ctx,
                rag.ollama.keep_alive,
                rag.ollama.embed_timeout_s,
            )
            with SqliteIndexStore(root / rag.index.path) as store:
                index = IndexBuilder(
                    store, embedder, rag.embedding.model, rag.embedding.batch_size
                ).refresh(corpus.records)
                vectors = store.load_vectors(rag.embedding.model)
            if vectors.dim != rag.embedding.dim:
                raise OllamaError(f"embedding dim {vectors.dim} != configured {rag.embedding.dim}")
            retriever = build_retriever(
                corpus.records,
                vectors=vectors,
                embedder=embedder,
                scope=corpus.scope,
                config=rag.retrieval,
            )
            chat = OllamaChatModel(
                client,
                rag.generation.model,
                dict(rag.generation.options),
                rag.generation.think,
                rag.ollama.keep_alive,
                rag.ollama.generate_timeout_s,
            )
            service = _make_service(
                retriever,
                assembler,
                chat,
                prompts,
                qa_config,
                rag.generation.model,
            )

    return RagRuntime(
        rag=rag,
        scope=corpus.scope,
        retriever=retriever,
        service=service,
        models=models,
        index=index,
        mode=retriever.mode,
    )
