"""Extracted-text quality check: catch garbled PDF text instead of calling it success.

Verdicts
--------
``ok``          readable text.
``fragmented``  readable and in logical order, but many words are split by
                spurious spaces (typical for Arabic-script PDFs whose dots are
                positioned as separate glyphs). Usable, reported as a warning.
``garbled``     not usable: glyph-id placeholders such as ``(cid:12)``,
                presentation-form letters, replacement/private-use characters,
                or Persian text in reversed (visual) order. Ingestion fails.
``empty``       no text at all (e.g. image-only page); handled by scan detection.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re

CID_RE = re.compile(r"\(cid:\d+\)")
_ARABIC_LETTER = re.compile(r"[\u0620-\u064a\u066e-\u06d3\u06fa-\u06ff]")
_PRESENTATION = re.compile(r"[\ufb50-\ufdff\ufe70-\ufefe]")
_BAD = re.compile(r"[\ufffd\ue000-\uf8ff]")
_PUNCT_STRIP = " \t\n.,:;!?()[]«»\"'،؛؟-–—|/"

# Frequent Persian function words; their mirror images are not real words.
FUNCTION_WORDS = ("در", "به", "از", "که", "را", "این", "با", "برای", "است", "یا", "می", "هر")
REVERSED_WORDS = tuple(w[::-1] for w in FUNCTION_WORDS)

CID_TOKEN_RATIO = 0.02
PRESENTATION_RATIO = 0.05
BAD_CHAR_RATIO = 0.01
FRAGMENT_RATIO = 0.03
MIN_ARABIC_TOKENS = 30
SINGLE_LETTER_WORDS = frozenset({"و"})
# Real Persian words of one or two letters (closed class + frequent nouns/verbs).
COMMON_SHORT_WORDS = frozenset(
    "و را به از در یا با که تا هر آن نه بر پس یک دو هم چه کل او سه خط حق حل شد طی جا حد ده "
    "سی وب کد صف رخ گم شش من تو ما شما اپ کف رد دل سر پا جز نو بد گل دم کم ای اش ام اند ها "
    "می نمی بی بی‌ ای‌ آب ای".split()
)


@dataclass(frozen=True)
class TextQuality:
    verdict: str
    reasons: tuple[str, ...] = ()
    metrics: dict[str, float] = field(default_factory=dict)

    @property
    def is_garbled(self) -> bool:
        return self.verdict == "garbled"

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["reasons"] = list(self.reasons)
        return data


def assess_text_quality(text: str) -> TextQuality:
    stripped = text.strip()
    if not stripped:
        return TextQuality("empty", (), {"chars": 0})
    tokens = stripped.split()
    n_tokens = max(1, len(tokens))
    cids = len(CID_RE.findall(stripped))
    arabic_letters = len(_ARABIC_LETTER.findall(stripped))
    presentation = len(_PRESENTATION.findall(stripped))
    bad = len(_BAD.findall(stripped))

    words = [t.strip(_PUNCT_STRIP) for t in tokens]
    arabic_tokens = [w for w in words if w and _ARABIC_LETTER.search(w)]
    single = [w for w in arabic_tokens if len(_ARABIC_LETTER.findall(w)) == 1 and w not in SINGLE_LETTER_WORDS]
    fragments = [
        w for w in arabic_tokens if len(_ARABIC_LETTER.findall(w)) <= 2 and w not in COMMON_SHORT_WORDS
    ]
    normal_hits = sum(1 for w in words if w in FUNCTION_WORDS)
    reversed_hits = sum(1 for w in words if w in REVERSED_WORDS)

    metrics = {
        "chars": float(len(stripped)),
        "tokens": float(len(tokens)),
        "cid_ratio": round(cids / n_tokens, 4),
        "presentation_ratio": round(presentation / max(1, arabic_letters + presentation), 4),
        "bad_char_ratio": round(bad / max(1, len(stripped)), 4),
        "arabic_tokens": float(len(arabic_tokens)),
        "single_letter_ratio": round(len(single) / max(1, len(arabic_tokens)), 4),
        "fragment_ratio": round(len(fragments) / max(1, len(arabic_tokens)), 4),
        "function_words": float(normal_hits),
        "reversed_function_words": float(reversed_hits),
    }
    reasons: list[str] = []
    if metrics["cid_ratio"] > CID_TOKEN_RATIO:
        reasons.append(f"glyph-id placeholders (cid) in {metrics['cid_ratio']:.1%} of tokens")
    if metrics["presentation_ratio"] > PRESENTATION_RATIO:
        reasons.append(f"Arabic presentation-form letters ({metrics['presentation_ratio']:.1%})")
    if metrics["bad_char_ratio"] > BAD_CHAR_RATIO:
        reasons.append(f"replacement/private-use characters ({metrics['bad_char_ratio']:.1%})")
    if reversed_hits >= 5 and reversed_hits > normal_hits:
        reasons.append(f"reversed (visual-order) Persian: {reversed_hits} mirrored vs {normal_hits} normal function words")
    if reasons:
        return TextQuality("garbled", tuple(reasons), metrics)
    if len(arabic_tokens) >= MIN_ARABIC_TOKENS and metrics["fragment_ratio"] > FRAGMENT_RATIO:
        return TextQuality(
            "fragmented",
            (
                f"{metrics['fragment_ratio']:.1%} of Persian tokens are 1-2 letter fragments "
                "(spurious intra-word spaces)",
            ),
            metrics,
        )
    return TextQuality("ok", (), metrics)
