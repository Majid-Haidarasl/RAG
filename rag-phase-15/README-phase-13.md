# فاز ۱۳ — ساختن درخواست پیشنهاد (RFP) و مدیریت پیشنهادها (نسخهٔ ۰.۱۳.۰)

هستهٔ RAG سلسله‌مراتبی آفلاین · مطالعهٔ موردی **آرمان‌رایان** · ایشو #۱۳ گیت‌هاب.

در فاز ۱۲ سیستم گفت مدیرعامل اول سراغ کدام مسئله‌ها برود (AR-ISS-024، AR-ISS-031 و AR-ISS-035). بعضی از این مسئله‌ها را باید **با کمک یک شرکت بیرونی** حل کرد؛ مثلاً ماژول گزارش‌گیری وب انبار آذرپخش. در فاز ۱۳ سیستم برای چنین مسئله‌ای یک **درخواست پیشنهاد** (RFP) می‌نویسد، پیشنهادهای رسیده را **ثبت می‌کند**، با **وزن‌های شفاف** به آن‌ها نمره می‌دهد، بررسی می‌کند که تصمیم ثبت‌شده با نمره‌ها می‌خواند، برای هر پیشنهاددهنده **بازخورد خودکار** می‌نویسد و نتیجه را به **دانش گره‌ها** (چه کسی در سازمان چه چیزی را می‌داند) وصل می‌کند.

همه‌چیز با قالب ثابت و از روی داده‌های ثبت‌شده ساخته می‌شود و هیچ عدد یا شناسه‌ای از خودش نمی‌سازد. مدل `qwen3:8b` فقط یک کار اختیاری و مشورتی دارد. وابستگی تازه‌ای اضافه نشده است. تست‌ها به Ollama، کارت گرافیک یا اینترنت نیاز ندارند.

## چند واژه به زبان ساده

- **درخواست پیشنهاد (RFP):** نامه‌ای که سازمان برای شرکت‌های بیرونی می‌فرستد: «این کار را لازم داریم، این‌ها شرط‌های ماست، پیشنهادتان را با این قالب بفرستید و ما با این معیارها انتخاب می‌کنیم.»
- **پیش‌نویس ثابت (blueprint):** فایل `data/rfp/rfp-blueprints.json`. نیازمندی‌ها، معیارها و پیوندهای دانش یک RFP را نگه می‌دارد. هر جمله‌اش از سند AR-RFP-025 گرفته شده و به آن ارجاع دارد.
- **نیازمندی (requirement):** یک بند RFP، مثل «دامنهٔ کار» یا «شرط پذیرش». ۱۱ بند داریم؛ ۷ بند **الزامی** (mandatory) است و بقیه **توصیه‌شده**.
- **معیار وزن‌دار (weighted criterion):** چیزی که پیشنهاد با آن سنجیده می‌شود. اینجا دو معیار: **فنی** با وزن ۶۰٪ و **مالی** با وزن ۴۰٪ (جمع وزن‌ها باید دقیقاً ۱ باشد).
- **امتیاز وزنی (weighted score):** `۰٫۶ × امتیاز فنی + ۰٫۴ × امتیاز مالی`. سهم هر معیار جدا چاپ می‌شود تا معلوم باشد عدد نهایی از کجا آمده (شفافیت).
- **دفتر پیشنهادها (proposal registry):** فایل `data/proposals/proposal-registry.json`. دو پیشنهاد (الف و ب)، قیمت، مدت، امتیاز ثبت‌شده و تصمیم نهایی در آن است.
- **انطباق (compliance):** پیشنهادی که یکی از بخش‌های خواسته‌شده (مثلاً «طرح آزمون») را نداشته باشد، «ناقص» است و نمی‌تواند برنده شود.
- **پشتوانهٔ سند (evidence grounding):** هر عدد و شناسه‌ای که در نیازمندی‌ها، پیشنهادها و بازخوردها آمده باید در متن سند منبع هم باشد (هر دو زبان).
- **پیوند دانش (knowledge link):** می‌گوید هر بخش از RFP به کدام گره و کدام فرد مربوط است؛ مثلاً بررسی سازگاری معماری با تیم وب (N-SW-WEB). نتیجهٔ انتخاب هم زیر زیرمسئلهٔ AR-ISS-024/WEB ثبت می‌شود.
- **بازخورد خودکار (automated feedback):** متن کوتاهی برای هر پیشنهاددهنده: امتیاز و نحوهٔ محاسبه، رتبه، برنده، فاصلهٔ قیمت و زمان، یادداشت ارزیاب و پرسش‌های روشن‌سازی.
- **داور (judge):** همان داور فاز ۱۰. متن RFP و بازخوردها را مثل یک خلاصه نمره می‌دهد (۲۰ نمره، قبولی از ۱۸).
- **کنترل منفی (negative control):** نسخهٔ خراب عمدی از داده یا متن. سیستم باید همهٔ آن‌ها را رد کند تا مطمئن شویم بررسی‌ها واقعاً کار می‌کنند.
- **لایهٔ ضدفساد (ACL):** کد کوچکی که دادهٔ فازهای قبل (مسئله‌ها، رتبه‌بندی، شکاف‌ها، مجریان) را به شکل سادهٔ موردنیاز فاز ۱۳ درمی‌آورد.

