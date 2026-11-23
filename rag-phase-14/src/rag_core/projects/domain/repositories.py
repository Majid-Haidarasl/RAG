"""Repository port for the project registry."""

from __future__ import annotations

from typing import Protocol

from rag_core.projects.domain.model import ProjectRegistry


class ProjectRegistrySource(Protocol):
    def load(self) -> ProjectRegistry:
        ...
