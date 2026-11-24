<div dir="rtl">

# اسلایدها

| فایل | محتوا |
|---|---|
| `armanrayan-rag-core.pptx` | ۱۲ اسلاید فارسی برای معرفی پروژه (حدود ۱۵ دقیقه) |
| `build_slides.js` | منبع اسلایدها؛ هر تغییر را این‌جا بدهید و فایل را دوباره بسازید |
| `demo-script.md` | متن دموی زنده، قدم‌به‌قدم |

فونت اسلایدها `Vazirmatn` است. اگر روی سیستم نصب نباشد، نمایش‌دهنده یک فونت دیگر جایش می‌گذارد و ممکن است
فاصله‌ها کمی عوض شوند. فونت رایگان است و از github.com/rastikerdar/vazirmatn گرفته می‌شود.

ساختن دوبارهٔ فایل (به Node.js نیاز دارد). در Ubuntu یا WSL:

</div>

```bash
sudo apt install -y nodejs npm
sudo npm install -g pptxgenjs
node presentation/build_slides.js
```

<div dir="rtl">


در Windows 11 می‌شود Node.js را از nodejs.org نصب کرد و همان دو فرمان آخر را در PowerShell زد
(`npm install -g pptxgenjs` بدون `sudo`).

عددهای اسلایدها همان عددهای `docs/final-report.md` هستند؛ اگر گزارش عوض شد، `build_slides.js` را هم به‌روز کنید.

</div>
