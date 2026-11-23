"""JSON adapter: data/executors/executor-registry.json → Executor aggregates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rag_core.executors.domain.model import Executor, ExpertiseTag, ReferralCapacity
from rag_core.shared_kernel.identifiers import DocumentId, ExecutorId, NodeIdentifier

REGISTRY_FILE = "executor-registry.json"


def executor_from_record(rec: dict[str, Any]) -> Executor:
    return Executor(
        identifier=ExecutorId(rec["id"]),
        display_name=rec["name_en"],
        home_node=NodeIdentifier(rec["home_node"]),
        expertise=tuple(ExpertiseTag(t) for t in rec.get("expertise", [])),
        allowed_referral_domains=tuple(rec.get("allowed_referral_domains", [])),
        capacity=ReferralCapacity(rec.get("capacity_hours_per_week")),
        name_fa=rec.get("name_fa", ""),
        role=rec.get("role_en", ""),
        role_fa=rec.get("role_fa", ""),
        specialty=tuple(rec.get("specialty", [])),
        knowledge_documents=tuple(DocumentId(d) for d in rec.get("knowledge_documents", [])),
        outputs=tuple(rec.get("outputs", [])),
        authority_limits=tuple(rec.get("authority_limits", [])),
        aliases=tuple(rec.get("aliases", [])),
        profile_version=str(rec.get("profile_version", "1.0")),
        source_document=rec.get("source", "AR-EXE-023"),
    )


class JsonExecutorRegistry:
    def __init__(self, directory: Path) -> None:
        self.dir = Path(directory)

    def records(self) -> list[dict[str, Any]]:
        data = json.loads((self.dir / REGISTRY_FILE).read_text(encoding="utf-8"))
        return list(data["executors"])

    def load(self, records: list[dict[str, Any]] | None = None) -> list[Executor]:
        return [executor_from_record(r) for r in (records if records is not None else self.records())]
