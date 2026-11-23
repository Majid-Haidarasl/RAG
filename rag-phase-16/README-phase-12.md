# فاز ۱۲ — پیگیری پروژه، پژوهش، دستاورد و شکاف، و انتخاب مسئله‌های کلیدی (نسخهٔ ۰.۱۲.۰)

هستهٔ RAG سلسله‌مراتبی آفلاین · مطالعهٔ موردی **آرمان‌رایان** · ایشو #۱۲ گیت‌هاب.

تا فاز ۱۱ سیستم جواب می‌ساخت، به جواب‌ها نمره می‌داد و هر گره یک گزارش دوره‌ای برای مدیر بالادستی‌اش می‌فرستاد. در فاز ۱۲ یک **دفتر پیگیری** به سیستم اضافه می‌شود: چه پروژه‌هایی داریم و حالشان چطور است، در این دوره چه چیزی به دست آمد (دستاورد)، با چه سختی‌هایی روبه‌رو شدیم (چالش)، چه سؤال‌هایی هنوز پژوهش لازم دارند، و کدام مسئله‌ها هنوز حل نشده‌اند. بعد سیستم با چند قاعدهٔ ساده **شکاف‌ها** را پیدا می‌کند و با یک فرمول شفاف می‌گوید مدیرعامل **اول سراغ کدام مسئله‌ها برود** و چرا.

وابستگی تازه‌ای اضافه نشده است. تست‌ها به Ollama، کارت گرافیک یا اینترنت نیاز ندارند.

## چند واژه به زبان ساده

- **دفتر پروژه (project registry):** فایل `data/projects/project-registry.json`. سه پروژه، ۱۵ رکورد و ۵ معیار کارنامه در آن ثبت شده و هر جمله‌اش به سند منبع (مثل AR-TRN-026 و AR-FIN-008) ارجاع دارد.
- **رکورد (record):** یک خط از دفتر. چهار نوع دارد: **دستاورد** (achievement)، **چالش** (challenge)، **پژوهش باز** (research) و **مسئلهٔ حل‌نشده** (unsolved issue).
- **وضعیت ادعا (state):** `recorded` یعنی ثبت و تأییدشده، `conditional` یعنی فقط با شرط درست است، `open` یعنی هنوز باز است. پژوهش‌ها همه `open` هستند و ادعای «نتیجهٔ اثبات‌شده» ندارند.
- **شرط (conditions):** محدودیت هر دستاورد یا چالش؛ مثلاً «فقط برای یک پرونده دیده شده». قاعدهٔ سیستم این است که شرط‌ها حذف نشوند.
- **کارنامه (scorecard):** چند معیار ارزیابی چرخه (مثل پوشش ارجاع یا کیفیت بازیابی) با وضعیت ثبت‌شده/مشروط/باز.
- **اعتبارسنجی (validation):** بررسی این‌که هر گره، سند و مسئله‌ای که در دفتر آمده واقعاً وجود دارد، عددها منطقی‌اند و مثلاً پروژهٔ «در خطر» واقعاً مسئلهٔ پرریسک باز دارد.
- **پشتوانهٔ سند (evidence grounding):** هر عدد و شناسه‌ای که در جمله‌های دفتر آمده باید در متن سند منبع (نسخهٔ فعال) هم باشد.
- **شکاف (gap):** چیزی که کم است یا گیر کرده؛ مثلاً زیرمسئله‌ای که منتظر زیرمسئلهٔ دیگری است، کمبود دانش، یا چالشی که هیچ مسئله‌ای دنبالش نمی‌کند.
- **وزن (weight) و امتیاز (score):** هر مسئلهٔ باز با ۹ عامل سنجیده می‌شود (اولویت، شدت، فوریت، ریسک، تعداد وابسته‌ها، مبلغ در خطر، زیرمسئله‌های مسدود، شکاف‌های باز، تعداد گره‌های درگیر). هر عامل عددی بین ۰ و ۱ است؛ ضرب در وزنش و جمع آن‌ها امتیازی بین ۰ و ۱۰۰ می‌دهد.
- **مسئلهٔ کلیدی (key issue):** حداکثر ۳ مسئلهٔ اول فهرست که امتیازشان دست‌کم ۲۵ باشد.
- **آزمون حساسیت (sensitivity):** هر وزن را ۲۰٪ کم و ۲۰٪ زیاد می‌کنیم (۹ عامل × ۲ = ۱۸ حالت) و می‌بینیم مسئلهٔ اول و مجموعهٔ کلیدی عوض می‌شوند یا نه. اگر عوض نشوند، نتیجه به انتخاب دقیق وزن‌ها حساس نیست.
- **اقدام بعدی (next action):** داخل یک مسئله، زیرمسئله‌ای که اگر انجام شود بیشترین زیرمسئلهٔ دیگر را آزاد می‌کند.
- **خلاصهٔ مسئله‌های کلیدی (brief):** متن کوتاه فارسی و انگلیسی برای مدیرعامل که با قالب ثابت از روی «واقعیت‌ها» ساخته می‌شود و داور فاز ۱۰ به آن نمره می‌دهد.
- **کنترل منفی (negative control):** دفتر یا خلاصهٔ خوب را عمداً خراب می‌کنیم؛ سیستم باید همه را رد کند.
- **لایهٔ ضدفساد (ACL):** کد کوچکی که دادهٔ بخش‌های دیگر (مسئله‌ها، چارت، IKE) را به شکل سادهٔ موردنیاز فاز ۱۲ درمی‌آورد تا بخش‌ها به هم گره نخورند.

