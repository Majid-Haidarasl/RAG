# تمرین‌ها

پیش از شروع، یک بار `bash scripts/setup_and_test.sh` را اجرا کنید و بعد `source .venv/bin/activate`.

## تمرین ۱ — اجرای تست‌ها

```bash
python -m pytest tests/unit/hierarchy -q
python -m pytest -m qa -q
```

**پرسش:** چند تست در بافت `hierarchy` هست؟ یک تست را باز کنید و بگویید چه چیزی را می‌سنجد.

## تمرین ۲ — یک پرسش در محدودهٔ گره

`python scripts/run_rag_demo.py --no-live` را اجرا کنید و در فایل نتیجهٔ `results/phase-08/` یک پرسش را پیدا کنید.

**پرسش:** کدام تکه‌ها برگشتند و از کدام سندها بودند؟ چرا تکه‌ای از گرهٔ دیگر برنگشت؟

## تمرین ۳ — خواندن داوری

در تازه‌ترین `results/phase-10/judge-check-*.json` یک خروجی رد‌شده پیدا کنید.

**پرسش:** کدام معیار امتیاز کم گرفت؟ داور قاعده‌ای و داور مدل هم‌نظر بودند؟

## تمرین ۴ — قاعدهٔ انتخاب

بخش `selection_rules` و `selection` در `config/eval.yaml` را بخوانید.

**پرسش:** چرا `ai_ids` روی `baseline` است و نه `listed_guarded`؟ اگر `listed_guarded` در اجرای بعدی ۳ از ۴ قبول
بگیرد، چه چیزی در خلاصهٔ فاز ۱۴ و ۱۶ عوض می‌شود؟

## تمرین ۵ — نوشتن یک تست

یک تست کوچک در `tests/unit/shared_kernel/` بنویسید که تبدیل یک عدد فارسی (مثل «۱۴۰۵») به عدد انگلیسی را بسنجد.
نام فایل باید در کل پروژه یکتا باشد.

```bash
python -m pytest tests/unit/shared_kernel -q
```

## تمرین ۶ — بررسی انتشار

یک خط به `README.md` اضافه کنید که از یکی از عبارت‌های فهرست `scan.phrases` در `config/release.yaml` استفاده کند و
`python scripts/run_release_check.py` را اجرا کنید.

**پرسش:** کدام بررسی `FAIL` شد و خط `phrase_scan:` چه نشان داد؟ بعد خط را پاک کنید و دوباره اجرا کنید.

## پاسخ‌ها

پاسخ‌ها با خود کد و فایل‌های نتیجه پیدا می‌شوند؛ اگر جایی گیر کردید، `docs/technical/` و `README-phase-NN.md`
همان فاز را ببینید.
