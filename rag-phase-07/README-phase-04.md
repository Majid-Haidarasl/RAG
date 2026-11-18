# فاز ۴ — زیربنای ورود سند

هستهٔ RAG سلسله‌مراتبی آفلاین · مطالعهٔ موردی **آرمان‌رایان** · ایشو #۴ گیت‌هاب.

این بسته روی خروجی فاز ۳ سوار می‌شود: پارسرهای DOC/DOCX/PDF، طرح‌وارهٔ فراداده، مدل ارجاع به منبع، خردسازی ساخت‌یافته، و نرمال‌سازی فارسی. تست واحد به Ollama و GPU نیاز ندارد. ورود پیکره هم فقط فایل محلی می‌خواند.

## استخراج داخل ریشهٔ ریپو

فرض: zip در `~/Downloads/rag-phase-04.zip` است و کلون ریپو در `~/Desktop/RAG`. اگر مسیر فرق دارد، همین دو جا را عوض کن. پوشهٔ `.venv` در `.gitignore` است و روی گیت نمی‌رود.

```bash
cd ~/Downloads
unzip -o rag-phase-04.zip -d ~/Desktop/RAG
cd ~/Desktop/RAG
bash scripts/setup_and_test.sh
```

اسکریپت محیط مجازی می‌سازد، وابستگی‌ها را نصب می‌کند، `pytest` را اجرا می‌کند و بعد پیکره را وارد می‌کند. در پایان یک بلوک بین دو خط `======== PHASE 4 SUMMARY` چاپ می‌شود. **همان بلوک را کامل کپی کن و بفرست.**

اگر ساخت `.venv` با خطا دربارهٔ `ensurepip` یا `venv` شکست: `sudo apt install -y python3.12-venv`

اگر `soffice` نصب نیست (تبدیل DOC لازم است): `sudo apt install -y libreoffice-writer --no-install-recommends`

نصب pip برای بار اول اینترنت می‌خواهد. خود تست و ورود سند شبکه را صدا نمی‌زنند.

اجرای جدا:

```bash
cd ~/Desktop/RAG
source .venv/bin/activate
pytest --strict-markers --tb=short
python scripts/run_corpus_ingest.py
```

## خروجی‌های این فاز

| مسیر | محتوا |
|---|---|
| `docs/phase-04/metadata-schema.md` | شرح فراداده |
| `schemas/knowledge-metadata.json` | JSON Schema |
| `docs/phase-04/source-reference-model.md` | لنگر صفحه / بند / افست / سلول جدول |
| `docs/phase-04/chunking-spec.md` | خردسازی با سقف مناسب bge-m3 |
| `src/rag_core/ingestion/` | آداپترها، نرمال‌سازی، خردساز، خط لوله |
| `corpus/` | ۵۲ سند DOCX اصلی به‌علاوه نمونهٔ DOC/PDF مشتق |
| `tests/unit/ingestion/` | تست واحد با فیکسچر ساخته‌شده |
| `scripts/run_corpus_ingest.py` | ورود پیکره و بلوک خلاصه |
| `گزارش-فاز-۴.docx` | گزارش کوتاه فارسی |

اسناد اصلی پیکره دست‌نخورده مانده‌اند. شناسه‌های با رقم فارسی در هشت فایل، هنگام ورود به رقم لاتین نرمال می‌شوند.