## از فاز ۱ تا ۱۳ در یک نگاه

| فاز | چه کردیم (ساده) |
|---|---|
| ۱–۲ | برنامه و نیازمندی‌ها؛ انتخاب `qwen3:8b` و `bge-m3`. |
| ۳ | اسکلت پروژه و بافت‌ها. |
| ۴ | خواندن و تکه‌کردن اسناد. |
| ۵ | چرخهٔ عمر دانش (نسخهٔ فعال) و متن‌های تکراری. |
| ۶ | چارت سازمانی: لایه‌ها و گره‌ها. |
| ۷ | مسئله و زیرمسئله (پروندهٔ آذرپخش AR-ISS-024). |
| ۸ | RAG: جست‌وجو و پاسخ با ارجاع. |
| ۹ | مجریان، گراف مسئله–دانش–مجری، خلاصهٔ مسئله. |
| ۱۰ | داور و روبریک ۲۰ نمره‌ای (قبولی از ۱۸). |
| ۱۱ | پردازش دوره‌ای گره‌ها و بستهٔ انتقال دانش به بالا. |
| ۱۲ | دفتر پروژه، قاعده‌های شکاف و انتخاب مسئله‌های کلیدی. |
| ۱۳ | ساختن RFP از مسئله‌های کلیدی، ثبت و نمره‌دهی پیشنهادها، بازخورد و پیوند به دانش گره‌ها. |

## سیستم هدف

- Fedora Linux، پایتون 3.15.2 (اسکریپت همان `python3` سیستم را برمی‌دارد)؛
- پردازندهٔ Intel Core i5-12400F، ۱۶ گیگابایت RAM؛
- کارت گرافیک NVIDIA RTX 3060 با ۱۲ گیگابایت حافظه؛
- Ollama با `qwen3:8b` (فقط برای مرحلهٔ زندهٔ اختیاری)؛
- مسیر پروژه `~/Desktop/RAG`.

کد روی پایتون 3.12 تا 3.15 کار می‌کند.

## فاز ۱۳ چه کار می‌کند (قدم‌به‌قدم)

1. **ورودی‌های فاز ۱۲ را دوباره می‌سازد** (بدون Ollama): مسئله‌ها، مجریان، شکاف‌ها و رتبه‌بندی چرخهٔ 1403-Q2. سه مسئلهٔ کلیدی: AR-ISS-024، AR-ISS-031 و AR-ISS-035.
2. **تصمیم می‌گیرد کدام مسئله RFP لازم دارد** (`config/rfp.yaml`):

   | مسئله | رتبه | دلیل | نتیجه |
   |---|---|---|---|
   | AR-ISS-024 | ۱ | هدف تعیین‌شده: زیرمسئلهٔ AR-ISS-024/WEB باید از بیرون تأمین شود | RFP |
   | AR-ISS-031 | ۲ | نوعش «زمان‌بندی» است، نه خرید | بدون RFP |
   | AR-ISS-035 | ۳ | نوعش «خرید/انتخاب پیمانکار» است | همان RFP |

   هر دو مسئله به یک پیش‌نویس (BP-WEB-REPORTING) می‌رسند، پس **یک RFP** ساخته می‌شود: **AR-RFP-1403-07** «ماژول گزارش‌گیری وب انبار آذرپخش».
