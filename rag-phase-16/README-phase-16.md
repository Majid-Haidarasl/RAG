# فاز ۱۶ — جمع‌بندی و انتشار (نسخهٔ ۱.۰.۰)

هستهٔ RAG سلسله‌مراتبی آفلاین · مطالعهٔ موردی **آرمان‌رایان** · ایشو #۱۶ گیت‌هاب («Final wrap-up»).

فاز ۱۶ آخرین فاز است. کار تازه‌ای به سیستم اضافه نمی‌کند؛ پروژه را برای تحویل آماده می‌کند:

1. **مستندات نهایی:** `README.md` کل پروژه، راهنمای کاربر، گزارش نهایی فاز ۱ تا ۱۶، مستندات فنی و فهرست شواهد.
2. **اسلایدها و آموزش:** ۱۲ اسلاید فارسی با منبعشان، متن دموی زنده، و مسیر آموزشی با تمرین برای عضو تازهٔ تیم.
3. **بررسی انتشار:** اسکریپت `scripts/run_release_check.py` با تنظیمات `config/release.yaml`.
4. **انتخاب `ai_ids`:** به `baseline` برگشت، چون اجرای فاز ۱۵ آن را بهتر از `listed_guarded` اندازه گرفت.
5. **مرتب‌کردن متن‌ها:** سرخط همهٔ بلوک‌های خلاصه یک‌شکل شد و توضیح‌های اضافهٔ اجرا در READMEها و اسکریپت‌ها کوتاه شد.
6. **چک‌لیست:** همهٔ خروجی‌های طرح ۱۶ فازی انجام شده‌اند؛ فقط برچسب `v1.0` مانده که بعد از اجرای نهایی زده می‌شود.

## بررسی انتشار چه چیزهایی را می‌سنجد

| بررسی | یعنی |
|---|---|
| `version_consistent` | نسخهٔ `1.0.0` در `pyproject.toml`، بستهٔ پایتون و فایل‌های تنظیمات یکی است |
| `docs_complete` | ۱۴ سند انتشار هست، کوتاه نیست و خط‌های اصلی‌اش را دارد |
| `phrase_scan` | در هیچ فایل متنی پروژه، عبارت‌های پیش‌نویس (فهرست `scan.phrases`) نمانده است |
| `negative_controls` | بررسی‌ها خطای عمدی را می‌گیرند: عبارت کاشته‌شده، سند کوتاه یا گمشده، نسخهٔ غلط، CHANGELOG ناقص، اسلاید کم |
| `changelog` | `CHANGELOG.md` همهٔ نسخه‌ها از 0.3.0 تا 1.0.0 را دارد و تازه‌ترین بالاست |
| `presentation` | فایل `.pptx` واقعاً pptx است، ۱۰ تا ۱۲ اسلاید دارد و منبعش هست |
| `evidence_present` | برای هر فاز دست‌کم یک فایل نتیجه از همین اجرا هست |
| `checklist_complete` | چک‌لیست بی‌مشکل است و جز برچسب `v1.0` کاری نمانده |
| `eval_defaults` | `config/eval.yaml` چهار انتخاب اندازه‌گیری‌شده را دارد (`ai_ids=baseline`) |
| `phase15_result` | بررسی کیفیت فاز ۱۵ در همین اجرا PASS شده است |

مثل فاز ۱۵، تأیید زندهٔ چهار انتخاب از نتیجهٔ فاز ۱۴ همین اجرا خوانده می‌شود و کنار وضعیت گزارش می‌شود
(`live_confirm` و `live_confirmed`)؛ قبولی به مدل وابسته نیست.

## انتخاب `ai_ids`

در اجرای فاز ۱۵ (۳ آذر ۱۴۰۵):

| گزینه | شناسهٔ نام‌برده | پذیرفته | شناسهٔ ساختگی |
|---|---|---|---|
| `baseline` | 11/18 | 2/4 | 0 |
| `listed_retry` | 15/18 | 2/4 | 1 |
| `listed_guarded` | 9/18 | 1/4 | 0 |

قاعدهٔ انتخاب (اول نرخ پذیرش، بعد شناسهٔ ساختگی کمتر) `baseline` را برمی‌گزیند. پس `config/eval.yaml` حالا
`ai_ids: baseline` دارد و `listed_guarded` به‌عنوان گزینه می‌ماند. قاعده عوض نشده است؛ اگر اجرای بعدی نتیجهٔ دیگری
بدهد، خط `live_confirm: ai_ids … agrees=NO` آن را نشان می‌دهد.

## اجرا

روی Ubuntu، یا روی Windows 11 داخل Ubuntu در WSL 2 (نصب: `docs/user-guide.md`):

```bash
cd ~/Desktop/RAG
unzip -o ~/Downloads/rag-phase-16.zip
bash scripts/setup_and_test.sh 2>&1 | tee ~/rag-phase-16-run.log
```

اسکریپت همان اسکریپت فازهای قبل است؛ بعد از بررسی فاز ۱۵، بررسی فاز ۱۶ اجرا می‌شود و آخرین بلوک
`PHASE 16 SUMMARY` است.

## در خلاصه چه انتظاری داریم

- تست‌ها: **1715** قبول (1643 قبلی + ۷۲ تست تازه)، صفر رد.
- `version: 1.0.0 places=7/7`
- `docs: complete=14/14`
- `phrase_scan: files=… phrases=11 hits=0`
- `negative_controls: phrases=11/11 short_doc=caught missing_doc=caught wrong_version=caught changelog=caught deck=caught`
- `changelog: versions=14 newest=1.0.0 problems=0`
- `presentation: presentation/armanrayan-rag-core.pptx slides=12 source=yes problems=0`
- `evidence: present=13/13`
- `checklist: deliverables=80 done=63 external=13 run=3 planned=1 phases=16 problems=0`
- `checklist_phases: 1=done 2=external 3=done … 15=done 16=partial`
- `eval_defaults: retrieval=baseline qa_prompt=qa.answer judge_prompt=strict_precheck ai_ids=baseline expected=4/4 problems=0`
- چهار خط `live_confirm … agrees=yes` و `readiness: ready=yes live_confirmed=4/4`
- `checks:` همه `ok` (۱۲ بررسی) و `status: PASS`.

