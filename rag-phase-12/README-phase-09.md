# فاز ۹ — تحلیل مجریان و مدل مسئله–دانش–مجری (نسخهٔ ۰.۹.۰)

هستهٔ RAG سلسله‌مراتبی آفلاین · مطالعهٔ موردی **آرمان‌رایان** · ایشو #۹ گیت‌هاب · پرونده مرجع: **آذرپخش** (AR-ISS-024).

این بسته روی فاز ۸ سوار می‌شود و بافت‌های `executors` و `ike` را کامل می‌کند: پروفایل مجریان با فرادادهٔ تخصص (بر پایهٔ AR-EXE-023)، تطبیق توضیح‌پذیر مجری با زیرمسئله، مقایسهٔ دانشِ ارجاع‌شده در مسئله با دانشی که گره مالک می‌تواند بازیابی کند (بازیاب فاز ۸)، گراف رابطه‌های نوع‌دار بین مسئله، زیرمسئله، دانش و مجری، و خلاصهٔ مسئله که با بررسی واقعیت سنجیده می‌شود. تست‌ها با جایگزین‌های ساختگی اجرا می‌شوند و به Ollama، GPU یا اینترنت نیاز ندارند.

وابستگی تازه‌ای اضافه نشده است.

## سیستم هدف

- Ubuntu 24.04.5 LTS، پایتون 3.12.3؛
- پردازندهٔ Intel Core i5-12400F، ۱۶ گیگابایت RAM؛
- کارت گرافیک NVIDIA RTX 3060 با ۱۲ گیگابایت حافظه (فقط مرحلهٔ زندهٔ Ollama از GPU استفاده می‌کند)؛
- Ollama 0.40.2 با مدل‌های `bge-m3:latest` و `qwen3:8b`؛
- مسیر پروژه `~/Desktop/RAG`.

مرحلهٔ زنده از همان نمایهٔ فاز ۸ (`.rag-index/phase-08.sqlite`) استفاده می‌کند؛ اگر پیکره تغییر نکرده باشد چیزی دوباره embed نمی‌شود. فقط دو خلاصه (فارسی و انگلیسی) با `qwen3:8b` تولید می‌شود.

## پیش‌نیاز مرحلهٔ زنده

```bash
ollama list
```

باید `bge-m3:latest` و `qwen3:8b` در فهرست باشند. اگر Ollama یا یکی از مدل‌ها نباشد، مرحلهٔ زنده `skipped` گزارش می‌شود و نتیجهٔ PASS/FAIL را تغییر نمی‌دهد.

## اجرا روی اوبونتو

فرض: zip در `~/Downloads/rag-phase-09.zip` است و کلون ریپو در `~/Desktop/RAG`.

```bash
cd ~/Downloads
unzip -o rag-phase-09.zip -d ~/Desktop/RAG
cd ~/Desktop/RAG
bash scripts/setup_and_test.sh
```

ترتیب اجرا: `pytest`، ورود پیکره (فاز ۴)، چرخهٔ عمر و تکرار (فاز ۵)، سلسله‌مراتب (فاز ۶)، بررسی مسئله‌ها (فاز ۷)، مرحلهٔ RAG (فاز ۸)، سپس بررسی مجریان و IKE فاز ۹.

آخرین بلوک بین دو خط `======== PHASE 9 SUMMARY (paste this block) ========` چاپ می‌شود. **همان بلوک آخر را کامل کپی کن و بفرست.**

اجرای جدا:

```bash
source .venv/bin/activate
pytest -m "matching or ike_model"
python scripts/run_ike_check.py            # بررسی آفلاین + مرحلهٔ زنده
python scripts/run_ike_check.py --no-live  # فقط بررسی آفلاین
```

## چه چیزی ساخته شد

