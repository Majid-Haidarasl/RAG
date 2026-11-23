# اجرا و نگه‌داری

## اجرای کامل

`bash scripts/setup_and_test.sh` همهٔ کار را انجام می‌دهد: محیط مجازی، نصب، تست‌ها با پوشش کد، و بررسی فاز ۴ تا ۱۶.
هر بررسی کد خروجی ۰ (قبول) یا ۱ (رد) دارد و کد خروجی‌های قبلی را با `--prior` می‌گیرد؛ پس اگر یک فاز رد شود،
بلوک‌های بعدی هم آن را نشان می‌دهند. کد خروجی کل اسکریپت، اولین کد غیر صفر است.

| ترتیب | اسکریپت | بلوک خلاصه |
|---|---|---|
| ۴ | `scripts/run_corpus_ingest.py` | `PHASE 4 INGEST SUMMARY` |
| ۵ | `scripts/run_corpus_dedup.py` | `PHASE 5 SUMMARY` |
| ۶ | `scripts/run_hierarchy_check.py` | `PHASE 6 SUMMARY` |
| ۷ | `scripts/run_issue_check.py` | `PHASE 7 SUMMARY` |
| ۸ | `scripts/run_rag_demo.py` | `PHASE 8 SUMMARY` |
| ۹ | `scripts/run_ike_check.py` | `PHASE 9 SUMMARY` |
| ۱۰ | `scripts/run_judge_check.py` | `PHASE 10 SUMMARY` |
| ۱۱ | `scripts/run_transfer_check.py` | `PHASE 11 SUMMARY` |
| ۱۲ | `scripts/run_project_check.py` | `PHASE 12 SUMMARY` |
| ۱۳ | `scripts/run_rfp_check.py` | `PHASE 13 SUMMARY` |
| ۱۴ | `scripts/run_eval_check.py` | `PHASE 14 SUMMARY` |
| ۱۵ | `scripts/run_quality_check.py` | `PHASE 15 SUMMARY` |
| ۱۶ | `scripts/run_release_check.py` | `PHASE 16 SUMMARY` |

## خروجی‌ها

| مسیر | محتوا | در مخزن؟ |
|---|---|---|
| `results/phase-NN/` | فایل JSON (و گاهی MD) نتیجهٔ هر فاز با برچسب زمان UTC | نه |
| `eval/results/` | نتیجهٔ ارزیابی فاز ۱۴ و جدول به‌روز معیارها | فقط README |
| `results/phase-15/` | `coverage.json`، `coverage.txt`، `htmlcov/` | نه |
| `exports/` | CSVهای انتقال دانش، پروژه‌ها و RFP | نه |
| `.rag-index/` | نمایهٔ SQLite و بردارها | نه |
| `/tmp/rag-phase-16-*.log` | گزارش pip و خروجی هر مرحله | نه |

## تغییر تنظیمات

- همهٔ عددها و نام‌ها در `config/*.yaml` است؛ کلید ناشناخته خطا می‌دهد تا غلط تایپی بی‌صدا نماند.
- بعد از عوض‌کردن پرامپت یا گزینه در `config/eval.yaml`، اجرای کامل نشان می‌دهد انتخاب با اندازه‌گیری می‌خواند یا نه
  (خط‌های `live_confirm` در خلاصهٔ فاز ۱۵ و ۱۶).

## افزودن تست

1. فایل تست را در `tests/unit/<بافت>/` بسازید؛ نامش نباید با فایل دیگری یکی باشد.
2. `pytestmark = [pytest.mark.<marker>]` بگذارید؛ marker تازه را در `pyproject.toml` ثبت کنید.
3. تست نباید به شبکه یا مدل وابسته باشد؛ برای مدل از کلاس ساختگی استفاده کنید.
4. `python -m pytest tests/unit/<بافت> -q`.

## انتشار نسخهٔ تازه

1. نسخه را در همهٔ جاهایی که `config/release.yaml` (بخش `versions`) نام می‌برد یکی کنید.
2. یک بخش تازه بالای `CHANGELOG.md` بنویسید و نسخه را به `changelog.versions` اضافه کنید.
3. `bash scripts/setup_and_test.sh`؛ خلاصهٔ فاز ۱۶ باید `status: PASS` باشد.
4. کامیت، و بعد برچسب git (مثل `v1.0`) روی همان کامیت.
