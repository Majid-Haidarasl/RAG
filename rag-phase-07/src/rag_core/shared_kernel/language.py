"""Language of a knowledge version or a query."""

from __future__ import annotations

from enum import StrEnum

from rag_core.shared_kernel.errors import InvariantError


class LanguageCode(StrEnum):
    FA = "fa"
    EN = "en"

    @classmethod
    def parse(cls, value: str) -> LanguageCode:
        key = value.strip().lower()
        aliases = {"fa": cls.FA, "fas": cls.FA, "per": cls.FA, "persian": cls.FA, "farsi": cls.FA,
                   "en": cls.EN, "eng": cls.EN, "english": cls.EN}
        if key not in aliases:
            raise InvariantError(f"unsupported language: {value!r}")
        return aliases[key]