3. **پیش‌نویس را بررسی می‌کند:** گره مالک، مسئله‌ها، زیرمسئله، سندها و مجریان واقعاً وجود دارند؛ جمع وزن‌ها ۱ است؛ هر ۷ بخش الزامی هست؛ هر مجری واقعاً عضو گره‌ای است که برایش نوشته شده.
4. **پشتوانهٔ سند را می‌سنجد:** ۱۱ نیازمندی و ۷ پیوند در هر دو زبان با متن سند AR-RFP-025 (و AR-SW-016) مقایسه می‌شوند و عدد وزن‌ها (۶۰ و ۴۰) هم باید در سند باشد.
5. **متن RFP را می‌سازد** (فارسی و انگلیسی) با این بخش‌ها: شناسه، چرا این درخواست (رتبه، امتیاز و عوامل اصلی از فاز ۱۲)، شکاف‌های دانشی روی این کار، نیاز، دامنه، تحویل‌دادنی‌ها، خارج از دامنه، معماری، امنیت، آزمون، قالب پیشنهاد، ارزیابی، پذیرش، انتقال دانش، معیارهای وزن‌دار و «دانش نزد کیست». داور قاعده‌ای فاز ۱۰ به آن نمره می‌دهد. چون RFP یک سند است و از خلاصه بلندتر، حد طول آن ۶۰۰۰ نویسه است (`judging.max_rfp_chars`).
6. **پیشنهادها را ثبت و نمره‌دهی می‌کند:**

   | پیشنهاد | شرکت | قیمت (میلیون تومان) | مدت | فنی × ۰٫۶ | مالی × ۰٫۴ | امتیاز وزنی |
   |---|---|---|---|---|---|---|
   | PRP-A (الف) | داده پرداز شفق | ۲۸۵ | ۷ هفته | ۸۲ → ۴۹٫۲ | ۷۴ → ۲۹٫۶ | **۷۸٫۸** |
   | PRP-B (ب) | نوین گزارش پارس | ۲۴۰ | ۵ هفته | ۶۸ → ۴۰٫۸ | ۸۶ → ۳۴٫۴ | **۷۵٫۲** |

   هر دو عدد با برگهٔ ارزیابی ثبت‌شده در سند می‌خوانند. برنده PRP-A است با ۳٫۶ امتیاز فاصله، هرچند PRP-B ۴۵ میلیون تومان ارزان‌تر و ۲ هفته کوتاه‌تر است. تصمیم ثبت‌شده هم PRP-A است، پس **تصمیم با نمره‌ها سازگار است**.
7. **بازخورد خودکار** برای هر دو پیشنهاد در هر دو زبان نوشته می‌شود و داور به هر چهار متن نمره می‌دهد.
8. **به دانش گره‌ها وصل می‌کند:** ۷ پیوند به ۶ گره (تیم وب، تجربهٔ کاربری، پشتیبانی، حقوقی، مالی، کتابخانهٔ دانش) و ۶ نفر؛ نتیجه (PRP-A با ۷۸٫۸) زیر AR-ISS-024/WEB ثبت می‌شود.
9. **کنترل‌های منفی:**
   - ۷ پیش‌نویس خراب: سند ساختگی، جمع وزن غیر از ۱، عدد ساختگی (۶۵٪ به جای ۶۰٪)، حذف بخش الزامی «پذیرش»، گره ناشناخته، مجری روی گره اشتباه، مسئلهٔ ناشناخته؛
   - ۱۰ دفتر پیشنهاد خراب: امتیاز مالی از فرمول قیمت (۸۴٫۲ به جای ۷۴)، قیمت غلط (۲۵۰)، معیار ساختگی، امتیاز جاافتاده، امتیاز ۱۱۰، حذف «طرح آزمون»، تصمیم به نفع پیشنهاد پایین‌تر، RFP ناشناخته، شناسهٔ تکراری، عدد ساختگی در بازخورد؛
   - ۶ متن RFP خراب و ۱۲ بازخورد خراب (عدد ساختگی، شناسهٔ ساختگی، حذف شناسه‌ها).

   همه باید رد شوند، **و هر کدام به دلیل درست** (مثلاً قیمت غلط باید با کد `ungrounded_number` رد شود).