## از فاز ۱ تا ۱۲ در یک نگاه

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
| ۱۲ | دفتر پروژه و دستاورد/چالش/پژوهش، قاعده‌های شکاف، امتیازدهی شفاف و انتخاب مسئله‌های کلیدی. |

## سیستم هدف

- Fedora Linux، پایتون 3.15.2؛
- پردازندهٔ Intel Core i5-12400F، ۱۶ گیگابایت RAM؛
- کارت گرافیک NVIDIA RTX 3060 با ۱۲ گیگابایت حافظه؛
- LibreOffice 26.8.3.1 و pdftotext 26.08.0 (برای خواندن اسناد در فازهای قبل)؛
- Ollama با `qwen3:8b` (فقط برای مرحلهٔ زندهٔ اختیاری)؛
- مسیر پروژه `~/Desktop/RAG`.

## فاز ۱۲ چه کار می‌کند (قدم‌به‌قدم)

1. **دفتر را می‌خواند** و سه پروژه را نشان می‌دهد:

   | پروژه | پیشرفت | ماندهٔ قرارداد (میلیون تومان) | مسئلهٔ اصلی | سلامت |
   |---|---|---|---|---|
   | PRJ-AZP-118 سامانه انبار آذرپخش | ۶۲٪ | ۱۲۴۰ از ۲۱۸۰ | AR-ISS-024 | در خطر (`at_risk`) |
   | PRJ-RHS-PORTAL پورتال ره‌آورد صنعت | ۷۸٪ | ۴۱۰ | AR-ISS-033 | زیر نظر (`watch`) |
   | PRJ-DSP-VISITOR اپ ویزیتور دشت‌پخش | ۴۵٪ | ۲۲۵ | AR-ISS-031 | زیر نظر (`watch`) |

   «سلامت» از روی مسئله‌های باز حساب می‌شود: مسئلهٔ باز با ریسک ۷ یا بیشتر یا زیرمسئلهٔ مسدود ← در خطر؛ فقط مسئلهٔ باز ← زیر نظر؛ هیچ مسئلهٔ باز ← روی برنامه.
