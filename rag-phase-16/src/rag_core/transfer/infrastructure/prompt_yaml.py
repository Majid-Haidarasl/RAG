"""Load versioned transfer suggestion prompts from ``config/prompts/transfer/*.yaml``."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from rag_core.shared_kernel.errors import InvariantError


@dataclass(frozen=True)
class TransferPromptSet:
    prompt_id: str
    version: str
    system_en: str
    system_fa: str
    user_en: str
    user_fa: str
    max_sentences: dict[str, int]
    audience_en: dict[str, str]
    audience_fa: dict[str, str]

    def system(self, language: str) -> str:
        return self.system_fa if language == "fa" else self.system_en

    def user_template(self, language: str) -> str:
        return self.user_fa if language == "fa" else self.user_en

    def audience(self, language: str, level: str) -> str:
        table = self.audience_fa if language == "fa" else self.audience_en
        return table.get(level, level)

    def sentences(self, level: str) -> int:
        return int(self.max_sentences.get(level, 6))

    def render(
        self,
        language: str,
        *,
        facts: str,
        audience: str,
        ids: str,
        sentences: int,
    ) -> tuple[str, str]:
        template = self.user_template(language)
        user = (
            template.replace("{facts}", facts)
            .replace("{audience}", audience)
            .replace("{ids}", ids)
            .replace("{sentences}", str(sentences))
        )
        return self.system(language), user


def load_transfer_prompts(
    directory: Path, prompt_id: str = "transfer.suggestions"
) -> TransferPromptSet:
    directory = Path(directory)
    docs: dict[str, dict] = {}
    for path in sorted(directory.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if "id" not in data:
            raise InvariantError(f"{path.name}: missing id")
        docs[data["id"]] = data
    if prompt_id not in docs:
        raise InvariantError(f"transfer prompt {prompt_id!r} not found in {directory}")
    data = docs[prompt_id]
    required = (
        "system_en",
        "system_fa",
        "user_en",
        "user_fa",
        "max_sentences",
        "audience_en",
        "audience_fa",
    )
    missing = [k for k in required if k not in data]
    if missing:
        raise InvariantError(f"{prompt_id}: missing keys {', '.join(missing)}")
    return TransferPromptSet(
        prompt_id=data["id"],
        version=str(data.get("version", "0")),
        system_en=str(data["system_en"]).rstrip("\n"),
        system_fa=str(data["system_fa"]).rstrip("\n"),
        user_en=str(data["user_en"]).rstrip("\n"),
        user_fa=str(data["user_fa"]).rstrip("\n"),
        max_sentences={str(k): int(v) for k, v in dict(data["max_sentences"]).items()},
        audience_en={str(k): str(v) for k, v in dict(data["audience_en"]).items()},
        audience_fa={str(k): str(v) for k, v in dict(data["audience_fa"]).items()},
    )