10. **خروجی CSV:** پنج فایل `rfp_requirements.csv`، `proposals.csv`، `evaluation.csv`، `feedback.csv` و `knowledge_links.csv` در `exports/rfp/AR-RFP-1403-07/` (با UTF-8 که اکسل فارسی را درست نشان دهد) و دوباره خوانده می‌شوند.
11. **مرحلهٔ زندهٔ اختیاری:** اگر Ollama و `qwen3:8b` باشند، مدل (بدون حالت فکرکردن، با خروجی JSON) یک **خلاصهٔ RFP** و یک **بازخورد برای پیشنهاد PRP-B** به هر دو زبان می‌نویسد. عددها و شناسه‌ها بررسی می‌شوند، داور قاعده‌ای و داور مدل نمره می‌دهند. این فقط **مشورت** است و روی RFP، نمره‌ها، تصمیم یا PASS/FAIL اثری ندارد.

## پیش‌نیاز مرحلهٔ زنده

```bash
ollama list
```

باید `qwen3:8b` در فهرست باشد. مدل embedding لازم نیست. اگر Ollama یا مدل نباشد، مرحلهٔ زنده `skipped` گزارش می‌شود. مرحلهٔ زنده حدود ۱۰ بار مدل را صدا می‌زند (۴ متن + ۶ داوری).

## اجرا روی لینوکس (Fedora)

فرض: zip در `~/Downloads/rag-phase-13.zip` است و کلون ریپو در `~/Desktop/RAG`.

```bash
cd ~/Downloads
unzip -o rag-phase-13.zip -d ~/Desktop/RAG
cd ~/Desktop/RAG
bash scripts/setup_and_test.sh
```

ترتیب اجرا: `pytest`، فازهای ۴ تا ۷، RAG فاز ۸، IKE فاز ۹، داور فاز ۱۰، انتقال فاز ۱۱، پروژه‌های فاز ۱۲ و در آخر RFP فاز ۱۳. آخرین بلوک بین دو خط `======== PHASE 13 SUMMARY (paste this block) ========` و `======== END PHASE 13 SUMMARY ========` چاپ می‌شود. **همان بلوک آخر را کامل کپی کن و بفرست.**

اجرای جدا:

```bash
source .venv/bin/activate
pytest -m "rfp or rfp_gen or proposals"
python scripts/run_rfp_check.py            # همه‌چیز + متن‌های هوش مصنوعی (اگر Ollama باشد)
python scripts/run_rfp_check.py --no-live  # فقط بخش آفلاین
```

## در خلاصه چه انتظاری داریم

این عددها از روی داده‌ها پیش‌بینی شده‌اند؛ عدد واقعی همان است که روی سیستم خودت چاپ می‌شود.

- تعداد تست‌ها: ۱۲۰۷ تست قبلی + ۱۴۸ تست تازه = **۱۳۵۵**.
- `prior_steps: ingest=0 dedup=0 hierarchy=0 issues=0 rag=0 ike=0 judge=0 transfer=0 projects=0`
- `inputs: cycle=1403-Q2 key=AR-ISS-024,AR-ISS-031,AR-ISS-035 gaps=14 blueprints=1 proposals=2 executors=15`
- `rfp_candidates: key=3 sourcing=2 (AR-ISS-024:target->BP-WEB-REPORTING,AR-ISS-035:procurement->BP-WEB-REPORTING) none=1 (AR-ISS-031:not_sourcing) rfps=1`
- `blueprint: BP-WEB-REPORTING rfp=AR-RFP-1403-07 requirements=11 (mandatory=7) criteria=2 weights=60+40 links=7 problems=0`
- `evidence: blueprint fa=18/18 en=18/18 weights fa=2/2 en=2/2`
- `evidence: proposals numbers fa=2/2 en=2/2 statements fa=4/4 en=4/4`
- `rfp AR-RFP-1403-07 fa: … gaps=1 … rule=20 accepted` و همین برای `en` (شکاف KL:AR-ISS-024/WEB).
- `evaluation: PRP-A weighted=78.8 (CRT-TECH 82x0.6=49.2 + CRT-FIN 74x0.4=29.6) published=78.8 match=yes rank=1 compliant=yes price=285 weeks=7`
- `evaluation: PRP-B weighted=75.2 (CRT-TECH 68x0.6=40.8 + CRT-FIN 86x0.4=34.4) published=75.2 match=yes rank=2 compliant=yes price=240 weeks=5`
- `decision: selected=PRP-A winner=PRP-A consistent=yes margin=3.6 cheapest=PRP-B price_gap=45 fastest=PRP-B duration_gap=2 published_match=2/2`
- چهار خط `feedback … rule=20 accepted`.
- `knowledge: links=7 valid=7 nodes=6 executors=6 outcome=AR-ISS-024/WEB<-PRP-A`
- `negative_controls: blueprint rejected=7/7 proposals rejected=10/10 rfp_text rejected=6/6 feedback rejected=12/12 by_kind=wrong_number:6/6,fabricated_id:6/6,drop_items:6/6`
- `csv: files=5 dir=exports/rfp/AR-RFP-1403-07 round_trip_problems=0`
- `live: skipped` (بدون Ollama) یا `live: ok` با خط‌های `live_ai` و `live_judge`.
- `checks:` همه `ok` (۱۴ بررسی) و `status: PASS`.

