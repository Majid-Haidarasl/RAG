# Phase 2 — Offline Models & Technical Baseline (kit 0.2.1 + results)

Offline hierarchical RAG student project · case study **ArmanRayan IT** · GitHub issue #2.

## راهنمای سریع (فارسی)

این بسته روی اوبونتوی خودت اجرا می‌شود و فقط به Ollama لوکال (`http://localhost:11434`) و سه مدل نصب‌شده نیاز دارد: `qwen3:8b`، `qwen2.5vl:3b` و `bge-m3`. اینترنت لازم نیست و هیچ کتابخانه‌ی جانبی پایتون هم لازم نیست.

```bash
cd ~/Downloads                      # هر جایی که zip را گذاشتی
unzip rag-phase-02-kit.zip
cd rag-phase-02
bash setup.sh                       # تست واحد + بررسی Ollama، مدل‌ها و GPU
python3 experiments/phase-02/run_all.py --quick    # تست سریع، حدود ۳ تا ۵ دقیقه
python3 experiments/phase-02/run_all.py            # تست کامل، حدود ۸ تا ۱۰ دقیقه (اجرای واقعی: ۷٫۲ دقیقه)
python3 experiments/phase-02/run_all.py --only vram   # فقط سنجش VRAM هم‌زمان، حدود ۱ دقیقه
```

در پایان، یک بلوک متنی بین دو خط چاپ می‌شود. آن را کامل کپی کن و بفرست. اگر توانستی فایل zip نتایج را هم بفرست؛ مسیرش در آخر خروجی چاپ می‌شود (`experiments/phase-02/results/phase02-results-<زمان>.zip`).

نکته‌ها:
- اگر Ollama بالا نیست: `sudo systemctl start ollama`
- در حین تست کامل، برنامه‌های سنگین GPU (بازی، مرورگر با ویدیو) را ببند تا عدد VRAM و سرعت تمیز باشد.
- فقط یک مرحله: `--only embed` یا `--only llm` یا `--only lvm`. بدون مقایسه‌ی think: `--no-think`.

## Quick start (English)

```bash
unzip rag-phase-02-kit.zip && cd rag-phase-02
bash setup.sh
python3 experiments/phase-02/run_all.py --quick   # smoke run, ~3-5 min
python3 experiments/phase-02/run_all.py           # full baseline, ~8-10 min on RTX 3060 12 GB (measured 7.2)
python3 experiments/phase-02/run_all.py --only vram   # co-residency VRAM check, ~1 min
```

**Baseline result:** run `20261109-184242`. Round 2 adds the offline run `20261109-190709`, the kit 0.2.0 LLM run `20261109-191910` and the VRAM run `20261109-192721`. See `docs/phase-02/offline-model-baseline.md` (sections 1–11). Raw files are in `experiments/phase-02/results/`.
To re-score a saved run with the current scoring code, without calling any model: `python3 experiments/phase-02/tools/rescore.py experiments/phase-02/results/<run_id>`.

Options: `--host URL` (or env `OLLAMA_HOST_URL`), `--only embed|llm|lvm|vram` (repeatable), `--no-think`,
`--timeout 300`, `--keep-loaded`. Model names can be overridden with `P2_EMBED_MODEL`, `P2_LLM_MODEL`, `P2_LVM_MODEL`.

## What it measures

| Script | Model | Measures |
|---|---|---|
| `check_env.py` | — | Python, Ollama version, the 3 models (size, quantization, max context), GPU via `nvidia-smi` |
| `run_embedding_test.py` | bge-m3 | Recall@1/3/5, MRR for FA, EN, FA→EN, EN→FA, mixed; latency; embedding dimension |
| `run_llm_test.py` | qwen3:8b | Grounded Q&A + citations, refusal, TransferPackage summaries (executive/technical), sub-issue JSON, LLM judge /20; tokens/s, TTFT, latency, JSON validity; think on vs off |
| `run_lvm_test.py` | qwen2.5vl:3b | Org chart, FA/EN financial table, scanned Persian SLA page: names/numbers vs expected, latency |
| `run_all.py` | all | Runs everything. Verified unload between stages, co-residency check from an empty GPU, VRAM via `/api/ps` + `nvidia-smi`. Writes `results/<timestamp>/` + zip. |
| `tools/rescore.py` | — | Re-scores a saved run with the current scoring and gold data |

## Layout

```
README.md  setup.sh  requirements.txt
config/model-registry.yaml          # 3 candidate models (Phase 2 output)
config/prompt-registry.json         # versioned prompt templates + JSON schemas (registry 0.2.1; decompose uses schema format by default)
docs/phase-02/offline-model-baseline.md   # baseline report (filled from run 20261109-184242)
گزارش-فاز-۲.docx                    # Persian completion report
docs/phase-02/model-usage-guide.md
docs/phase-02/prompt-test-plan.md
experiments/phase-02/               # scripts, data, tests, tools/mock_ollama.py
experiments/phase-02/data/          # 24 chunks, 30 gold questions, LLM cases, 3 test images
experiments/phase-02/results/20261109-184242/   # baseline run (raw + rescored.json)
```

## Testing without Ollama

`experiments/phase-02/tools/mock_ollama.py` is a fake Ollama server used to verify the pipeline.
Its numbers mean nothing about model quality.

```bash
python3 experiments/phase-02/tools/mock_ollama.py --port 11500 &
OLLAMA_HOST_URL=http://127.0.0.1:11500 python3 experiments/phase-02/run_all.py --quick
```
