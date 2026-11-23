# راهنمای کاربر — نصب و اجرا روی Ubuntu و Windows 11

این راهنما برای کسی است که می‌خواهد سیستم را روی کامپیوتر خودش نصب و اجرا کند. دو راه پشتیبانی می‌شود:

- **Ubuntu** (مثلاً Ubuntu 24.04 LTS) — مستقیم.
- **Windows 11** — با **WSL 2** و Ubuntu داخل آن. Ollama روی خود ویندوز نصب می‌شود.

## ۱. سخت‌افزار لازم

| مورد | حداقل |
|---|---|
| پایتون | 3.12 یا تازه‌تر (Ubuntu 24.04 همین را دارد) |
| حافظه | ۱۶ گیگابایت |
| کارت گرافیک | برای مرحله‌های زنده حدود ۸ گیگابایت حافظهٔ گرافیکی (NVIDIA) |
| فضای دیسک | حدود ۱۵ گیگابایت (بیشترش مدل‌ها) |

تست‌های واحد و بررسی‌های آفلاین به کارت گرافیک و Ollama نیاز ندارند؛ فقط مرحله‌های «زنده» از مدل استفاده می‌کنند.

## ۲. Ubuntu

### بسته‌های سیستم

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git unzip curl libreoffice-writer poppler-utils
```

- `libreoffice-writer` فایل‌های قدیمی `.doc` را به `.docx` تبدیل می‌کند (فاز ۴).
- `poppler-utils` برنامهٔ `pdftotext` را می‌دهد که متن فارسی PDF را درست می‌خواند.

### Ollama و مدل‌ها

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull bge-m3
ollama pull qwen3:8b
ollama pull qwen2.5vl:3b
ollama list
```

- `bge-m3` متن را به بردار تبدیل می‌کند (جست‌وجوی معنایی، فارسی و انگلیسی).
- `qwen3:8b` پاسخ، خلاصه، RFP و داوری را تولید می‌کند.
- `qwen2.5vl:3b` مدل تصویر است که در سنجش فاز ۲ برای جدول و نمودار به کار رفت؛ اسکریپت اجرای کامل به آن نیازی ندارد.
- Ollama باید روی `http://localhost:11434` در دسترس باشد. اگر سرویس بالا نیست: `sudo systemctl start ollama`.

### گرفتن پروژه

```bash
mkdir -p ~/Desktop/RAG
cd ~/Desktop/RAG
unzip -o ~/Downloads/rag-phase-16.zip
```

یا با git: `git clone https://github.com/Majid-Haidarasl/RAG.git` و بعد `cd RAG/rag-phase-16`.

`~/Desktop/RAG` فقط مثال است. اگر ریپو را جای دیگری کلون کرده‌اید، در همهٔ دستورهای این راهنما به‌جای آن
پوشه‌ای را بنویسید که ریپو را در آن کلون کرده‌اید.

بعد بروید سراغ بخش ۴ (اجرا).

## ۳. Windows 11

اسکریپت اصلی (`scripts/setup_and_test.sh`) یک اسکریپت bash برای لینوکس است. روی ویندوز آن را **داخل Ubuntu روی WSL 2**
اجرا کنید. **Git Bash کافی نیست:** اسکریپت `python3` را صدا می‌زند (در ویندوز معمولاً `py` یا `python` است و
`python3` فروشگاه ویندوز را باز می‌کند) و محیط مجازی را از `.venv/bin/activate` فعال می‌کند، در حالی که پایتون ویندوز
آن را در `.venv\Scripts` می‌سازد؛ پس در Git Bash اسکریپت همان اول می‌ایستد. اجرای مستقیم با پایتون ویندوز هم آزموده نشده است.

پس در ویندوز، پایتون، Git، LibreOffice و poppler (`pdftotext`) **داخل Ubuntu** و با `apt` نصب می‌شوند و فقط Ollama
روی خود ویندوز است.

### قدم ۱ — نصب WSL و Ubuntu

PowerShell را با «Run as administrator» باز کنید:

```powershell
wsl --install -d Ubuntu-24.04
```

کامپیوتر را دوباره راه‌اندازی کنید، Ubuntu را از منوی Start باز کنید و یک نام کاربری و رمز بسازید.
درایور تازهٔ NVIDIA ویندوز کافی است؛ داخل Ubuntu درایور جدا نصب نکنید.

### قدم ۲ — Ollama برای ویندوز و مدل‌ها

برنامهٔ نصب را از `https://ollama.com/download/windows` بگیرید و نصب کنید. بعد در PowerShell:

```powershell
ollama pull bge-m3
ollama pull qwen3:8b
ollama pull qwen2.5vl:3b
ollama list
```

### قدم ۳ — دیدن Ollama از داخل Ubuntu

تنظیمات پروژه فقط به `http://localhost:11434` وصل می‌شود. برای این‌که `localhost` داخل WSL همان ویندوز باشد،
حالت شبکهٔ «mirrored» را روشن کنید. فایل `%UserProfile%\.wslconfig` را (مثلاً با Notepad) بسازید:

```ini
[wsl2]
networkingMode=mirrored
```

بعد در PowerShell `wsl --shutdown` بزنید و Ubuntu را دوباره باز کنید. آزمایش، داخل Ubuntu:

```bash
curl http://localhost:11434/api/version
```

باید نسخهٔ Ollama را نشان دهد. راه دیگر این است که Ollama را به‌جای ویندوز داخل خود Ubuntu نصب کنید
(همان فرمان‌های بخش ۲)؛ کارت گرافیک از داخل WSL هم در دسترس است.

### قدم ۴ — بسته‌ها داخل Ubuntu

