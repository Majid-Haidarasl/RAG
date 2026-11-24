"""Load ``config/prompts/qa/*.yaml`` into a ``QaPromptSet``."""

from __future__ import annotations

from pathlib import Path

import yaml

from rag_core.qa.domain.prompts import QaPromptSet
from rag_core.shared_kernel.errors import InvariantError


def load_qa_prompts(directory: Path, prompt_id: str = "qa.answer") -> QaPromptSet:
    directory = Path(directory)
    docs: dict[str, dict] = {}
    for path in sorted(directory.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if "id" not in data:
            raise InvariantError(f"{path.name}: missing id")
        docs[data["id"]] = data
    if prompt_id not in docs:
        raise InvariantError(f"prompt {prompt_id} not found in {directory}")
    answer = docs[prompt_id]
    messages_doc = docs.get(answer.get("messages", "qa.messages"), {})
    return QaPromptSet(
        prompt_id=answer["id"],
        version=str(answer["version"]),
        system=answer["system"],
        user=answer["user"],
        refusal_token=answer.get("refusal_token", "INSUFFICIENT_CONTEXT"),
        language_names=dict(
            answer.get("language_names") or {"fa": "Persian (فارسی)", "en": "English"}
        ),
        messages={k: dict(v) for k, v in (messages_doc.get("messages") or {}).items()},
    )
