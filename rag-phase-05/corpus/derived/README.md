# Derived corpus samples (Phase 4)

The official ArmanRayan corpus remains the 52 DOCX files in `corpus/fa` and `corpus/en`. Those files are **not** rewritten (spec 7.6 / Phase 1 usage rule). Persian-digit identifiers inside eight FA files are normalized at ingestion time.

This folder holds a small number of DOC and PDF **exports of existing documents**, plus one synthetic image-only PDF, so the Phase 4 adapters can be exercised on every supported format:

| Subfolder | Content |
|---|---|
| `pdf/` | Text PDFs exported with LibreOffice from selected DOCX files |
| `doc/` | Legacy `.doc` exports of the same sources |
| `scanned/` | One image-only PDF used to verify scan detection (no OCR is run) |

Re-generate locally (optional, requires LibreOffice):

```bash
# see scripts in the Phase 4 kit; the checked-in files are already generated
```