داخل پنجرهٔ Ubuntu:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git unzip curl libreoffice-writer poppler-utils
```

### قدم ۵ — گرفتن پروژه

پروژه را در پوشهٔ خانهٔ لینوکس بگذارید، نه در `/mnt/c/...`؛ روی درایو ویندوز همه چیز چند برابر کندتر است.

```bash
mkdir -p ~/Desktop/RAG
cd ~/Desktop/RAG
unzip -o /mnt/c/Users/<نام-کاربری-ویندوز>/Downloads/rag-phase-16.zip
```

پوشهٔ پروژه از File Explorer ویندوز هم با نشانی `\\wsl$\Ubuntu-24.04\home\<نام-کاربری>\Desktop\RAG` دیده می‌شود.

## ۴. اجرای کامل (Ubuntu و WSL یکی است)

```bash
cd ~/Desktop/RAG
bash scripts/setup_and_test.sh 2>&1 | tee run.log
```

اسکریپت به ترتیب این کارها را می‌کند:

1. محیط مجازی `.venv` را می‌سازد و پروژه را با ابزارهای توسعه نصب می‌کند (بار اول اینترنت لازم است).
2. همهٔ تست‌های واحد را با اندازه‌گیری پوشش کد اجرا می‌کند.
3. بررسی فاز ۴ تا ۱۶ را یکی‌یکی اجرا می‌کند؛ هر کدام یک بلوک `PHASE N SUMMARY` چاپ می‌کند.
4. آخرین بلوک `PHASE 16 SUMMARY` است. اگر `status: PASS` باشد، همه چیز درست است.

اجرای کامل چند دقیقه طول می‌کشد و بیشترِ زمان مال مرحله‌های زنده است. بدون Ollama کوتاه‌تر است و مرحله‌های زنده
با `skipped` گزارش می‌شوند.

## ۵. خواندن نتیجه

- خط `checks:` در هر بلوک نشان می‌دهد کدام بررسی `ok` و کدام `FAIL` شد.
- خط `results_json:` مسیر فایل کامل نتیجهٔ همان فاز است (زیر `results/` یا `eval/results/`).
- فهرست همهٔ فایل‌های نتیجه و این‌که هر عدد گزارش از کجا می‌آید در `eval/evidence/README.md` است.
- گزارش پوشش کد: `results/phase-15/htmlcov/index.html`. در Ubuntu با `xdg-open` و در WSL با
  `explorer.exe "$(wslpath -w results/phase-15/htmlcov/index.html)"` باز می‌شود.

## ۶. اجرای یک بخش به‌تنهایی

بعد از اجرای اول، محیط مجازی آماده است:

```bash
cd ~/Desktop/RAG
source .venv/bin/activate
python -m pytest tests/unit/qa -q          # فقط تست‌های یک بخش
python -m pytest -m release -q             # فقط تست‌های فاز ۱۶
python scripts/run_rag_demo.py --no-live   # جست‌وجو و پاسخ بدون مدل
python scripts/run_rag_demo.py             # با Ollama
python scripts/run_release_check.py        # بررسی انتشار
```

هر اسکریپت با `--help` گزینه‌هایش را نشان می‌دهد.

## ۷. تنظیمات

همهٔ تنظیمات در پوشهٔ `config/` است و با ویرایش متن عوض می‌شود:

| فایل | چه چیزی را تنظیم می‌کند |
|---|---|
| `config/rag.yaml` | مدل‌ها، آدرس Ollama، اندازهٔ تکه‌ها و جست‌وجو |
| `config/judge.yaml` | داور، معیارها و حد قبولی |
| `config/eval.yaml` | مجموعهٔ مرجع و نسخهٔ انتخاب‌شدهٔ هر پرامپت |
| `config/transfer.yaml`، `config/projects.yaml`، `config/rfp.yaml` | انتقال دانش، پروژه‌ها و RFP |
| `config/quality.yaml`، `config/release.yaml` | حد پوشش کد و بررسی انتشار |

## ۸. مشکل‌های رایج

| نشانه | راه‌حل |
|---|---|
| `python3 not found` یا `Python 3.12+ required` | `sudo apt install -y python3 python3-venv` و دوباره اجرا |
| `python3 -m venv failed` | `sudo apt install -y python3-venv` |
| `pip install -e .[dev] failed` | اتصال اینترنت را بررسی کنید؛ گزارش در `/tmp/rag-phase-16-pip.log` |
| `live: skipped` در خلاصه‌ها | Ollama بالا نیست یا مدل‌ها نصب نیستند؛ `ollama list` و `curl http://localhost:11434/api/version` |
| در WSL: Ollama ویندوز دیده نمی‌شود | حالت mirrored در `.wslconfig` (بخش ۳، قدم ۳) و `wsl --shutdown` |
| خطای تبدیل `.doc` | `sudo apt install -y libreoffice-writer` |
| `poppler (pdftotext) is not installed` | `sudo apt install -y poppler-utils` |
| حافظهٔ گرافیکی کم | برنامه‌های دیگری که از کارت استفاده می‌کنند را ببندید؛ `nvidia-smi` |
| در WSL همه چیز کند است | پروژه را از `/mnt/c/...` به پوشهٔ خانهٔ لینوکس (`~`) ببرید |

برای پاک‌کردن همه چیز و شروع دوباره: پوشه‌های `.venv`، `.rag-index`، `results` و `exports` را پاک کنید
و اسکریپت را دوباره اجرا کنید.

## ۹. سیستمی که عددهای گزارش روی آن اندازه‌گیری شد

عددهای `docs/final-report.md` روی سیستم مرجع اندازه‌گیری شده‌اند (Fedora Linux، Python 3.15.2، Ollama 0.40.17؛
مشخصات کامل در بخش ۲ همان گزارش). روی سیستم دیگر عددهای زمان فرق می‌کند؛ عددهای کیفیت باید نزدیک بمانند.