- **پروفایل مجریان** (`data/executors/executor-registry.json`):
  - ۱۵ مجری نام‌برده در AR-EXE-023، هر کدام با گره تیمی خانه (لایهٔ ۳ سلسله‌مراتب فاز ۶)؛
  - تخصص اصلی، حوزه‌های مجاز ارجاع (فارسی و انگلیسی)، برچسب‌های تخصص، اسناد دانشی در اختیار، خروجی‌ها و حدود اختیار؛
  - ظرفیت ارجاع به ساعت در هفته؛ برای منابع انسانی، مالی و حقوقی ظرفیت منتشر نشده (`null`) و از راه برنامه‌ریزی واحد تعیین می‌شود؛ نه صفر است و نه نامحدود؛
  - حقوق و دستمزد عمداً ثبت نشده است (داده محرمانه)؛
  - نام‌های جایگزین، مثل `Rouzbeh Mohseni` در فهرست مسئله‌ها که به `EX-ROOZBEH-MOHSENI` می‌رسد؛
  - اعتبارسنجی: شناسه، یکتایی، گره خانه، لایهٔ ۳، وجود اسناد در فهرست پیکره، بازهٔ ظرفیت.
- **تطبیق مجری:**
  - متن زیرمسئله (عنوان، دامنه و خروجی پذیرش) با واژگان تخصص هر مجری مقایسه می‌شود؛
  - امتیاز = ۰٫۴ گره (مالک ۱، پشتیبان ۰٫۶) + ۰٫۳ اسناد مشترک + ۰٫۳ واژه‌های حوزه؛
  - دست‌کم دو واژهٔ مشترک لازم است؛ یک کلیدواژه کافی نیست (AR-EXE-023)؛
  - نقش‌ها: نامزد مسئول، همکار، نامزد بیرون از گره (فقط نمایش)، کنار گذاشته؛
  - مرجع پذیرش: `board` برای تصمیم رزروشده (LEG)، وگرنه مالک تیم؛
  - دفتر ظرفیت: اگر ساعت‌های رزرو از ظرفیت بگذرد، خطا می‌دهد و اولویت‌بندی با معاون مربوط است.
- **مقایسهٔ مسئله و دانش:** برای هر زیرمسئله، جست‌وجو از گره مالک با بازیاب فاز ۸ (top_k=8): اسناد پوشش‌داده‌شده، پیشنهادی (بازیابی‌شده ولی ارجاع‌نشده)، جاافتاده، بیرون از دامنه، و وجود شاهد کافی.
- **مدل رابطه‌های IKE:** شش نوع رابطه `relates_to`، `part_of`، `depends_on`، `can_handle`، `evidence_for`، `knowledge_lack` با قاعدهٔ نوع دو سر رابطه، بررسی تکرار، وابستگی بین زیرمسئله‌های یک مسئله و تشخیص چرخه.
- **کمبود دانش:** سند ارجاع‌شده‌ای که هیچ مجری پیشنهادی در اختیار ندارد، نبودِ مسئول، سند بیرون از دامنهٔ گره مالک، نبودِ شاهد در دامنه.
- **خلاصهٔ مسئله:** فهرست واقعیت‌ها از گراف، خلاصهٔ قالبی فارسی و انگلیسی، و در مرحلهٔ زنده خلاصهٔ `qwen3:8b`؛ هر شناسه و عدد خلاصه باید در واقعیت‌ها باشد (بررسی واقعیت فاز ۸) و پوشش زیرمسئله‌ها شمرده می‌شود.

## خطوط مورد انتظار در خلاصه

این مقدارها روی سیستم آزمون تأیید شدند:

```
status: PASS
executors: total=15 home_nodes=13 capacity_published=12 unpublished=3 validation_errors=0 warnings=3
matching: case=AR-ISS-024 sub_issues=4 recommended=9 named=9 seed_agreement=4/4 precision=1.0 recall=1.0
  AR-ISS-024/HW: lead=Saeed Akbari collab=Farzaneh Javadi,Ehsan Davari authority=team_owner:N-HW-REP seed=ok
  AR-ISS-024/WIN: lead=Roozbeh Mohseni collab=- authority=team_owner:N-SW-WIN seed=ok
  AR-ISS-024/WEB: lead=Nazanin Farahani collab=Hanieh Saadati,Yasaman Karami authority=team_owner:N-SW-WEB seed=ok
  AR-ISS-024/LEG: lead=Mahsa Jalali collab=Reza Abbasi authority=board seed=ok
referral_roles: lead_candidate=5 collaborator=4 cross_node_candidate=0 excluded=51
referral_policy: EX-KIAN-RAZAVI@WEB=excluded EX-AMIN-TOURANI@WEB=excluded EX-ROOZBEH-MOHSENI@HW=excluded EX-KAMRAN-NIKPOUR@HW=excluded EX-FARZANEH-JAVADI@WIN=excluded
ike_registry_graph: relations=51 relates_to=23 can_handle=9 evidence_for=11 knowledge_lack=2 depends_on=2 part_of=4
summary_template: fa=grounded:True coverage=4/4 claims=20 en=grounded:True coverage=4/4 claims=20
live: ok
checks: pytest=ok prior_steps=ok executor_registry_valid=ok seed_executors_resolved=ok matching_matches_seed=ok referral_policy=ok leads_match_exe023=ok records_built=ok ike_graph_valid=ok ike_graph_consistent=ok template_summaries_grounded=ok
```

