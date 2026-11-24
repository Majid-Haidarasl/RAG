"""Ports of the prioritization context (signals come in through infrastructure ACLs)."""

from __future__ import annotations

from typing import Protocol

from rag_core.prioritization.domain.model import IssueSignal


class SignalSource(Protocol):
    def signals(self) -> list[IssueSignal]: ...