## نتیجهٔ اجرا روی سیستم من

اجرا: ۲ آذر ۱۴۰۵، حدود ساعت ۲۳:۱۹ به وقت تهران، روی Fedora Linux با پایتون 3.15.2، LibreOffice 26.8.3.1، pdftotext 26.08.0 و Ollama 0.40.17 با مدل `qwen3:8b` (همان سخت‌افزار: i5-12400F، ۱۶ گیگابایت RAM، RTX 3060 با ۱۲ گیگابایت). نتیجه: **PASS**، هر ۱۴ بررسی `ok`.

```text
======== PHASE 13 SUMMARY (paste this block) ========
status: PASS
kit: rag-core 0.13.0 (phase 13 rfp generation, proposal management)
python: 3.15.2
pytest_exit: 0
pytest_passed: 1355
pytest_failed: 0
pytest_errors: 0
pytest_skipped: 0
prior_steps: ingest=0 dedup=0 hierarchy=0 issues=0 rag=0 ike=0 judge=0 transfer=0 projects=0
inputs: cycle=1403-Q2 key=AR-ISS-024,AR-ISS-031,AR-ISS-035 gaps=14 blueprints=1 proposals=2 executors=15
rfp_candidates: key=3 sourcing=2 (AR-ISS-024:target->BP-WEB-REPORTING,AR-ISS-035:procurement->BP-WEB-REPORTING) none=1 (AR-ISS-031:not_sourcing) rfps=1
blueprint: BP-WEB-REPORTING rfp=AR-RFP-1403-07 requirements=11 (mandatory=7) criteria=2 weights=60+40 links=7 problems=0
evidence: blueprint fa=18/18 en=18/18 weights fa=2/2 en=2/2
evidence: proposals numbers fa=2/2 en=2/2 statements fa=4/4 en=4/4
rfp AR-RFP-1403-07 fa: sections=11 requirements=11 issues=AR-ISS-024,AR-ISS-035 gaps=1 words=569 chars=3679 rule=20 accepted
rfp AR-RFP-1403-07 en: sections=11 requirements=11 issues=AR-ISS-024,AR-ISS-035 gaps=1 words=528 chars=4232 rule=20 accepted
evaluation: PRP-A weighted=78.8 (CRT-TECH 82x0.6=49.2 + CRT-FIN 74x0.4=29.6) published=78.8 match=yes rank=1 compliant=yes price=285 weeks=7
evaluation: PRP-B weighted=75.2 (CRT-TECH 68x0.6=40.8 + CRT-FIN 86x0.4=34.4) published=75.2 match=yes rank=2 compliant=yes price=240 weeks=5
decision: selected=PRP-A winner=PRP-A consistent=yes margin=3.6 cheapest=PRP-B price_gap=45 fastest=PRP-B duration_gap=2 published_match=2/2
feedback PRP-A fa: chars=612 rule=20 accepted
feedback PRP-A en: chars=724 rule=20 accepted
feedback PRP-B fa: chars=718 rule=20 accepted
feedback PRP-B en: chars=853 rule=20 accepted
knowledge: links=7 valid=7 nodes=6 executors=6 outcome=AR-ISS-024/WEB<-PRP-A
negative_controls: blueprint rejected=7/7 proposals rejected=10/10 rfp_text rejected=6/6 feedback rejected=12/12 by_kind=wrong_number:6/6,fabricated_id:6/6,drop_items:6/6
csv: files=5 dir=exports/rfp/AR-RFP-1403-07 round_trip_problems=0
live: ok
live_ai: model=qwen3:8b think=off format=json generated=4 parse_errors=0 grounded=4/4 invented_ids=0 accepted=2/4
live_judge: ai rule=2/4 llm=3/4 combined=2/4 feedback_templates llm=2/2
  rfp_summary AR-RFP-1403-07 fa: accepted mentioned=3/4 rule=18 llm=18
  feedback PRP-B fa: accepted mentioned=2/2 rule=20 llm=20
  rfp_summary AR-RFP-1403-07 en: rejected mentioned=2/4 rule=16 llm=15
  feedback PRP-B en: rejected mentioned=1/2 rule=15 llm=20
live_timings: generate_avg_s=5.175 tokens_avg=1226+260 total_s=31.5
checks: pytest=ok prior_steps=ok inputs_loaded=ok blueprint_valid=ok evidence_grounded=ok rfp_generated=ok rfp_accepted=ok proposals_valid=ok evaluation_matches_published=ok decision_consistent=ok feedback_accepted=ok knowledge_linked=ok negative_controls_rejected=ok csv_round_trip=ok
results_json: /home/mdhdl/Desktop/RAG/results/phase-13/rfp-check-20261123T194948Z.json
======== END PHASE 13 SUMMARY ========
```

