// Builds armanrayan-rag-core.pptx (12 slides, Persian, right-to-left).
// Run from the kit root:  npm install -g pptxgenjs && node presentation/build_slides.js
// The numbers are the measured results of docs/final-report.md.
const path = require("path");
const pptxgen = require("pptxgenjs");

const FONT = "Vazirmatn";
const C = { ink: "1F2A44", muted: "6B7280", accent: "0F766E", light: "E6F2F0", bg: "FAFAF8", rule: "D1D5DB" };
const W = 10, M = 0.5;

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.author = "Majid Haidarasl";
pres.title = "هستهٔ RAG آفلاین آرمان‌رایان";
pres.subject = "rag-core 1.0.0";
pres.rtlMode = true;
pres.defineSlideMaster({ title: "BODY", background: { color: C.bg }, objects: [] });

const rtl = (extra) => Object.assign({ fontFace: FONT, rtlMode: true, lang: "fa-IR", align: "right", margin: 0 }, extra);

function base(title, n) {
  const s = pres.addSlide({ masterName: "BODY" });
  s.addText(title, rtl({ x: M, y: 0.35, w: W - 2 * M, h: 0.7, fontSize: 24, bold: true, color: C.ink }));
  s.addShape(pres.shapes.LINE, { x: M, y: 1.1, w: W - 2 * M, h: 0, line: { color: C.rule, width: 1 } });
  s.addText(String(n), { x: M, y: 5.2, w: 0.5, h: 0.25, fontFace: FONT, fontSize: 10, color: C.muted, margin: 0 });
  return s;
}

// Plain paragraphs with a leading dot: list bullets land on the wrong side in some right-to-left viewers.
function bullets(s, items, box) {
  const runs = items.map((t, i) => ({ text: "• " + t, options: { rtlMode: true, align: "right", breakLine: i < items.length - 1 } }));
  s.addText(runs, rtl(Object.assign({ fontSize: 18, color: C.ink, paraSpaceAfter: 10, valign: "top" }, box)));
}

function card(s, x, y, w, h, big, label) {
  s.addShape(pres.shapes.RECTANGLE, { x, y, w, h, fill: { color: C.light }, line: { color: C.light } });
  s.addText(big, { x, y: y + 0.15, w, h: h * 0.5, fontFace: FONT, fontSize: 30, bold: true, color: C.accent, align: "center", margin: 0 });
  s.addText(label, rtl({ x: x + 0.1, y: y + h * 0.58, w: w - 0.2, h: h * 0.35, fontSize: 12, color: C.ink, align: "center" }));
}

// 1 — cover
function slide01() {
  const s = pres.addSlide({ masterName: "BODY" });
  s.addShape(pres.shapes.RECTANGLE, { x: W - 0.25, y: 0, w: 0.25, h: 5.625, fill: { color: C.accent }, line: { color: C.accent } });
  s.addText("هستهٔ RAG سلسله‌مراتبی آفلاین", rtl({ x: M, y: 1.5, w: W - 1.5, h: 0.9, fontSize: 34, bold: true, color: C.ink }));
  s.addText("مطالعهٔ موردی آرمان‌رایان · نسخهٔ 1.0.0", rtl({ x: M, y: 2.45, w: W - 1.5, h: 0.5, fontSize: 18, color: C.accent }));
  s.addText("پرسش و پاسخ با منبع، ایشوها، انتقال دانش، RFP و ارزیابی — همه روی یک کامپیوتر و بدون اینترنت",
    rtl({ x: M, y: 3.2, w: W - 1.5, h: 0.8, fontSize: 14, color: C.muted }));
  s.addText("آذر ۱۴۰۵", rtl({ x: M, y: 4.6, w: W - 1.5, h: 0.4, fontSize: 13, color: C.ink }));
}

