"""config/rag.yaml: models and endpoint live in config, not in code."""

from pathlib import Path

import pytest

from rag_core.rag.infrastructure.config import load_settings, settings_from_dict
from rag_core.shared_kernel.errors import InvariantError

pytestmark = [pytest.mark.rag, pytest.mark.retrieval]

ROOT = Path(__file__).resolve().parents[3]


def test_shipped_config_matches_phase2_decisions() -> None:
    s = load_settings(ROOT / "config" / "rag.yaml")
    assert s.ollama.base_url == "http://localhost:11434"
    assert s.embedding.model == "bge-m3:latest" and s.embedding.dim == 1024
    assert s.generation.model == "qwen3:8b" and s.generation.think is False
    assert s.generation.options["temperature"] <= 0.3 and s.generation.options["num_ctx"] == 8192
    assert s.retrieval.rrf_k == 60 and s.retrieval.top_k == 5
    assert s.retrieval.near_duplicate_threshold == 0.80
    assert 8 <= s.embedding.batch_size <= 32
    assert s.ollama.generate_timeout_s >= 120 and s.ollama.connect_timeout_s <= 5
    assert s.index.path.startswith(".rag-index/")
    assert (ROOT / s.qa.prompt_dir / "answer.yaml").is_file()


def test_defaults_when_sections_missing() -> None:
    s = settings_from_dict({})
    assert s.generation.model == "qwen3:8b" and s.context.budget_tokens == 3500


def test_unknown_keys_rejected() -> None:
    with pytest.raises(InvariantError, match="unknown keys"):
        settings_from_dict({"embedding": {"modle": "x"}})
    with pytest.raises(InvariantError, match="unknown config sections"):
        settings_from_dict({"cloud": {}})
    with pytest.raises(InvariantError, match="mapping"):
        settings_from_dict({"qa": ["x"]})


def test_index_cache_is_gitignored() -> None:
    assert ".rag-index/" in (ROOT / ".gitignore").read_text(encoding="utf-8")