در بلوک فاز ۱۴ خط `selection:` حالا `ai_ids=baseline` نشان می‌دهد و در بلوک فاز ۱۵ خط چک‌لیست همان عددهای بالا را دارد.

## نتیجهٔ اجرا روی سیستم آزمون

اجرا در ۳ آذر ۱۴۰۵، حدود ساعت ۰۲:۱۱ به وقت تهران (20261123T224140Z به وقت جهانی)، با پایتون 3.15.2 و Ollama 0.40.17.
نتیجه: **همهٔ فازهای ۴ تا ۱۶ `status: PASS`**؛ در فاز ۱۶ هر ۱۲ بررسی `ok`.

| مورد | مقدار |
|---|---|
| تست‌ها | 1715 قبول، 0 رد (59.23 ثانیه) |
| پوشش خط / شاخه | 96.3٪ (13977/14509) / 89.8٪ (3595/4002)، ۲۹۲ ماژول |
| موجودی تست | ۲۳ پوشه، ۱۵۷ فایل، ۱۲۸۶ تابع تست |
| نسخه | `version: 1.0.0 places=7/7` |
| مستندات | `docs: complete=14/14` |
| عبارت‌ها | `phrase_scan: files=569 phrases=11 hits=0` |
| کنترل‌های منفی | همه گرفته شد (`phrases=11/11`، سند کوتاه و گمشده، نسخهٔ غلط، CHANGELOG، اسلاید) |
| CHANGELOG / اسلایدها / شواهد | `versions=14` / `slides=12` / `present=13/13` |
| چک‌لیست | `deliverables=80 done=63 external=13 run=3 planned=1 phases=16 problems=0` |
| انتخاب‌ها | `eval_defaults … expected=4/4`؛ چهار خط `live_confirm … agrees=yes` |
| آمادگی | `readiness: ready=yes live_confirmed=4/4` |
| شناسه‌ها در فاز ۱۴ | `baseline` ۲ از ۴ پذیرفته، ۰ شناسهٔ ساختگی |
| داور در فاز ۱۴ | `strict_precheck` ۳۸ از ۴۲، kappa 0.809 |

فایل نتیجه: `results/phase-16/release-check-20261123T224140Z.json`.

## برچسب انتشار v1.0

بعد از `status: PASS` بالا، کامیت فاز ۱۶ در مخزن قرار گرفت و برچسب `v1.0` («first release») روی همان کامیت زده شد.

## خروجی‌ها

| مسیر | محتوا |
|---|---|
| `README.md` | معرفی کل پروژه |
| `CHANGELOG.md` | تغییرات هر نسخه تا 1.0.0 |
| `docs/user-guide.md` | نصب روی Ubuntu و Windows 11 (WSL 2)، مدل‌های Ollama و اجرا |
| `docs/final-report.md` | گزارش نهایی با نتیجه‌های اندازه‌گیری‌شده |
| `docs/technical/` | معماری و نگه‌داری |
| `docs/phase-16/final-checklist.md` | چک‌لیست نهایی ۸۰ خروجی |
| `eval/evidence/README.md` | هر عدد از کدام فایل نتیجه می‌آید |
| `presentation/` | اسلایدها، منبعشان و متن دمو |
| `training/` | مسیر آموزشی و تمرین‌ها |
| `config/release.yaml`، `scripts/run_release_check.py` | بررسی انتشار |
| `tests/unit/release/` | تست‌های فاز ۱۶ |
| `results/phase-16/release-check-<UTC>.json` و `.md` | نتیجهٔ بررسی انتشار در هر اجرا |

## چه چیزهایی مرتب شد

- سرخط بلوک‌های خلاصه همه به شکل `======== PHASE N SUMMARY ========` شد (فاز ۴: `PHASE 4 INGEST SUMMARY`).
- جمله‌های اضافهٔ دربارهٔ رونوشت‌گرفتن از خروجی از READMEها و اسکریپت‌ها حذف شد؛ حالا فقط گفته می‌شود عددهای
  بخش «نتیجه» از کدام بلوک آمده‌اند. خلاصهٔ اجرای فاز ۲ حالا با `RUN SUMMARY` شروع می‌شود.
- توضیح سرآغاز `scripts/setup_and_test.sh` کوتاه و فهرست‌وار شد و گزارش‌های موقت به نام `/tmp/rag-phase-16-*.log` نوشته می‌شوند.
- وضعیت فاز در چک‌لیست: فازی که خروجی‌هایش این‌جا انجام شده یا در پوشهٔ خودش تحویل شده، `done` حساب می‌شود
  (قبلاً فاز ۱ با این‌که کامل بود `partial` نشان داده می‌شد).
- `config/release.yaml` نوع منبع نسخه را هم بررسی می‌کند تا غلط تایپی بی‌صدا نماند.

## محدودیت‌ها

- بررسی عبارت‌ها فقط فهرست ثابت `scan.phrases` را می‌گردد، نه هر جملهٔ نامناسب.
- اسلایدها با فونت Vazirmatn ساخته شده‌اند؛ بدون آن فونت ظاهرشان کمی عوض می‌شود.
- عددهای گزارش نهایی روی پیکرهٔ کوچک و ساختگی آرمان‌رایان اندازه‌گیری شده‌اند.