2. **اعتبارسنجی می‌کند:** شناسهٔ تکراری، گره/سند/مسئلهٔ ناشناخته، دستاورد بدون سند، دستاورد یا چالش بدون شرط، پژوهشی که ادعای نتیجهٔ قطعی دارد یا برنامه‌اش ناقص است، مسئلهٔ حل‌نشده‌ای که به هیچ مسئله‌ای وصل نیست، و وضعیت پروژه‌ای که با مسئله‌هایش نمی‌خواند.
3. **پشتوانهٔ سند را می‌سنجد:** هر جمله در هر دو زبان با متن نسخهٔ فعال سندهایش مقایسه می‌شود.
4. **شکاف‌ها را پیدا می‌کند** با ۸ قاعده:

   | کد | نام | کی فعال می‌شود | شدت پیش‌فرض |
   |---|---|---|---|
   | RG | پژوهش باز | پژوهشی هنوز باز یا مشروط است (اگر به مسئلهٔ باز وصل باشد یک درجه شدیدتر) | متوسط |
   | KL | کمبود دانش | زیرمسئلهٔ فعال کمبود دانش دارد (از تحلیل فاز ۹؛ اگر مسدود باشد زیاد) | متوسط |
   | EX | بدون مجری | زیرمسئلهٔ فعال نه مجری اصلی دارد نه مجری ثبت‌شده | زیاد |
   | DEP | وابستگی مسدود | زیرمسئلهٔ مسدود منتظر زیرمسئلهٔ دیگری است که هنوز حل نشده | زیاد |
   | CH | چالش بی‌صاحب | چالشی که هیچ مسئلهٔ ثبت‌شده‌ای دنبالش نمی‌کند | متوسط |
   | SC | کارنامهٔ باز | معیار کارنامه باز است (اگر مشروط باشد: کم) | متوسط |
   | ST | حل‌نشدهٔ کهنه | رکورد حل‌نشده‌ای که همهٔ مسئله‌هایش بسته شده‌اند | کم |
   | EV | بدون سند | رکوردی که هیچ سندی ندارد | زیاد |

   هر قاعده را می‌شود در `config/projects.yaml` خاموش کرد یا شدتش را عوض کرد.
5. **مسئله‌ها را رتبه‌بندی می‌کند.** وزن‌ها (جمع = ۱): اولویت ۰٫۱۵، شدت ۰٫۱۰، فوریت ۰٫۱۵، ریسک ۰٫۱۵، وابسته‌ها ۰٫۱۰، مبلغ در خطر ۰٫۱۰، زیرمسئلهٔ مسدود ۰٫۱۰، شکاف باز ۰٫۱۰، گره‌های درگیر ۰٫۰۵. مسئلهٔ بسته (AR-ISS-034) و تکراری (AR-ISS-036 که تکرار AR-ISS-024 است) کنار گذاشته می‌شوند. برای هر مسئله سه عامل اصلی هم چاپ می‌شود تا معلوم باشد امتیاز از کجا آمده.
6. **با روش قدیم فاز ۷ مقایسه می‌کند** (`۳×فوریت + ۲×ریسک + وابسته‌ها`) و **آزمون حساسیت** را اجرا می‌کند.
7. **اقدام بعدی** را برای مسئله‌های کلیدی پیدا می‌کند: برای AR-ISS-024 زیرمسئلهٔ AR-ISS-024/HW، چون AR-ISS-024/WIN و AR-ISS-024/LEG منتظر آن هستند.
8. **خلاصهٔ مسئله‌های کلیدی** را به فارسی و انگلیسی می‌سازد و داور قاعده‌ای فاز ۱۰ به آن نمره می‌دهد.
9. **کنترل‌های منفی:** ۹ دفتر خراب (سند ساختگی، گره ناشناخته، مسئلهٔ ناشناخته، عدد غلط ۸۷ به جای ۷۸، پژوهش با ادعای نتیجه، دستاورد بدون سند، حل‌نشده بدون مسئله، دستاورد بدون شرط، وضعیت غلط) و ۶ خلاصهٔ خراب (عدد ساختگی، شناسهٔ ساختگی، حذف مسئله‌های کلیدی؛ هر کدام در دو زبان). همه باید رد شوند.
10. **خروجی CSV:** چهار فایل `projects.csv`، `records.csv`، `gaps.csv` و `priorities.csv` در `exports/project-tracking/1403-Q2/` (با UTF-8 که اکسل فارسی را درست نشان دهد) و دوباره خوانده می‌شوند تا مطمئن شویم چیزی عوض نشده.
11. **مرحلهٔ زندهٔ اختیاری:** اگر Ollama و `qwen3:8b` باشند، مدل (بدون حالت فکرکردن، با خروجی JSON) یک خلاصهٔ کوتاه و ترتیب پیشنهادی می‌دهد. این فقط **مشورت** است: عددها و شناسه‌هایش بررسی می‌شوند، داورها نمره می‌دهند، ولی رتبه‌بندی قطعی هیچ‌وقت عوض نمی‌شود.

## پیش‌نیاز مرحلهٔ زنده

```bash
ollama list
```

باید `qwen3:8b` در فهرست باشد. اگر Ollama یا مدل نباشد، مرحلهٔ زنده `skipped` گزارش می‌شود و PASS/FAIL را تغییر نمی‌دهد. مدل embedding لازم نیست.

