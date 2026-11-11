"""Poppler ``pdftotext -bbox`` adapter with RTL line reconstruction.

Why not plain ``pdftotext -layout`` / ``-raw``?
* ``-raw`` keeps content-stream order: Persian glyph runs come out in visual
  (left-to-right) order.
* ``-layout`` gives the right logical order, but Arabic-script fonts whose dots
  are positioned as separate glyphs (Noto Naskh via LibreOffice or Chrome)
  produce spurious spaces inside words: ``ت صمیم``, ``ن سخ ه``.

``-bbox`` gives every poppler "word" (a glyph run, visual order) with its box.
We rebuild each line right-to-left, reverse Arabic runs into logical order,
keep embedded LTR runs (Latin, digits) left-to-right, and decide spaces from
geometry: a gap smaller than ``JOIN_FACTOR`` × the document's typical
inter-word gap joins two Arabic runs. The typical gap is the mode of the
normalized gap histogram, so the rule adapts to font and size.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import html
from pathlib import Path
import re
import shutil
import statistics
import subprocess

_WORD_RE = re.compile(
    r'<word xMin="([-\d.]+)" yMin="([-\d.]+)" xMax="([-\d.]+)" yMax="([-\d.]+)">(.*?)</word>', re.S
)
_ARABIC_LETTER = re.compile(r"[\u0620-\u064a\u066e-\u06d3\u06fa-\u06ff]")
_LTR_CHAR = re.compile(r"[A-Za-z0-9\u06f0-\u06f9\u0660-\u0669]")
_LTR_RUN = re.compile(r"[A-Za-z0-9\u06f0-\u06f9\u0660-\u0669][A-Za-z0-9\u06f0-\u06f9\u0660-\u0669.,:/%+\-]*[A-Za-z0-9\u06f0-\u06f9\u0660-\u0669]")
_BIDI = re.compile(r"[\u202a-\u202e\u200e\u200f\u2066-\u2069]")

JOIN_FACTOR = 0.6
DEFAULT_JOIN_GAP = 0.06  # normalized by box height, used when too few gaps to estimate
MODE_RANGE = (0.07, 0.35)
LINE_TOLERANCE = 0.35
PARAGRAPH_STEP = 1.45
PDFTOTEXT_TIMEOUT_S = 120


def find_pdftotext() -> str | None:
    return shutil.which("pdftotext")


@dataclass(frozen=True)
class Box:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str  # visual order as emitted by poppler

    @property
    def height(self) -> float:
        return max(0.1, self.y1 - self.y0)

    @property
    def center(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def arabic(self) -> bool:
        return bool(_ARABIC_LETTER.search(self.text))

    @property
    def ltr(self) -> bool:
        return not self.arabic and bool(_LTR_CHAR.search(self.text))


@dataclass(frozen=True)
class PopplerPage:
    number: int
    paragraphs: tuple[str, ...]

    @property
    def text(self) -> str:
        return "\n\n".join(self.paragraphs)


def visual_to_logical(run: str) -> str:
    """Reverse an Arabic glyph run; keep embedded numbers/Latin left-to-right."""
    rev = run[::-1]
    return _LTR_RUN.sub(lambda m: m.group(0)[::-1], rev)


def run_bbox(path: Path, executable: str | None = None) -> str:
    exe = executable or find_pdftotext()
    if exe is None:
        raise FileNotFoundError("pdftotext")
    proc = subprocess.run(
        [exe, "-bbox", "-enc", "UTF-8", str(path), "-"],
        capture_output=True,
        text=True,
        timeout=PDFTOTEXT_TIMEOUT_S,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"pdftotext exit {proc.returncode}")
    return proc.stdout


def parse_bbox_pages(xhtml: str) -> list[list[Box]]:
    pages: list[list[Box]] = []
    for chunk in xhtml.split("<page ")[1:]:
        boxes = []
        for x0, y0, x1, y1, raw in _WORD_RE.findall(chunk):
            text = _BIDI.sub("", html.unescape(raw)).strip()
            if text:
                boxes.append(Box(float(x0), float(y0), float(x1), float(y1), text))
        pages.append(boxes)
    return pages


def group_lines(boxes: list[Box]) -> list[list[Box]]:
    lines: list[dict] = []
    for box in sorted(boxes, key=lambda b: b.center):
        if lines and abs(box.center - lines[-1]["c"]) < LINE_TOLERANCE * box.height:
            line = lines[-1]
            line["b"].append(box)
            line["c"] = statistics.fmean(b.center for b in line["b"])
        else:
            lines.append({"c": box.center, "b": [box]})
    return [line["b"] for line in lines]


def _is_rtl(line: list[Box]) -> bool:
    arabic = sum(len(_ARABIC_LETTER.findall(b.text)) for b in line)
    latin = sum(1 for b in line for ch in b.text if ch.isascii() and ch.isalpha())
    return arabic > 0 and arabic >= latin


def _visual_rtl(line: list[Box]) -> list[Box]:
    return sorted(line, key=lambda b: -b.x1)


def _gap(a: Box, b: Box, rtl: bool) -> float:
    h = max(a.height, b.height)
    return ((a.x0 - b.x1) if rtl else (b.x0 - a.x1)) / h


def estimate_join_gap(pages: list[list[Box]]) -> tuple[float, float | None]:
    """Return (join threshold, typical inter-word gap) from Arabic–Arabic gaps."""
    hist: Counter[float] = Counter()
    for boxes in pages:
        for line in group_lines(boxes):
            if not _is_rtl(line):
                continue
            ordered = _visual_rtl(line)
            for a, b in zip(ordered, ordered[1:]):
                if a.arabic and b.arabic:
                    g = round(_gap(a, b, True), 2)
                    if MODE_RANGE[0] <= g <= MODE_RANGE[1]:
                        hist[g] += 1
    if sum(hist.values()) < 30:
        return DEFAULT_JOIN_GAP, None
    mode = hist.most_common(1)[0][0]
    return JOIN_FACTOR * mode, mode


def line_text(line: list[Box], join_gap: float) -> str:
    if not _is_rtl(line):
        ordered = sorted(line, key=lambda b: b.x0)
        return " ".join(b.text for b in ordered)
    visual = _visual_rtl(line)
    # Logical order = visual right-to-left, except runs of LTR boxes which keep
    # their own left-to-right order.
    items: list[tuple[Box, bool]] = []  # (box, join_with_previous)
    i = 0
    while i < len(visual):
        if visual[i].ltr:
            j = i
            while j + 1 < len(visual) and visual[j + 1].ltr:
                j += 1
            for k, box in enumerate(reversed(visual[i : j + 1])):
                items.append((box, False))
            i = j + 1
            continue
        box = visual[i]
        join = (
            i > 0
            and box.arabic
            and visual[i - 1].arabic
            and _gap(visual[i - 1], box, True) < join_gap
        )
        items.append((box, join))
        i += 1
    parts: list[str] = []
    for box, join in items:
        text = visual_to_logical(box.text) if box.arabic else box.text
        if parts and not join:
            parts.append(" ")
        parts.append(text)
    return "".join(parts)


_WORD_FINAL_SINGLES = frozenset({"ه", "ی", "ة"})


def _single_arabic_letter(token: str) -> bool:
    return len(token) == 1 and bool(_ARABIC_LETTER.match(token)) and token != "و"


def repair_single_letters(text: str) -> str:
    """Re-attach stray single Persian letters left by glyph-run splitting.

    Persian has no one-letter words except ``و``. ``ه``/``ی`` are word-final
    far more often, so they join backwards; other letters join forwards
    (``خ دمت`` → ``خدمت``, ``نتیج ه`` → ``نتیجه``).
    """
    tokens = text.split(" ")
    out: list[str] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
        prev_ok = bool(out) and bool(_ARABIC_LETTER.search(out[-1][-1:]))
        next_ok = bool(_ARABIC_LETTER.match(nxt[:1]))
        if _single_arabic_letter(tok):
            if tok in _WORD_FINAL_SINGLES and prev_ok:
                out[-1] += tok
            elif next_ok:
                tokens[i + 1] = tok + nxt
            elif prev_ok:
                out[-1] += tok
            else:
                out.append(tok)
        else:
            out.append(tok)
        i += 1
    return " ".join(out)


def page_paragraphs(boxes: list[Box], join_gap: float) -> tuple[str, ...]:
    lines = group_lines(boxes)
    if not lines:
        return ()
    centers = [statistics.fmean(b.center for b in line) for line in lines]
    steps = [b - a for a, b in zip(centers, centers[1:])]
    typical = statistics.median(steps) if steps else 0.0
    paragraphs: list[list[str]] = [[]]
    for idx, line in enumerate(lines):
        if idx > 0 and typical > 0 and steps[idx - 1] > PARAGRAPH_STEP * typical:
            paragraphs.append([])
        text = repair_single_letters(line_text(line, join_gap).strip())
        if text:
            paragraphs[-1].append(text)
    return tuple(" ".join(p) for p in paragraphs if p)


def extract_pdf_pages(path: Path, executable: str | None = None) -> tuple[list[PopplerPage], dict[str, float | None]]:
    pages = parse_bbox_pages(run_bbox(path, executable))
    join_gap, mode = estimate_join_gap(pages)
    out = [PopplerPage(n, page_paragraphs(boxes, join_gap)) for n, boxes in enumerate(pages, start=1)]
    return out, {"join_gap": round(join_gap, 4), "word_gap_mode": mode}
