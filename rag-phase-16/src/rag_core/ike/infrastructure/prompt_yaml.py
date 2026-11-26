"""Load versioned IKE summary prompts from ``config/prompts/ike/*.yaml``."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from rag_core.shared_kernel.errors import InvariantError


@dataclass(frozen=True)
class IkeSummaryPromptSet:
    prompt_id: str
    version: str
    system_en: str
    system_fa: str
    user_en: str
    user_fa: str

    def system(self, language: str) -> str:
        return self.system_fa if language == "fa" else self.system_en

    def user_template(self, language: str) -> str:
        return self.user_fa if language == "fa" else self.user_en

    def render(self, language: str, *, facts: str) -> tuple[str, str]:
        template = self.user_template(language)
        return self.system(language), template.replace("{facts}", facts)


def load_ike_summary_prompts(
    directory: Path, prompt_id: str = "ike.summary"
) -> IkeSummaryPromptSet:
    directory = Path(directory)
    docs: dict[str, dict] = {}
    for path in sorted(directory.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if "id" not in data:
            raise InvariantError(f"{path.name}: missing id")
        docs[data["id"]] = data
    if prompt_id not in docs:
        raise InvariantError(f"ike prompt {prompt_id!r} not found in {directory}")
    data = docs[prompt_id]
    required = ("system_en", "system_fa", "user_en", "user_fa")
    missing = [k for k in required if k not in data]
    if missing:
        raise InvariantError(f"{prompt_id}: missing keys {', '.join(missing)}")
    return IkeSummaryPromptSet(
        prompt_id=data["id"],
        version=str(data.get("version", "0")),
        system_en=str(data["system_en"]).rstrip("\n"),
        system_fa=str(data["system_fa"]).rstrip("\n"),
        user_en=str(data["user_en"]).rstrip("\n"),
        user_fa=str(data["user_fa"]).rstrip("\n"),
    )
