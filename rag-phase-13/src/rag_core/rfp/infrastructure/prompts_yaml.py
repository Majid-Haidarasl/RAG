"""``config/prompts/rfp/*.yaml`` -> section headings and the two advisory prompts.

* ``sections.yaml``     — RFP section headings in English and Persian;
* ``rfp_summary.yaml``  — AI summary of an RFP and clarification questions;
* ``feedback.yaml``     — AI feedback to a bidder.

Placeholders are written as ``{facts}``, ``{items}`` and ``{task}`` and are
replaced with ``str.replace`` (so JSON examples with braces stay as they are).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from rag_core.rfp.domain.generator import DEFAULT_HEADINGS
from rag_core.shared_kernel.errors import InvariantError

PROMPT_KEYS = {"id", "version", "system_en", "system_fa", "user_en", "user_fa"}


@dataclass(frozen=True)
class PromptSet:
    prompt_id: str
    version: str
    system_en: str
    system_fa: str
    user_en: str
    user_fa: str

    def render(self, language: str, **values: str) -> tuple[str, str]:
        system = self.system_fa if language == "fa" else self.system_en
        user = self.user_fa if language == "fa" else self.user_en
        for key, value in values.items():
            user = user.replace("{" + key + "}", value)
        return system, user


@dataclass(frozen=True)
class RfpPrompts:
    headings: dict[str, tuple[str, str]] = field(
        default_factory=lambda: dict(DEFAULT_HEADINGS)
    )
    rfp_summary: PromptSet | None = None
    feedback: PromptSet | None = None


def _yaml(path: Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise InvariantError(f"{path.name} must be a mapping")
    return data


def prompt_set(data: dict[str, Any], name: str) -> PromptSet:
    unknown = sorted(set(data) - PROMPT_KEYS)
    if unknown:
        raise InvariantError(f"{name}: unknown keys {', '.join(unknown)}")
    missing = [
        k
        for k in ("system_en", "system_fa", "user_en", "user_fa")
        if not str(data.get(k, "")).strip()
    ]
    if missing:
        raise InvariantError(f"{name}: missing {', '.join(missing)}")
    for k in ("user_en", "user_fa"):
        if "{facts}" not in str(data[k]):
            raise InvariantError(f"{name}: {k} must contain the {{facts}} placeholder")
    return PromptSet(
        str(data.get("id", name)),
        str(data.get("version", "1.0")),
        str(data["system_en"]).strip(),
        str(data["system_fa"]).strip(),
        str(data["user_en"]).strip(),
        str(data["user_fa"]).strip(),
    )


def headings_from(data: dict[str, Any]) -> dict[str, tuple[str, str]]:
    raw = data.get("headings") or {}
    unknown = sorted(set(raw) - set(DEFAULT_HEADINGS))
    if unknown:
        raise InvariantError(f"sections.yaml: unknown headings {', '.join(unknown)}")
    out = dict(DEFAULT_HEADINGS)
    for key, rec in raw.items():
        if (
            not isinstance(rec, dict)
            or not str(rec.get("en", "")).strip()
            or not str(rec.get("fa", "")).strip()
        ):
            raise InvariantError(f"sections.yaml: heading {key} needs en and fa")
        out[key] = (str(rec["en"]).strip(), str(rec["fa"]).strip())
    return out


def load_rfp_prompts(folder: Path) -> RfpPrompts:
    folder = Path(folder)
    return RfpPrompts(
        headings_from(_yaml(folder / "sections.yaml")),
        prompt_set(_yaml(folder / "rfp_summary.yaml"), "rfp_summary.yaml"),
        prompt_set(_yaml(folder / "feedback.yaml"), "feedback.yaml"),
    )
