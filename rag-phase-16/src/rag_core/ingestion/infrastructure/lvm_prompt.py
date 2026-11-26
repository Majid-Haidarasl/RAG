"""Load versioned LVM page-text prompts from ``config/prompts/lvm/*.yaml``."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from rag_core.shared_kernel.errors import InvariantError


@dataclass(frozen=True)
class LvmPrompt:
    prompt_id: str
    version: str
    system: str
    user: str

    @property
    def task_prompt(self) -> str:
        system = self.system.strip()
        user = self.user.strip()
        if system and user:
            return f"{system}\n\n{user}"
        return system or user


def load_lvm_prompt(
    directory: Path, prompt_id: str = "lvm.page_text"
) -> LvmPrompt:
    directory = Path(directory)
    docs: dict[str, dict] = {}
    for path in sorted(directory.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if "id" not in data:
            raise InvariantError(f"{path.name}: missing id")
        docs[data["id"]] = data
    if prompt_id not in docs:
        raise InvariantError(f"prompt {prompt_id} not found in {directory}")
    doc = docs[prompt_id]
    return LvmPrompt(
        prompt_id=doc["id"],
        version=str(doc["version"]),
        system=str(doc.get("system") or ""),
        user=str(doc.get("user") or ""),
    )