## اجرا

روی Ubuntu، یا روی Windows 11 داخل Ubuntu در WSL 2؛ نصب در `docs/user-guide.md` آمده است.

فرض: zip در `~/Downloads/rag-phase-12.zip` است و کلون ریپو در `~/Desktop/RAG`.

```bash
cd ~/Downloads
unzip -o rag-phase-12.zip -d ~/Desktop/RAG
cd ~/Desktop/RAG
bash scripts/setup_and_test.sh
```

ترتیب اجرا: `pytest`، فازهای ۴ تا ۷، RAG فاز ۸، IKE فاز ۹، داور فاز ۱۰، انتقال فاز ۱۱ و در آخر بررسی پروژه‌ها در فاز ۱۲. آخرین بلوک بین دو خط `======== PHASE 12 SUMMARY ========` و `======== END PHASE 12 SUMMARY ========` چاپ می‌شود. عددهای بخش «نتیجه» از همین بلوک برداشته می‌شوند.

اجرای جدا:

```bash
source .venv/bin/activate
pytest -m "projects or research_gaps or prioritization"
python scripts/run_project_check.py            # همه‌چیز + خلاصهٔ هوش مصنوعی (اگر Ollama باشد)
python scripts/run_project_check.py --no-live  # فقط بخش آفلاین
```

## در خلاصه چه انتظاری داریم

این عددها از روی داده‌ها پیش‌بینی شده‌اند؛ عدد واقعی همان است که روی سیستم خودت چاپ می‌شود.

- تعداد تست‌ها: ۱۰۶۱ تست قبلی + ۱۴۶ تست تازه = **۱۲۰۷**.
- `registry: projects=3 records=15 (research=2 achievement=5 challenge=4 unsolved_issue=4) scorecard=5 problems=0`
- `evidence: projects fa=3/3 en=3/3 records fa=15/15 en=15/15`
- `gaps: total=…` — بدون کمبودهای دانش ۱۰ شکاف: RG:2، DEP:2 (AR-ISS-024/WIN و AR-ISS-024/LEG)، CH:3، SC:3. به این‌ها به تعداد زیرمسئله‌هایی که در تحلیل فاز ۹ کمبود دانش دارند شکاف KL اضافه می‌شود.
- `priorities: ranked=5 excluded=2 (AR-ISS-034:closed,AR-ISS-036:duplicate_of:AR-ISS-024) key=AR-ISS-024,AR-ISS-031,AR-ISS-035 (top 3, score >= 25)`
- امتیازها: AR-ISS-024 حدود ۷۷ تا ۸۳ (بسته به تعداد شکاف‌هایش)، AR-ISS-031 ‏33.92، AR-ISS-035 ‏30.17، AR-ISS-032 ‏28.33، AR-ISS-033 ‏17.18.
- `sensitivity: perturbations=18 top1_stable=18/18 key_set_stable=18/18`
- `legacy: phase7_order=AR-ISS-024,AR-ISS-031,AR-ISS-032,AR-ISS-035,AR-ISS-033 same_top1=True top3_overlap=2/3` — روش قدیم هم AR-ISS-024 را اول می‌گذارد؛ تفاوت در جای سوم است: روش تازه AR-ISS-035 را جلوتر از AR-ISS-032 می‌گذارد چون فوریت، وابسته و گره درگیر بیشتری دارد (هرچند ریسکش کمتر است).
- `next_action: AR-ISS-024 -> AR-ISS-024/HW unblocks=2 (AR-ISS-024/LEG,AR-ISS-024/WIN)`
- `brief fa: key=3 … rule=20 accepted` و `brief en: key=3 … rule=20 accepted`
- `negative_controls: registry rejected=9/9 brief rejected=6/6`
- `csv: files=4 dir=exports/project-tracking/1403-Q2 round_trip_problems=0`
- `live: skipped` (بدون Ollama) یا `live: ok` با دو خط `live_brief` و `live_judge`.
- `checks:` همه `ok` و `status: PASS`.

## نتیجهٔ اجرا روی سیستم من

اجرا: ۲ آذر ۱۴۰۵، حدود ساعت ۲۲:۲۷ به وقت تهران، روی Fedora Linux با پایتون 3.15.2 (همان سخت‌افزار: i5-12400F، ۱۶ گیگابایت RAM، RTX 3060 با ۱۲ گیگابایت). نتیجه: **PASS**، هر ۱۴ بررسی `ok`.