ترتیب نام همکاران در هر سطر بر پایهٔ امتیاز است. شاخص‌های مقایسهٔ دانش (`knowledge_offline`، `live_knowledge`) و شمار رابطه‌های گراف آفلاین و زنده به نتیجهٔ بازیابی بستگی دارند.

## نتیجه روی داده‌ها

سیستم آزمون: Ubuntu 24.04.5 LTS، پایتون 3.12.3، پردازندهٔ Intel Core i5-12400F، ۱۶ گیگابایت RAM، کارت گرافیک NVIDIA RTX 3060 با ۱۲ گیگابایت حافظه؛ مسیر پروژه `~/Desktop/RAG`. Ollama 0.40.2، مدل embedding `bge-m3:latest` و مدل تولید `qwen3:8b` (حالت تفکر خاموش).

زمان اجرا: ۲۸ آبان ۱۴۰۵، ساعت ۰۳:۳۱ به وقت تهران (2026-11-19 00:01:13 UTC). خلاصهٔ فاز ۹: `status: PASS`. فایل نتیجه: `results/phase-09/ike-check-20261119T000113Z.json`.

| شاخص | مقدار |
|---|---|
| تست‌ها | ۷۸۸ پاس، ۰ شکست، ۰ خطا، ۰ ردشده (۲۹٫۳۲ ثانیه) |
| مراحل قبلی | ingest، dedup، hierarchy، issues، rag همه با خروج ۰ |
| مجریان و اعتبارسنجی | ۱۵ مجری، ۱۳ گره خانه، ظرفیت منتشرشده ۱۲، منتشرنشده ۳، خطا ۰، هشدار ۳ |
| تطبیق AR-ISS-024 | ۴ زیرمسئله، ۹ پیشنهاد، ۹ نام‌برده، توافق با فهرست ۴ از ۴، دقت ۱٫۰، بازخوانی ۱٫۰ |
| نقش‌های ارجاع | نامزد مسئول ۵، همکار ۴، نامزد بیرون از گره ۰، کنارگذاشته ۵۱ |
| سیاست ارجاع | هر پنج مورد کنار گذاشته شد (کیان@WEB، امین@WEB، روزبه@HW، کامران@HW، فرزانه@WIN) |
| بار کاری | ۹ از ۱۵ مجری با ارجاع؛ چهار مسئول اصلی مطابق AR-EXE-023 |
| تطبیق مسئله‌های تخت | ۶ مسئله، ۴ تا با مسئول |
| مقایسهٔ دانش آفلاین | واژگانی، یادآوری ارجاع در ۸ مورد ۰٫۸۷۵، پوشش ۵ از ۱۰، پیشنهادی ۱۱، بیرون از دامنه ۴، با شاهد ۴ از ۴ |
| گراف فهرست | ۵۱ رابطه: relates_to ۲۳، can_handle ۹، evidence_for ۱۱، knowledge_lack ۲، depends_on ۲، part_of ۴ |
| گراف آفلاین | ۶۵ رابطه: relates_to ۳۴، can_handle ۹، evidence_for ۱۱، knowledge_lack ۵، depends_on ۲، part_of ۴ |
| کمبود دانش | HW→AR-HW-013، HW→AR-HW-015، WIN→AR-HW-015، WEB→AR-RFP-025، LEG→AR-FIN-010 |
| خلاصهٔ قالبی | فارسی و انگلیسی هر دو مبتنی بر واقعیت، پوشش ۴ از ۴، هر کدام ۲۰ ادعا |
| مرحلهٔ زنده | ok |
| نمایهٔ زنده | ۱۲۱۹ فعال، ۰ embed تازه، ۱۲۱۹ استفاده‌شدهٔ مجدد، بعد ۱۰۲۴، ساخت ۰٫۱۳۵ ثانیه |
| مقایسهٔ دانش زنده | ترکیبی، یادآوری ارجاع در ۸ مورد ۱٫۰، پوشش ۶ از ۱۰، پیشنهادی ۹، با شاهد ۴ از ۴، میانگین جست‌وجو ۰٫۰۶۵۷ ثانیه |
| گراف زنده | ۶۳ رابطه: relates_to ۳۲، can_handle ۹، evidence_for ۱۱، knowledge_lack ۵، depends_on ۲، part_of ۴ |
| خلاصهٔ زنده فارسی | مبتنی بر واقعیت، ادعای بی‌پشتوانه ۰، پوشش ۴ از ۴، ۴۲۶ نویسه، تولید ۴٫۳۰۹ ثانیه، توکن ۹۹۵+۲۱۹ |
| خلاصهٔ زنده انگلیسی | مبتنی بر واقعیت، ادعای بی‌پشتوانه ۰، پوشش ۴ از ۴، ۱۰۰۱ نویسه، تولید ۵٫۸۲۸ ثانیه، توکن ۸۶۱+۳۱۲ |
| زمان کل مرحلهٔ زنده | ۱۲٫۴ ثانیه |
| بررسی‌ها | هر ۱۱ مورد ok |

