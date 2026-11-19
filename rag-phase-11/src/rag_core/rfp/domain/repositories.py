from __future__ import annotations

from typing import Protocol

from rag_core.rfp.domain.model import Rfp
from rag_core.shared_kernel.identifiers import RfpId


class RfpRepository(Protocol):
    def get(self, rfp_id: RfpId) -> Rfp: ...
    def save(self, rfp: Rfp) -> None: ...