| مورد | پیش‌بینی | نتیجهٔ واقعی |
|---|---|---|
| تعداد تست‌ها | ۱۲۰۷ + ۱۴۸ = ۱۳۵۵ | **۱۳۵۵ قبول**، ۰ خطا، ۰ ردشده، ۰ جاافتاده |
| ورودی‌ها | ۳ مسئلهٔ کلیدی، ۱۴ شکاف، ۱۵ مجری | همان |
| نامزدهای RFP | AR-ISS-024 و AR-ISS-035 از بیرون، AR-ISS-031 نه | همان؛ ۱ RFP (AR-RFP-1403-07) |
| پیش‌نویس | ۱۱ نیازمندی (۷ الزامی)، وزن ۶۰+۴۰، ۷ پیوند، ۰ مشکل | همان |
| پشتوانهٔ سند | ۱۸/۱۸ و ۲/۲؛ پیشنهادها ۲/۲ و ۴/۴ | همان در هر دو زبان |
| متن RFP | ۲۰ از ۲۰، قبول | فارسی ۲۰ و انگلیسی ۲۰، قبول (۱۱ بخش، ۱ شکاف) |
| نمرهٔ PRP-A | 78.8 | **78.8** (برابر نمرهٔ ثبت‌شده) |
| نمرهٔ PRP-B | 75.2 | **75.2** (برابر نمرهٔ ثبت‌شده) |
| تصمیم | PRP-A، سازگار | PRP-A، سازگار، فاصله 3.6 |
| بازخوردها | ۴ متن، ۲۰، قبول | هر ۴ متن ۲۰، قبول |
| پیوند دانش | ۷/۷، ۶ گره، ۶ مجری | همان |
| کنترل‌های منفی | ۷/۷، ۱۰/۱۰، ۶/۶، ۱۲/۱۲ | همان |
| CSV | ۵ فایل، ۰ مشکل | ۵ فایل، ۰ مشکل |
| متن‌های هوش مصنوعی (اختیاری) | فقط مشورت | ۴ متن، همه پشتوانه‌دار، ۰ شناسهٔ ساختگی، **۲ از ۴ قبول** |

به زبان ساده:

