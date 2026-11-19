"""Question language: the answer must be in the language of the question."""

from __future__ import annotations

from rag_core.knowledge.domain.fingerprint import guess_language


def question_language(text: str) -> str:
    guess = guess_language(text)
    if guess is not None:
        return guess
    arabic = sum(1 for ch in text if "\u0600" <= ch <= "\u06ff")
    latin = sum(1 for ch in text if ch.isascii() and ch.isalpha())
    return "fa" if arabic >= latin and arabic > 0 else "en"
