<div dir="rtl">

# راهنمای کاربر برای نصب و اجرا روی `Ubuntu` و ویندوز ۱۱

این راهنما برای کسی است که می‌خواهد سامانه را روی رایانهٔ خودش نصب و اجرا کند. دو راه پشتیبانی می‌شود:

- روی `Ubuntu`، مثلاً نسخهٔ `Ubuntu 24.04 LTS`، پروژه به‌طور مستقیم اجرا می‌شود.
- روی `Windows 11`، پروژه داخل `Ubuntu` و روی `WSL 2` اجرا می‌شود و `Ollama` روی خود ویندوز نصب می‌شود.

## ۱. سخت‌افزار و نرم‌افزار لازم

| مورد | حداقل |
|---|---|
| پایتون | نسخهٔ ۳.۱۲ یا تازه‌تر، که در `Ubuntu 24.04` به‌طور پیش‌فرض نصب است |
| حافظه | ۱۶ گیگابایت |
| کارت گرافیک | برای مرحله‌های زنده، کارت `NVIDIA` با حدود ۸ گیگابایت حافظهٔ گرافیکی |
| فضای دیسک | حدود ۱۵ گیگابایت که بیشتر آن برای مدل‌هاست |

تست‌های واحد و بررسی‌های آفلاین به کارت گرافیک و `Ollama` نیاز ندارند؛ فقط مرحله‌های «زنده» از مدل استفاده می‌کنند.

## ۲. نصب روی `Ubuntu` به‌طور مستقیم

### بسته‌های سیستم

</div>

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git unzip curl libreoffice-writer poppler-utils
```

<div dir="rtl">

- بستهٔ `libreoffice-writer` فایل‌های قدیمی `.doc` را برای فاز ۴ به `.docx` تبدیل می‌کند.
- بستهٔ `poppler-utils` برنامهٔ `pdftotext` را نصب می‌کند که متن فارسی فایل‌های `PDF` را درست می‌خواند.

### نصب `Ollama` و مدل‌ها

</div>

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull bge-m3
ollama pull qwen3:8b
ollama pull qwen2.5vl:3b
ollama list
```

<div dir="rtl">

- مدل `bge-m3` متن را برای جست‌وجوی معنایی فارسی و انگلیسی به بردار تبدیل می‌کند.
- مدل `qwen3:8b` پاسخ، خلاصه، درخواست پیشنهاد و داوری را تولید می‌کند.
- مدل `qwen2.5vl:3b` مدل تصویر است و در سنجش فاز ۲ برای جدول و نمودار به کار رفت؛ اسکریپت اجرای کامل به آن نیازی ندارد.
- سرویس `Ollama` باید روی نشانی `http://localhost:11434` در دسترس باشد. اگر سرویس اجرا نشده است، فرمان `sudo systemctl start ollama` را اجرا کنید.

### گرفتن پروژه

</div>

```bash
mkdir -p ~/Desktop/RAG
cd ~/Desktop/RAG
unzip -o ~/Downloads/rag-phase-16.zip
```

<div dir="rtl">

راه دیگر، گرفتن پروژه با `git` است: ابتدا `git clone https://github.com/Majid-Haidarasl/RAG.git` و سپس `cd RAG/rag-phase-16` را اجرا کنید.

مسیر `~/Desktop/RAG` فقط یک مثال است. اگر مخزن را جای دیگری کلون کرده‌اید، در همهٔ دستورهای این راهنما به‌جای آن، پوشه‌ای را بنویسید که مخزن را در آن کلون کرده‌اید.

پس از این مرحله، به بخش ۴ بروید و پروژه را اجرا کنید.

## ۳. نصب روی ویندوز ۱۱ با زیرسیستم لینوکس

اسکریپت اصلی، یعنی `scripts/setup_and_test.sh`، یک اسکریپت `bash` برای لینوکس است. در ویندوز باید آن را داخل `Ubuntu` و روی `WSL 2` اجرا کنید.

ابزار `Git Bash` برای این کار کافی نیست، به دو دلیل:

- اسکریپت فرمان `python3` را صدا می‌زند، ولی در ویندوز پایتون معمولاً با نام `py` یا `python` شناخته می‌شود و `python3` فروشگاه ویندوز را باز می‌کند.
- اسکریپت محیط مجازی را از مسیر `.venv/bin/activate` فعال می‌کند، در حالی که پایتون ویندوز آن را در مسیر `.venv\Scripts` می‌سازد.

به همین دلیل، اسکریپت در `Git Bash` از همان ابتدا متوقف می‌شود. اجرای مستقیم با پایتون ویندوز هم آزموده نشده است.

