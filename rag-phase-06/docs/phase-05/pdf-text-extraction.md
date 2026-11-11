# PDF text extraction — fix 0.5.1 (finding F5-1)

Status: implemented in `rag-core 0.5.1`. Context: **Ingestion**.
Code: `src/rag_core/ingestion/infrastructure/pdf_poppler.py`,
`parser_pdf.py`, `src/rag_core/ingestion/domain/text_quality.py`.

## Problem

The Phase 4 adapter used `pdfplumber` for PDF text. For the three Persian PDF
renditions (AR-FIN-008, AR-HR-005, AR-SW-022, exported by LibreOffice with
Noto Naskh Arabic) it returned `(cid:NN)` glyph placeholders and Persian runs in
**visual** (reversed) order. Parsing did not fail, so Phase 4 counted the files
as "success". Side effect: the Persian-digit ID normalizer "fixed" 72 bogus IDs in
the garbled FIN-008 text (ingest `id_digits` 460 → 391 after the fix; the 52
DOCX files are unchanged at 388).

## What we tried (box, poppler 25.03)

| Option | Persian result | Why |
|---|---|---|
| pdfplumber | garbled (37 % cid tokens, 212 mirrored vs 37 normal function words) | no ToUnicode use for the Type 3 subset font; visual order |
| `pdftotext -raw` | glyph runs in visual order | content-stream order |
| `pdftotext -layout` | logical order, but spurious spaces inside words (`ت صمیم`, `ن سخ ه`) and some displaced glyphs | dots are positioned as separate glyphs, so poppler sees gaps |
| **`pdftotext -bbox` + our line rebuild** | logical order, ~1,360 spurious splits per document removed, char-5 Jaccard to DOCX 0.86–0.97 | chosen |

The splitting also appears with a static (non-variable) Noto Naskh font and in
a Chrome-printed PDF, so it is a property of how the glyphs are positioned
(not only of LibreOffice). Some ambiguity is left: a few false gaps are exactly as
wide as real spaces (`داخ|لی` 2.47 pt vs a real space of 2.43 pt).

## Algorithm (`pdf_poppler.py`)

1. `pdftotext -bbox -enc UTF-8` → every glyph run ("word") with its box; bidi
   control marks removed.
2. Lines: group boxes by vertical centre (tolerance 0.35 × box height).
3. Direction: a line is RTL if it has Arabic-script letters and at least as
   many of them as Latin letters.
4. RTL lines: sort boxes right-to-left; reverse each Arabic run into logical
   order (`visual_to_logical`, embedded numbers/Latin keep their direction);
   consecutive LTR boxes (Latin/digits) keep left-to-right order.
5. Spaces: between two Arabic runs, the gap is normalized by box height. The
   typical inter-word gap is the **mode** of these gaps in [0.07, 0.35]
   (box: 0.11 for LibreOffice PDFs, 0.13 for Chrome). Gaps < **0.6 × mode** are
   joined. A ground-truth check against the DOCX found zero real spaces below
   this threshold. With fewer than 30 gaps the default is 0.06.
6. `repair_single_letters`: Persian has no one-letter words except `و`, so a
   stray single letter is re-attached (`ه`/`ی` backwards, others forwards).
7. Paragraph break when the line step is > 1.45 × the median step.

pdfplumber is still used for page count, scanned-page detection (images,
char count) and table cells. Its tables are kept only if their text passes the
quality check (Persian tables are already in the poppler text).

## Quality check (`text_quality.py`)

| Verdict | Rule | Effect |
|---|---|---|
| `garbled` | cid placeholders > 2 % of tokens, presentation-form letters > 5 %, replacement/private-use > 1 %, or ≥ 5 mirrored function words outnumbering normal ones | `GarbledTextError` (ingest **failure**) |
| `fragmented` | ≥ 30 Persian tokens and > 3 % are 1–2-letter tokens outside a closed list of real short words | kept, warning |
| `ok` / `empty` | otherwise / no text | normal; empty pages go to scan detection |

Calibration: all 52 DOCX files score `ok` (max fragment ratio 0.0066). The
three Persian PDFs score `fragmented` (0.079–0.111): readable and in logical
order, but some two-letter splits remain (`مرخ صی`, `حض ور`).

## Missing poppler

If `pdftotext` is not on PATH the adapter falls back to pdfplumber, adds the
warning `pdftotext not found … sudo apt install -y poppler-utils`, and Persian
PDFs then fail as garbled, with the same hint. `scripts/setup_and_test.sh` checks
for `pdftotext` and prints the hint. The poppler unit tests are skipped
without it.

## Impact on dedup

Word shingles still see the remaining splits, so chunk-level matching between a
Persian PDF and its DOCX is partial. Document-level rendition matching uses
whitespace-insensitive **character 5-grams** of the normalized text, comparing
all document pairs exactly (59 documents). It matches all 7 renditions,
including the 3 Persian PDFs (J = 0.86, 0.97, 0.96). See
`versioning-and-dedup.md` §5.
