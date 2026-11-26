from __future__ import annotations

import re

from rag_core.models.domain.ports import LlmResult

_BLOCK_LABEL = re.compile(r"^\[([^\]]+)\]", re.M)


class FakeChatModel:
    def generate(self, system: str, user: str) -> LlmResult:
        match = _BLOCK_LABEL.search(user)
        if match is None:
            return LlmResult(text="INSUFFICIENT_CONTEXT")
        return LlmResult(text=f"پاسخ آزمایشی. [{match.group(1)}]")