// 2 — problem
function slide02() {
  const s = base("دانش سازمان در سندها پراکنده است و نباید از سازمان بیرون برود", 2);
  bullets(s, [
    "صدها سند فارسی و انگلیسی؛ پیدا کردن جواب درست وقت می‌برد",
    "هر واحد سازمان فقط باید دانش خودش و زیرمجموعه‌اش را ببیند",
    "جواب باید منبع داشته باشد تا بشود به آن اعتماد کرد",
    "مدل زبانی محلی (Ollama) — هیچ داده‌ای به بیرون نمی‌رود",
  ], { x: M, y: 1.4, w: W - 2 * M, h: 3.2 });
}

// 3 — architecture
function slide03() {
  const s = base("از سند تا جواب داوری‌شده در پنج قدم", 3);
  const steps = ["خواندن اسناد", "نسخه و تکراری", "نمایه و جست‌وجو", "پاسخ با ارجاع", "داوری"];
  const bw = 1.55, gap = 0.27, y = 2.1;
  steps.forEach((t, i) => {
    const x = W - M - bw - i * (bw + gap);
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: bw, h: 0.9, fill: { color: i === 4 ? C.accent : C.light }, line: { color: C.accent, width: 1 } });
    s.addText(t, rtl({ x, y, w: bw, h: 0.9, fontSize: 14, bold: true, align: "center", valign: "middle", color: i === 4 ? "FFFFFF" : C.ink }));
    if (i < steps.length - 1) {
      s.addShape(pres.shapes.LINE, { x: x - gap, y: y + 0.45, w: gap, h: 0, line: { color: C.accent, width: 1.5, endArrowType: "triangle" }, flipH: true });
    }
  });
  s.addText("ingestion → knowledge → rag → qa → judging؛ کنارشان: hierarchy، issues، ike، projects، rfp، tuning و quality",
    { x: M, y: 3.5, w: W - 2 * M, h: 0.5, fontFace: FONT, fontSize: 12, color: C.muted, align: "center", margin: 0 });
  s.addText("طراحی دامنه‌محور: هر بافت یک بستهٔ پایتون با لایهٔ domain، application و infrastructure",
    rtl({ x: M, y: 4.2, w: W - 2 * M, h: 0.5, fontSize: 13, color: C.ink, align: "center" }));
}

// 4 — corpus numbers
function slide04() {
  const s = base("پیکرهٔ آزمایشی: ۵۲ سند، ۱۳۵۶ تکه، ۲۱ گره سازمانی", 4);
  const cw = 2.6, gap = 0.4, y = 1.6;
  [["60", "فایل خوانده شد (docx، doc، pdf)"], ["1356", "تکه پس از تکه‌بندی"], ["26/26", "سند به گرهٔ سازمانی وصل شد"]]
    .forEach(([big, label], i) => card(s, W - M - cw - i * (cw + gap), y, cw, 1.8, big, label));
  s.addText("۵۳ نسخه و ۱۲۱۹ تکهٔ فعال پس از حذف تکراری‌ها · ۷ ایشو و ۴ زیرایشو",
    rtl({ x: M, y: 3.8, w: W - 2 * M, h: 0.5, fontSize: 14, color: C.muted, align: "center" }));
}

// 5 — retrieval and QA
function slide05() {
  const s = base("جست‌وجو در محدودهٔ گره، با ارجاع درست در همهٔ جواب‌ها", 5);
  s.addChart(pres.charts.BAR, [{ name: "فاز ۸", labels: ["hit@5", "MRR", "واقعیت‌ها", "ارجاع"], values: [87.5, 71.9, 93.3, 100] }], {
    x: M, y: 1.3, w: 5.6, h: 3.7, barDir: "col", chartColors: [C.accent], showLegend: false, showValue: true,
    dataLabelPosition: "outEnd", dataLabelFontSize: 12, dataLabelFormatCode: "0.0", valAxisMinVal: 0, valAxisMaxVal: 100, valAxisHidden: true,
    valGridLine: { style: "none" }, catGridLine: { style: "none" }, catAxisLabelFontFace: FONT, catAxisLabelFontSize: 12,
    catAxisLabelColor: C.ink, dataLabelColor: C.ink,
  });
  bullets(s, ["درصد، روی ۱۶ پرسش مرجع", "hit@5: 0.875", "MRR: 0.719", "واقعیت‌ها: ۱۴ از ۱۵", "ارجاع درست: ۱۱ از ۱۱", "نقض محدوده در فاز ۱۴: صفر"],
    { x: 6.4, y: 1.5, w: 3.1, h: 3.5, fontSize: 15 });
}