```text
======== PHASE 12 SUMMARY ========
status: PASS
kit: rag-core 0.12.0 (phase 12 projects, research gaps, prioritization)
python: 3.15.2
pytest_exit: 0
pytest_passed: 1207
pytest_failed: 0
pytest_errors: 0
pytest_skipped: 0
prior_steps: ingest=0 dedup=0 hierarchy=0 issues=0 rag=0 ike=0 judge=0 transfer=0
cycle: 1403-Q2 cutoff=1403-06-31 case=AR-ISS-024 ike_items=4 executors=15
registry: projects=3 records=15 (research=2 achievement=5 challenge=4 unsolved_issue=4) scorecard=5 problems=0
  PRJ-AZP-118: progress=62% remaining=1240 contract=2180 owner=N-CEO status=at_risk health=at_risk issues=4 open=3 blocked_sub=2 records=achievement:1,challenge:1,unsolved_issue:3
  PRJ-RHS-PORTAL: progress=78% remaining=410 contract=- owner=N-SW-WEB status=active health=watch issues=2 open=1 blocked_sub=0 records=achievement:1
  PRJ-DSP-VISITOR: progress=45% remaining=225 contract=- owner=N-SW-MOB status=active health=watch issues=1 open=1 blocked_sub=0 records=achievement:1,unsolved_issue:1
evidence: projects fa=3/3 en=3/3 records fa=15/15 en=15/15
gaps: total=14 by_rule=RG:2,KL:4,DEP:2,CH:3,SC:3 by_severity=high:4,medium:8,low:2
  KL:AR-ISS-024/LEG high issue=AR-ISS-024 lacks=1; status=blocked
  KL:AR-ISS-024/WIN high issue=AR-ISS-024 lacks=1; status=blocked
  DEP:AR-ISS-024/LEG high issue=AR-ISS-024 waits_for=AR-ISS-024/HW
  DEP:AR-ISS-024/WIN high issue=AR-ISS-024 waits_for=AR-ISS-024/HW
  RG:RES-PHOTO-TRIAGE medium state=open; people=2
  RG:RES-RETRIEVAL-EVAL medium state=open; people=2
  KL:AR-ISS-024/HW medium issue=AR-ISS-024 lacks=2; status=in_progress
  KL:AR-ISS-024/WEB medium issue=AR-ISS-024 lacks=1; status=in_progress
  CH:CHL-KEY-CAPACITY medium no registered issue tracks this challenge
  CH:CHL-LOST-CONDITIONS medium no registered issue tracks this challenge
  CH:CHL-REPAIR-NOTES medium no registered issue tracks this challenge
  SC:SC-RRQ medium state=open; research=RES-RETRIEVAL-EVAL
  SC:SC-CAP low state=conditional
  SC:SC-REP low state=conditional
priorities: ranked=5 excluded=2 (AR-ISS-034:closed,AR-ISS-036:duplicate_of:AR-ISS-024) key=AR-ISS-024,AR-ISS-031,AR-ISS-035 (top 3, score >= 25)
  1. AR-ISS-024 score=82.75 KEY top=urgency 12, risk 12, priority 11.25
  2. AR-ISS-031 score=33.92 KEY top=priority 7.5, urgency 7.5, risk 7.5
  3. AR-ISS-035 score=30.17 KEY top=priority 7.5, urgency 7.5, risk 6
  4. AR-ISS-032 score=28.33 top=risk 9, priority 7.5, urgency 6
  5. AR-ISS-033 score=17.18 top=money at stake 4.1, priority 3.75, urgency 3
sensitivity: perturbations=18 top1_stable=18/18 key_set_stable=18/18
legacy: phase7_order=AR-ISS-024,AR-ISS-031,AR-ISS-032,AR-ISS-035,AR-ISS-033 same_top1=True top3_overlap=2/3
next_action: AR-ISS-024 -> AR-ISS-024/HW unblocks=2 (AR-ISS-024/LEG,AR-ISS-024/WIN)
brief fa: key=3 gaps=6 words=175 chars=1282 rule=20 accepted
brief en: key=3 gaps=6 words=163 chars=1359 rule=20 accepted
negative_controls: registry rejected=9/9 brief rejected=6/6 by_kind=wrong_number:2/2,fabricated_id:2/2,drop_items:2/2
csv: files=4 dir=exports/project-tracking/1403-Q2 round_trip_problems=0
live: ok
live_brief: model=qwen3:8b think=off format=json generated=2 parse_errors=0 grounded=2/2 invented_ids=0 same_top=2/2 accepted=0/2
live_judge: ai rule=0/2 llm=1/2 combined=0/2 templates llm=2/2
  brief fa: rejected order=AR-ISS-024,AR-ISS-031,AR-ISS-035 mentioned=3 rule=18 llm=16
  brief en: rejected order=AR-ISS-024,AR-ISS-031,AR-ISS-035 mentioned=3 rule=18 llm=18
live_timings: brief_avg_s=4.039 judge_avg_s=2.029 tokens_avg=1006+202 total_s=16.2
checks: pytest=ok prior_steps=ok registry_loaded=ok records_built=ok registry_valid=ok evidence_grounded=ok research_gaps_tracked=ok gaps_detected=ok ranking_complete=ok key_issues_selected=ok ranking_stable=ok brief_accepted=ok negative_controls_rejected=ok csv_round_trip=ok
results_json: /home/mdhdl/Desktop/RAG/results/phase-12/project-check-20261123T185733Z.json
======== END PHASE 12 SUMMARY ========
```