- **همه‌چیز طبق پیش‌بینی بود:** هر عددی که از قبل حساب کرده بودیم دقیقاً همان درآمد. سیستم فقط برای AR-ISS-024 و AR-ISS-035 سراغ شرکت بیرونی رفت و AR-ISS-031 (مسئلهٔ زمان‌بندی) را کنار گذاشت.
- **حساب نمره‌ها درست است:** PRP-A با 82×0.6 + 74×0.4 = 78.8 و PRP-B با 68×0.6 + 86×0.4 = 75.2. هر دو با نمرهٔ ثبت‌شده در سند می‌خوانند و تصمیم (PRP-A) با نمره‌ها سازگار است. PRP-B ارزان‌تر (45 میلیون تومان کمتر) و سریع‌تر (۲ هفته زودتر) بود، ولی نمرهٔ فنی پایین‌ترش باعث شد دوم شود.
- **متن‌های قالبی سالم بودند:** RFP و هر چهار بازخورد نمرهٔ کامل ۲۰ گرفتند. همهٔ ۳۵ نسخهٔ خراب (پیش‌نویس، پیشنهاد، متن RFP و بازخورد) رد شدند.
- **متن‌های هوش مصنوعی:** `qwen3:8b` چهار متن نوشت و هیچ عدد یا شناسه‌ای از خودش نساخت. دو متن فارسی قبول شدند (خلاصهٔ RFP با ۱۸ و ۱۸، بازخورد PRP-B با ۲۰ و ۲۰). دو متن انگلیسی رد شدند چون همهٔ شناسه‌های لازم را نیاورده بودند: خلاصهٔ RFP فقط ۲ از ۴ شناسه را آورد (داور قاعده‌ای ۱۶، داور مدل ۱۵) و بازخورد PRP-B فقط ۱ از ۲ (داور قاعده‌ای ۱۵، با اینکه داور مدل ۲۰ داد). حکم نهایی «قبولِ هر دو داور» است، پس نتیجه ۲ از ۴ شد. این روی RFP، نمره‌ها، تصمیم و فایل‌ها اثری ندارد؛ فقط مشورت بود.
- **زمان:** مرحلهٔ زنده حدود ۳۱.۵ ثانیه طول کشید (هر متن حدود ۵.۲ ثانیه).

فایل نتایج: `results/phase-13/rfp-check-20261123T194948Z.json`.

## خروجی‌ها

| مسیر | محتوا |
|---|---|
| `data/rfp/rfp-blueprints.json` | پیش‌نویس RFP: نیازمندی‌ها، معیارهای وزن‌دار و پیوندهای دانش |
| `data/proposals/proposal-registry.json` | پیشنهادهای ثبت‌شده و تصمیم نهایی |
| `src/rag_core/rfp/` | مدل پیش‌نویس، اعتبارسنجی، پشتوانهٔ سند، انتخاب نامزدها، ساختن متن RFP، متن هوش مصنوعی، تنظیمات، پرامپت‌ها، داوری |
| `src/rag_core/proposals/` | دفتر پیشنهادها، اعتبارسنجی، پشتوانهٔ سند، نمره‌دهی وزنی، بازخورد، پیوند دانش، CSV |
| `config/rfp.yaml` | تنظیمات فاز ۱۳ (نامزدها، حد طول RFP، مدل) |
| `config/prompts/rfp/` | عنوان بخش‌ها و دو پرامپت مشورتی (خلاصهٔ RFP و بازخورد) |
| `scripts/run_rfp_check.py` | اجرای فاز ۱۳ و بلوک خلاصه |
| `exports/rfp/` | فایل‌های CSV هر RFP (در git ثبت نمی‌شود) |
| `results/phase-13/` | فایل JSON نتایج هر اجرا (در git ثبت نمی‌شود) |
| `tests/unit/rfp/`، `tests/unit/proposals/` | تست‌های فاز ۱۳ (نشانه‌های `rfp_gen` و `proposals`) |
| `docs/phase-13/rfp-and-evaluation.md` | توضیح کامل طراحی، فرمول‌ها و محدودیت‌ها |

## محدودیت‌ها

- فقط یک پیش‌نویس RFP داریم. برای مسئلهٔ تازه‌ای که از بیرون تأمین می‌شود باید اول یک پیش‌نویس بررسی‌شده با سند منبع اضافه شود؛ سیستم برای مسئلهٔ بدون پیش‌نویس فقط می‌گوید `no_blueprint` و چیزی نمی‌سازد.
- سند فقط دو امتیاز فنی و مالی را ثبت کرده است؛ زیرمعیارها (مثلاً سازگاری با API) ثبت نشده‌اند و ساخته نمی‌شوند.
- امتیازها را ارزیاب انسانی داده است؛ سیستم فقط حساب را بازتولید و با تصمیم مقایسه می‌کند، خودش به کیفیت پیشنهاد نمره نمی‌دهد.
- متن‌های هوش مصنوعی هیچ اثری روی RFP، نمره‌ها، تصمیم یا CSV ندارند.