// 6 — judge
function slide06() {
  const s = base("داور مدل به‌تنهایی سهل‌گیر بود؛ پیش‌بررسی قطعی آن را درست کرد", 6);
  s.addChart(pres.charts.BAR, [{ name: "kappa", labels: ["داور مدل", "پیش‌بررسی + داور", "داور قاعده‌ای"], values: [0.0, 0.809, 0.952] }], {
    x: M, y: 1.3, w: 5.6, h: 3.7, barDir: "col", dataLabelFormatCode: "0.000", chartColors: [C.accent], showLegend: false, showValue: true,
    dataLabelPosition: "outEnd", dataLabelFontSize: 11, valAxisMinVal: 0, valAxisMaxVal: 1, valAxisHidden: true,
    valGridLine: { style: "none" }, catGridLine: { style: "none" }, catAxisLabelFontFace: FONT, catAxisLabelFontSize: 11,
    catAxisLabelColor: C.ink, dataLabelColor: C.ink,
  });
  bullets(s, ["kappa: توافق با برچسب مرجع", "داور مدل تنها (فاز ۱۰): 0.0", "پیش‌بررسی + داور سخت‌گیر: ۳۸ از ۴۲", "جواب ناقص رد شد: ۳ از ۳"],
    { x: 6.4, y: 1.5, w: 3.1, h: 3.5, fontSize: 15 });
}

// 7 — projects and RFP
function slide07() {
  const s = base("ایشوهای کلیدی و انتخاب پیشنهاد با امتیاز وزن‌دار", 7);
  const cw = 4.2, y = 1.5;
  card(s, W - M - cw, y, cw, 1.6, "024 · 031 · 035", "سه ایشوی کلیدی AR-ISS؛ آزمون حساسیت ۱۸ از ۱۸");
  card(s, M, y, cw, 1.6, "78.8 / 75.2", "امتیاز PRP-A در برابر PRP-B");
  bullets(s, ["۱۹ از ۱۹ بستهٔ انتقال دانش ساخته شد؛ کنترل‌های منفی ۱۰۴ از ۱۰۴",
    "متن‌های رسمی مدل همیشه بازبینی انسانی می‌خواهند"], { x: M, y: 3.5, w: W - 2 * M, h: 1.3, fontSize: 14 });
}

