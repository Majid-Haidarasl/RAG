<div dir="rtl">

# برنامهٔ پرسش و پاسخ آرمان‌رایان

این پوشه یک رابط وب و یک واسط برنامه‌نویسی روی هستهٔ `rag-phase-16` است.
کاربر یک سؤال آزاد می‌پرسد، یک گرهٔ سازمانی را انتخاب می‌کند، و پاسخی مستند با منابع و ارجاع می‌گیرد.

## پیش‌نیازها

- پایتون نسخهٔ ۳.۱۲ یا بالاتر
- نسخهٔ پایدار `Node.js` از شاخهٔ `LTS`
- سرویس `Ollama` با مدل‌های `bge-m3` و `qwen3:8b`

راهنمای نصب فقط برای دو محیط نوشته شده است: `Ubuntu` به‌طور مستقیم، و ویندوز ۱۱ فقط از طریق `WSL 2`.

## نصب روی اوبونتو

بسته‌های پایه را نصب کنید:

</div>

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git curl
```

<div dir="rtl">

سرویس `Ollama` و مدل‌ها:

</div>

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull bge-m3
ollama pull qwen3:8b
```

<div dir="rtl">

سپس وابستگی‌های این برنامه را نصب کنید؛ از ریشهٔ مخزن:

</div>

```bash
cd rag-app/api
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cd ../web
npm install
```

<div dir="rtl">

## نصب روی ویندوز ۱۱ با زیرسیستم لینوکس

روی ویندوز ۱۱ فقط مسیر `WSL 2` با توزیع `Ubuntu` پشتیبانی می‌شود؛ `Git Bash` کافی نیست.
`Ollama` را روی خود ویندوز نصب کنید و مدل‌های `bge-m3` و `qwen3:8b` را بکشید.
داخل توزیع اوبونتوی `WSL 2` همان فرمان‌های بخش اوبونتو را برای پایتون، محیط مجازی و `npm` اجرا کنید.
اگر سرویس `Ollama` روی ویندوز به `WSL` دیده نشد، نشانی میزبان ویندوز را در پیکربندی هسته بررسی کنید.

## اجرای توسعه

برای توسعه بدون مدل واقعی، واسط را با حالت ساختگی اجرا کنید و سپس رابط را جداگانه بالا بیاورید.

در ترمینال اول:

</div>

```bash
cd rag-app/api
source .venv/bin/activate
RAG_API_MODEL_MODE=fake uvicorn rag_api.main:app --reload --app-dir src --port 8000
```

<div dir="rtl">

در ترمینال دوم:

</div>

```bash
cd rag-app/web
npm run dev
```

<div dir="rtl">

رابط توسعه معمولاً روی درگاه `5173` باز می‌شود و درخواست‌های `api` را به درگاه `8000` پروکسی می‌کند.

## اجرای نهایی با یک فرمان سرویس

ابتدا رابط را بسازید، سپس همان سرویس واسط فایل‌های ساخته‌شده را سرو کند:

</div>

```bash
cd rag-app/web
npm run build
cd ../api
source .venv/bin/activate
RAG_API_WEB_DIST=../web/dist uvicorn rag_api.main:app --app-dir src --host 0.0.0.0 --port 8000
```

<div dir="rtl">

پس از این کار، ریشهٔ نشانی `http://127.0.0.1:8000/` همان رابط وب است و مسیرهای `api` همچنان کار می‌کنند.

## سه نقطهٔ پایانی

وضعیت سامانه:

</div>

```bash
curl -s http://127.0.0.1:8000/api/health
```

<div dir="rtl">

فهرست گره‌های سازمانی:

</div>

```bash
curl -s http://127.0.0.1:8000/api/nodes
```

<div dir="rtl">

پرسش در دامنهٔ یک گره:

</div>

```bash
curl -s -X POST http://127.0.0.1:8000/api/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"سقف مرخصی ساعتی در روز و در ماه چقدر است؟","node_id":"N-ADM-HR"}'
```

<div dir="rtl">

## متغیرهای محیطی

پیشوند همهٔ متغیرها `RAG_API_` است و از تنظیمات `settings.py` خوانده می‌شود.

| متغیر | پیش‌فرض | توضیح |
|---|---|---|
| `RAG_API_CORE_ROOT` | مسیر `rag-phase-16` نسبت به مخزن | ریشهٔ هستهٔ `RAG` |
| `RAG_API_MODEL_MODE` | `ollama` | مقدار `ollama` یا `fake` |
| `RAG_API_DEFAULT_NODE` | `N-CEO` | گرهٔ پیش‌فرض فهرست |
| `RAG_API_MAX_QUESTION_CHARS` | `2000` | سقف طول سؤال |
| `RAG_API_CORS_ORIGINS` | نشانی‌های محلی `5173` | فهرست خاستگاه‌های مجاز |
| `RAG_API_WEB_DIST` | خالی | مسیر پوشهٔ ساخته‌شدهٔ وب؛ در صورت وجود `index.html` در ریشه سرو می‌شود |

## عیب‌یابی

- در اولین روشن‌شدن ممکن است پاسخ `warming_up` بیاید؛ چند ثانیه صبر کنید و دوباره بپرسید.
- اگر مدل در دسترس نباشد، کد `model_unavailable` برمی‌گردد؛ وضعیت سرویس `Ollama` و نام مدل‌ها را بررسی کنید.
- برای گرهٔ ناشناس کد `unknown_node` می‌آید؛ شناسه باید با الگوی واحدهای سازمانی یکی باشد.
- اگر درگاه `8000` یا `5173` اشغال است، فرایند قبلی را ببندید یا درگاه دیگری بدهید.

برگهٔ پذیرش دستی در فایل [`docs/acceptance.md`](docs/acceptance.md) است.

</div>