پس در ویندوز، پایتون، `Git`، `LibreOffice` و `poppler` همراه با `pdftotext` داخل `Ubuntu` و با `apt` نصب می‌شوند و فقط `Ollama` روی خود ویندوز قرار می‌گیرد.

### قدم ۱: نصب `WSL` و `Ubuntu` روی ویندوز

برنامهٔ `PowerShell` را با گزینهٔ «Run as administrator» باز کنید و این فرمان را بزنید:

</div>

```powershell
wsl --install -d Ubuntu-24.04
```

<div dir="rtl">

سپس رایانه را دوباره راه‌اندازی کنید، `Ubuntu` را از منوی `Start` باز کنید و یک نام کاربری و رمز بسازید.
نصب درایور تازهٔ `NVIDIA` در ویندوز کافی است؛ داخل `Ubuntu` درایور جداگانه نصب نکنید.

### قدم ۲: نصب `Ollama` برای ویندوز و مدل‌ها

برنامهٔ نصب را از نشانی `https://ollama.com/download/windows` بگیرید و نصب کنید. سپس در `PowerShell` این فرمان‌ها را بزنید:

</div>

```powershell
ollama pull bge-m3
ollama pull qwen3:8b
ollama pull qwen2.5vl:3b
ollama list
```

<div dir="rtl">

### قدم ۳: دسترسی به `Ollama` ویندوز از داخل لینوکس

تنظیمات پروژه فقط به نشانی `http://localhost:11434` وصل می‌شود. برای این‌که `localhost` در `WSL` همان ویندوز باشد، حالت شبکهٔ `mirrored` را روشن کنید.
برای این کار، فایل `%UserProfile%\.wslconfig` را، مثلاً با `Notepad`، با این محتوا بسازید:

</div>

```ini
[wsl2]
networkingMode=mirrored
```

<div dir="rtl">

سپس در `PowerShell` فرمان `wsl --shutdown` را بزنید و `Ubuntu` را دوباره باز کنید. برای آزمایش، داخل `Ubuntu` این فرمان را اجرا کنید:

</div>

```bash
curl http://localhost:11434/api/version
```

<div dir="rtl">

خروجی این فرمان باید نسخهٔ `Ollama` را نشان دهد.
راه دیگر این است که `Ollama` را به‌جای ویندوز، داخل خود `Ubuntu` و با همان فرمان‌های بخش ۲ نصب کنید؛ کارت گرافیک از داخل `WSL` هم در دسترس است.

### قدم ۴: نصب بسته‌ها داخل محیط لینوکس

این فرمان‌ها را در پنجرهٔ `Ubuntu` بزنید:

</div>

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git unzip curl libreoffice-writer poppler-utils
```

<div dir="rtl">

### قدم ۵: گرفتن پروژه

پروژه را در پوشهٔ خانهٔ لینوکس بگذارید، نه در مسیر `/mnt/c/...`؛ روی درایو ویندوز همه‌چیز چند برابر کندتر اجرا می‌شود.

</div>

```bash
mkdir -p ~/Desktop/RAG
cd ~/Desktop/RAG
unzip -o /mnt/c/Users/<نام-کاربری-ویندوز>/Downloads/rag-phase-16.zip
```

<div dir="rtl">

پوشهٔ پروژه از `File Explorer` ویندوز هم با نشانی `\\wsl$\Ubuntu-24.04\home\<نام-کاربری>\Desktop\RAG` دیده می‌شود.

## ۴. اجرای کامل، که در `Ubuntu` و `WSL` یکسان است

</div>

```bash
cd ~/Desktop/RAG
bash scripts/setup_and_test.sh 2>&1 | tee run.log
```

<div dir="rtl">

اسکریپت این کارها را به ترتیب انجام می‌دهد:

1. محیط مجازی `.venv` را می‌سازد و پروژه را با ابزارهای توسعه نصب می‌کند؛ در اجرای اول، اینترنت لازم است.
2. همهٔ تست‌های واحد را همراه با اندازه‌گیری پوشش کد اجرا می‌کند.
3. بررسی فاز ۴ تا ۱۶ را یکی‌یکی اجرا می‌کند و هر کدام یک بلوک `PHASE N SUMMARY` چاپ می‌کند.
4. آخرین بلوک، `PHASE 16 SUMMARY` است. اگر در آن `status: PASS` آمده باشد، همه‌چیز درست است.

اجرای کامل چند دقیقه طول می‌کشد و بیشتر این زمان صرف مرحله‌های زنده می‌شود.
بدون `Ollama` اجرا کوتاه‌تر است و مرحله‌های زنده با وضعیت `skipped` گزارش می‌شوند.

## ۵. خواندن نتیجه

- خط `checks:` در هر بلوک نشان می‌دهد کدام بررسی `ok` و کدام `FAIL` شده است.
- خط `results_json:` مسیر فایل کامل نتیجهٔ همان فاز را زیر `results/` یا `eval/results/` نشان می‌دهد.
- فهرست همهٔ فایل‌های نتیجه و منبع هر عدد گزارش در فایل `eval/evidence/README.md` آمده است.
- گزارش پوشش کد در فایل `results/phase-15/htmlcov/index.html` است. این فایل در `Ubuntu` با `xdg-open` باز می‌شود و در `WSL` با فرمان `explorer.exe "$(wslpath -w results/phase-15/htmlcov/index.html)"` باز می‌شود.

## ۶. اجرای یک بخش به‌تنهایی

پس از اجرای اول، محیط مجازی آماده است و می‌توانید هر بخش را جداگانه اجرا کنید:

</div>

```bash
cd ~/Desktop/RAG
source .venv/bin/activate
python -m pytest tests/unit/qa -q          # فقط تست‌های یک بخش
python -m pytest -m release -q             # فقط تست‌های فاز ۱۶
python scripts/run_rag_demo.py --no-live   # جست‌وجو و پاسخ بدون مدل
python scripts/run_rag_demo.py             # با Ollama
python scripts/run_release_check.py        # بررسی انتشار
```

<div dir="rtl">

هر اسکریپت با گزینهٔ `--help` گزینه‌های خود را نشان می‌دهد.

## ۷. تنظیمات

همهٔ تنظیمات در پوشهٔ `config/` قرار دارد و با ویرایش متن تغییر می‌کند:

| فایل | چه چیزی را تنظیم می‌کند |
|---|---|
| `config/rag.yaml` | مدل‌ها، نشانی `Ollama`، اندازهٔ تکه‌ها و جست‌وجو |
| `config/judge.yaml` | داور، معیارها و حد قبولی |
| `config/eval.yaml` | مجموعهٔ مرجع و نسخهٔ انتخاب‌شدهٔ هر پرامپت |
| `config/transfer.yaml`، `config/projects.yaml`، `config/rfp.yaml` | انتقال دانش، پروژه‌ها و درخواست پیشنهاد |
| `config/quality.yaml`، `config/release.yaml` | حد پوشش کد و بررسی انتشار |

## ۸. مشکل‌های رایج

| نشانه | راه‌حل |
|---|---|
| `python3 not found` یا `Python 3.12+ required` | فرمان `sudo apt install -y python3 python3-venv` و اجرای دوباره |
| `python3 -m venv failed` | فرمان `sudo apt install -y python3-venv` |
| `pip install -e .[dev] failed` | اتصال اینترنت را بررسی کنید؛ گزارش در فایل `/tmp/rag-phase-16-pip.log` است |
| `live: skipped` در خلاصه‌ها | سرویس `Ollama` اجرا نشده یا مدل‌ها نصب نیستند؛ فرمان‌های `ollama list` و `curl http://localhost:11434/api/version` را بزنید |
| در `WSL`، `Ollama` ویندوز دیده نمی‌شود | حالت `mirrored` را در `.wslconfig` روشن کنید (بخش ۳، قدم ۳) و فرمان `wsl --shutdown` را بزنید |
| خطای تبدیل `.doc` | فرمان `sudo apt install -y libreoffice-writer` |
| `poppler (pdftotext) is not installed` | فرمان `sudo apt install -y poppler-utils` |
| حافظهٔ گرافیکی کم | برنامه‌های دیگری را که از کارت استفاده می‌کنند ببندید و با `nvidia-smi` وضعیت را ببینید |
| در `WSL` همه‌چیز کند است | پروژه را از `/mnt/c/...` به پوشهٔ خانهٔ لینوکس، یعنی `~`، منتقل کنید |

برای پاک‌کردن همه‌چیز و شروع دوباره، پوشه‌های `.venv`، `.rag-index`، `results` و `exports` را پاک کنید و اسکریپت را دوباره اجرا کنید.

## ۹. سیستمی که عددهای گزارش روی آن اندازه‌گیری شد

عددهای فایل `docs/final-report.md` روی سیستم مرجع با `Fedora Linux`، `Python 3.15.2` و `Ollama 0.40.17` اندازه‌گیری شده‌اند؛ مشخصات کامل در بخش ۲ همان گزارش آمده است.
روی سیستم دیگر، عددهای زمان فرق می‌کند، ولی عددهای کیفیت باید نزدیک بمانند.

</div>