// 8 — tests
function slide08() {
  const s = base("از ۱۴۹ تا ۱۷۱۵ تست؛ پوشش خط ۹۶٫۳٪", 8);
  s.addChart(pres.charts.BAR, [{ name: "تست‌ها", labels: ["5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "15", "16"],
    values: [149, 240, 474, 658, 788, 937, 1061, 1207, 1355, 1493, 1643, 1715] }], {
    x: M, y: 1.3, w: 6.2, h: 3.7, barDir: "col", chartColors: [C.accent], barGapWidthPct: 60,
    showLegend: false, valAxisMinVal: 0, valGridLine: { color: "E5E7EB", size: 0.5 }, catGridLine: { style: "none" },
    catAxisLabelColor: C.muted, valAxisLabelColor: C.muted, catAxisTitle: "فاز", showCatAxisTitle: true,
    catAxisTitleFontFace: FONT, catAxisTitleColor: C.muted,
  });
  bullets(s, ["پوشش خط ۹۶٫۳٪، شاخه ۸۹٫۸٪", "هیچ تستی به مدل، کارت گرافیک یا اینترنت نیاز ندارد", "۵۹٫۲۳ ثانیه برای همهٔ ۱۷۱۵ تست"],
    { x: 7.0, y: 1.5, w: 2.5, h: 3.5, fontSize: 15 });
}

// 9 — selection rule
function slide09() {
  const s = base("تنظیمات با اندازه‌گیری انتخاب می‌شوند، نه با حدس", 9);
  const head = (t) => ({ text: t, options: { bold: true, color: "FFFFFF", fill: { color: C.accent }, align: "center", fontFace: FONT } });
  const cell = (t) => ({ text: t, options: { align: "center", fontFace: FONT, color: C.ink } });
  s.addTable([
    [head("شناسهٔ ساختگی"), head("پذیرفته"), head("شناسهٔ نام‌برده"), head("گزینهٔ ai_ids")],
    [cell("0"), cell("2/4"), cell("11/18"), cell("baseline (انتخاب)")],
    [cell("1"), cell("2/4"), cell("15/18"), cell("listed_retry")],
    [cell("0"), cell("1/4"), cell("9/18"), cell("listed_guarded")],
  ], { x: M, y: 1.4, w: W - 2 * M, colW: [2.0, 2.0, 2.0, 3.0], fontSize: 15, border: { pt: 0.5, color: C.rule }, rowH: 0.5 });
  s.addText("قاعده: اول نرخ پذیرش، بعد شناسهٔ ساختگی کمتر. نمونه کوچک است (۴ متن) و در هر اجرا دوباره سنجیده می‌شود.",
    rtl({ x: M, y: 3.6, w: W - 2 * M, h: 0.8, fontSize: 14, color: C.muted }));
}

// 10 — limits
function slide10() {
  const s = base("محدودیت‌ها را می‌دانیم", 10);
  bullets(s, [
    "پیکره کوچک و ساختگی است؛ روی دادهٔ واقعی باید دوباره سنجید",
    "مجموعه‌های مرجع کوچک‌اند؛ یک مورد عدد را زیاد جابه‌جا می‌کند",
    "qwen3:8b گاهی شناسه‌ها را کامل نمی‌نویسد",
    "PDF اسکن‌شده با عدد فارسی به OCR یا بازبینی نیاز دارد",
    "رابط گرافیکی ساخته نشد؛ کار با اسکریپت و تنظیمات است",
  ], { x: M, y: 1.4, w: W - 2 * M, h: 3.4 });
}

// 11 — run it
function slide11() {
  const s = base("با یک فرمان: نصب، ۱۶ فاز بررسی و خلاصهٔ نهایی", 11);
  s.addShape(pres.shapes.RECTANGLE, { x: M, y: 1.4, w: W - 2 * M, h: 1.5, fill: { color: C.ink }, line: { color: C.ink } });
  s.addText([
    { text: "ollama pull bge-m3 && ollama pull qwen3:8b", options: { breakLine: true } },
    { text: "cd ~/Desktop/RAG", options: { breakLine: true } },
    { text: "bash scripts/setup_and_test.sh" },
  ], { x: M + 0.3, y: 1.5, w: W - 2 * M - 0.6, h: 1.3, fontFace: "DejaVu Sans Mono", fontSize: 15, color: "FFFFFF", align: "left", margin: 0, valign: "middle" });
  bullets(s, ["آخرین بلوک: PHASE 16 SUMMARY با status: PASS", "Ubuntu، یا Windows 11 با Ubuntu روی WSL 2",
    "راهنما: docs/user-guide.md · شواهد: eval/evidence/README.md"], { x: M, y: 3.2, w: W - 2 * M, h: 1.6, fontSize: 14 });
}

// 12 — next steps
function slide12() {
  const s = base("قدم بعدی: دادهٔ واقعی یک واحد سازمان", 12);
  bullets(s, ["اجرا روی اسناد واقعی و ساختن مجموعهٔ مرجع بزرگ‌تر", "OCR برای PDFهای اسکن‌شده",
    "یک رابط وب ساده برای پرسش و بازبینی", "سنجش مدل‌های دیگر با همان قاعدهٔ انتخاب"], { x: M, y: 1.4, w: W - 2 * M - 0.5, h: 3.0 });
  s.addShape(pres.shapes.RECTANGLE, { x: W - 0.25, y: 0, w: 0.25, h: 5.625, fill: { color: C.accent }, line: { color: C.accent } });
}

[slide01, slide02, slide03, slide04, slide05, slide06, slide07, slide08, slide09, slide10, slide11, slide12].forEach((f) => f());
pres.writeFile({ fileName: path.join(__dirname, "armanrayan-rag-core.pptx") });
