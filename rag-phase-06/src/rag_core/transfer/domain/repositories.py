from __future__ import annotations

from typing import Protocol

from rag_core.shared_kernel.identifiers import NodeIdentifier
from rag_core.transfer.domain.model import TransferPackage, TransferRuleSet
from rag_core.shared_kernel.layer import LayerIndex


class TransferPackageRepository(Protocol):
    def save(self, package: TransferPackage) -> None: ...
    def latest_accepted(self, source_node: NodeIdentifier, target_node: NodeIdentifier) -> TransferPackage | None: ...


class TransferRuleSetRepository(Protocol):
    def get(self, layer: LayerIndex) -> TransferRuleSet: ...