| زیرمسئله | مسئول | همکاران | مرجع پذیرش |
|---|---|---|---|
| AR-ISS-024/HW | سعید اکبری | فرزانه جوادی، احسان داوری | team_owner:N-HW-REP |
| AR-ISS-024/WIN | روزبه محسنی | — | team_owner:N-SW-WIN |
| AR-ISS-024/WEB | نازنین فراهانی | هانیه سعادتی، یاسمن کرمی | team_owner:N-SW-WEB |
| AR-ISS-024/LEG | مهسا جلالی | رضا عباسی | هیئت‌مدیره |

نمایهٔ فاز ۸ دوباره استفاده شد و embedding تکرار نشد. یادآوری ارجاع در مرحلهٔ زنده از ۰٫۸۷۵ آفلاین به ۱٫۰ رسید. هر دو خلاصهٔ مدل بدون ادعای بی‌پشتوانه و با پوشش کامل چهار زیرمسئله تولید شد.

## خروجی‌ها

| مسیر | محتوا |
|---|---|
| `src/rag_core/executors/domain/` | پروفایل، تخصص، تطبیق، ظرفیت، اعتبارسنجی، درگاه‌ها |
| `src/rag_core/executors/application/` | بارگذاری فهرست، سرویس تطبیق، مقایسه با فهرست مسئله‌ها، بار کاری |
| `src/rag_core/executors/infrastructure/` | خواندن JSON، مخزن حافظه، لایه‌های ضدفساد سلسله‌مراتب و مسئله‌ها |
| `src/rag_core/ike/domain/` | مدل رابطه‌ها، نماها، مقایسهٔ دانش، سازندهٔ گراف، خلاصه |
| `src/rag_core/ike/application/` | سرویس IKE و سرویس خلاصه |
| `src/rag_core/ike/infrastructure/` | لایه‌های ضدفساد مسئله‌ها، مجریان و بازیاب فاز ۸ |
| `data/executors/` | فهرست مجریان و توضیح فیلدها |
| `scripts/run_ike_check.py` | بررسی آفلاین، مرحلهٔ زنده، بلوک خلاصهٔ فاز ۹ |
| `results/phase-09/` | فایل JSON نتایج هر اجرا |
| `tests/unit/executors/`، `tests/unit/ike/` | تست‌های فاز ۹ |
| `docs/phase-09/ike-model.md` | طراحی مدل مجری و IKE، قاعده‌ها و نکته‌های باز |