| مورد | پیش‌بینی | نتیجهٔ واقعی |
|---|---|---|
| تعداد تست‌ها | ۱۲۰۷ | **۱۲۰۷ قبول**، ۰ خطا، ۰ ردشده |
| دفتر پروژه | ۰ مشکل | ۰ مشکل؛ ۳ پروژه، ۱۵ رکورد، ۵ معیار |
| پشتوانهٔ سند | ۳/۳ و ۱۵/۱۵ | ۳/۳ و ۱۵/۱۵ در هر دو زبان |
| شکاف‌ها | ۱۰ + KL | **۱۴** (KL=۴؛ زیاد ۴، متوسط ۸، کم ۲) |
| مسئله‌های کلیدی | AR-ISS-024، AR-ISS-031، AR-ISS-035 | همان سه مسئله |
| امتیاز AR-ISS-024 | ۷۷ تا ۸۳ | **82.75** (به سقف رسید) |
| حساسیت | ۱۸/۱۸ | ۱۸/۱۸ برای مسئلهٔ اول و ۱۸/۱۸ برای مجموعهٔ کلیدی |
| مقایسه با فاز ۷ | مسئلهٔ اول یکی، ۲ از ۳ | همان: same_top1=True، ۲ از ۳ |
| اقدام بعدی | AR-ISS-024/HW | AR-ISS-024/HW (آزادکردن LEG و WIN) |
| خلاصه‌ها | ۲۰ و ۲۰، قبول | ۲۰ و ۲۰، قبول |
| کنترل‌های منفی | ۹/۹ و ۶/۶ | ۹/۹ و ۶/۶ |
| CSV | ۴ فایل، ۰ مشکل | ۴ فایل، ۰ مشکل |
| خلاصهٔ هوش مصنوعی (اختیاری) | فقط مشورت | ۲ خلاصه، هر دو پشتوانه‌دار، **۰ از ۲ قبول** |

به زبان ساده:

- **شکاف‌ها ۱۴ تا شد:** تحلیل فاز ۹ برای هر چهار زیرمسئلهٔ AR-ISS-024 (HW، WIN، WEB، LEG) کمبود دانش پیدا کرد، پس ۴ شکاف KL به ۱۰ شکاف پایه اضافه شد. دو تای آن‌ها (WIN و LEG) «زیاد» هستند چون آن زیرمسئله‌ها مسدودند.
- **چرا امتیاز AR-ISS-024 برابر 82.75 شد:** روی این مسئله ۶ شکاف هست (۴ KL و ۲ DEP)؛ سقف شکاف ۵ است، پس عامل «شکاف‌های باز» کامل (۱۰ امتیاز) شد و امتیاز به بیشترین مقدار ممکن برای این مسئله رسید. فاصله‌اش با مسئلهٔ دوم (33.92) خیلی زیاد است.
- **رتبه‌بندی محکم است:** با تغییر ۲۰٪ی هر وزن، نه مسئلهٔ اول عوض شد نه مجموعهٔ سه مسئلهٔ کلیدی. روش قدیم فاز ۷ هم AR-ISS-024 را اول گذاشت؛ تنها فرق جای سوم است (روش تازه AR-ISS-035 را جلوتر از AR-ISS-032 می‌گذارد).
- **خلاصه‌های قالبی سالم بودند:** هر دو خلاصه نمرهٔ کامل ۲۰ گرفتند و داور مدل هم هر دو را قبول کرد (۲ از ۲). همهٔ ۱۵ نسخهٔ خراب رد شدند.
- **خلاصهٔ هوش مصنوعی خوب بود ولی قبول نشد:** `qwen3:8b` چیزی از خودش نساخت (هر عدد و شناسه در واقعیت‌ها بود، ۰ شناسهٔ ساختگی) و ترتیبش دقیقاً همان ترتیب سیستم بود (AR-ISS-024، AR-ISS-031، AR-ISS-035). داور قاعده‌ای به هر دو ۱۸ داد ولی قبول نکرد، یعنی جمع نمره به حد قبولی رسید اما دست‌کم یک معیار زیر حداقل خودش ماند (احتمالاً همهٔ شکاف‌های نام‌برده در واقعیت‌ها را نیاورده بود). داور مدل به نسخهٔ انگلیسی ۱۸ (قبول) و به فارسی ۱۶ داد. چون حکم نهایی «قبولِ هر دو داور» است، نتیجه ۰ از ۲ شد. این روی رتبه‌بندی و فایل‌ها اثری ندارد؛ فقط مشورت بود.
- **زمان:** مرحلهٔ زنده حدود ۱۶ ثانیه طول کشید (هر خلاصه حدود ۴ ثانیه، هر داوری حدود ۲ ثانیه).

فایل نتایج: `results/phase-12/project-check-20261123T185733Z.json`.

## خروجی‌ها

| مسیر | محتوا |
|---|---|
| `data/projects/project-registry.json` | دفتر پروژه‌ها، رکوردها و کارنامهٔ چرخهٔ 1403-Q2 |
| `src/rag_core/projects/` | مدل دفتر، اعتبارسنجی، پشتوانهٔ سند، سرویس پیگیری، خواندن JSON، CSV، تنظیمات |
| `src/rag_core/research_gaps/` | مدل شکاف، ۸ قاعده، گزارش شکاف، لایهٔ ضدفساد ورودی‌ها |
| `src/rag_core/prioritization/` | وزن‌ها، امتیازدهی، حساسیت، اقدام بعدی، خلاصهٔ کلیدی، خلاصهٔ هوش مصنوعی، داوری |
| `config/projects.yaml` | تنظیمات فاز ۱۲ (قاعده‌ها، وزن‌ها، سقف‌ها، مدل) |
| `scripts/run_project_check.py` | اجرای فاز ۱۲ و بلوک خلاصه |
| `exports/project-tracking/` | فایل‌های CSV هر چرخه (در git ثبت نمی‌شود) |
| `results/phase-12/` | فایل JSON نتایج هر اجرا (در git ثبت نمی‌شود) |
| `tests/unit/projects/`، `tests/unit/research_gaps/`، `tests/unit/prioritization/` | تست‌های فاز ۱۲ |
| `docs/phase-12/project-knowledge.md` | توضیح کامل طراحی، قاعده‌ها و محدودیت‌ها |

## محدودیت‌ها

- وزن‌ها انتخاب ما هستند، نه یک قانون سازمانی. آزمون حساسیت فقط نشان می‌دهد تغییر ۲۰٪ی نتیجه را عوض نمی‌کند؛ اگر مدیریت وزن دیگری بخواهد، باید در `config/projects.yaml` عوض شود.
- «مبلغ در خطر» فقط برای مسئلهٔ اصلی هر پروژه از ماندهٔ قرارداد می‌آید؛ برای مسئله‌های دیگر فقط مبلغ تصمیم ثبت‌شده حساب می‌شود.
- کمبودهای دانش فقط برای زیرمسئله‌های AR-ISS-024 از تحلیل فاز ۹ می‌آیند.
- پژوهش‌ها فقط پرسش و برنامه‌اند؛ هیچ نتیجه‌ای را ثابت‌شده اعلام نمی‌کنند.
- خلاصهٔ هوش مصنوعی هیچ اثری روی رتبه‌بندی، دفتر یا CSV ندارد.
