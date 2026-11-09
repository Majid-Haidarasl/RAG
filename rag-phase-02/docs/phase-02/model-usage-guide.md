# Phase 2: How to Use the Models

Status: v1.1, updated with run `20261109-184242` and the round-2 runs `20261109-190709` (offline), `20261109-191910` (LLM, kit 0.2.0) and `20261109-192721` (VRAM) (Ollama 0.40.2). Phase 2 output "how to use the models" (spec 8.2, phase 2 in section 21). Metric links: C-17 (offline operation), C-18 (small-model management).
Values marked *measured* come from these runs. No projections remain.

## 1. Runtime

All models run locally through **Ollama** on the target PC: Ubuntu, i5-12400F, 16 GB RAM, RTX 3060 12 GB.

| Item | Value |
|---|---|
| Endpoint | `http://localhost:11434`. Keep it bound to localhost (the default). Do not expose it with `OLLAMA_HOST=0.0.0.0`. |
| Network | Needed only once, for `ollama pull`. Runtime is offline: run `20261109-190709` ran 86/86 LLM calls with the internet disconnected (C-17, LLM stage). |
| Service | `sudo systemctl start ollama`, `systemctl status ollama`, `journalctl -u ollama -f` |
| Model files | `/usr/share/ollama/.ollama/models` (system service) or `~/.ollama/models` (user) |

| Role | Ollama name | Size on disk | Max context | Context used by the project |
|---|---|---|---|---|
| Embedding | `bge-m3:latest` (566.70M, F16) | 1.16 GB | 8,192 tokens | Set `options.num_ctx: 8192` explicitly. Ollama loaded it with 4,096 by default. |
| LLM | `qwen3:8b` (8.2B, Q4_K_M) | 5.23 GB | 40,960 tokens | `num_ctx` 8,192 |
| LVM | `qwen2.5vl:3b` (3.8B, Q4_K_M) | 3.2 GB | 128K tokens | `num_ctx` 8,192; one image ≈ 1,360 prompt tokens (measured) |

## 2. API calls used by the project

| Purpose | Endpoint | Key fields |
|---|---|---|
| Embeddings | `POST /api/embed` | `model`, `input` (string or list, batch it), `keep_alive` |
| Chat / generation | `POST /api/chat` | `model`, `messages`, `stream`, `think`, `format`, `options`, `keep_alive` |
| Vision | `POST /api/chat` | message `images: [base64]` |
| Loaded models and VRAM | `GET /api/ps` | `size`, `size_vram`, `context_length` |
| Model metadata | `POST /api/show` | `model_info.*.context_length`, `capabilities` |
| Unload | `/api/generate` or `/api/embed` | `keep_alive: 0` |

Minimal examples:

```bash
curl -s localhost:11434/api/embed -d '{"model":"bge-m3","input":["مرخصی استحقاقی سالانه"]}' | head -c 200
curl -s localhost:11434/api/chat -d '{"model":"qwen3:8b","think":false,"stream":false,
  "messages":[{"role":"user","content":"Say OK"}],"options":{"num_ctx":8192}}'
curl -s localhost:11434/api/ps
```

`/api/embed` returns L2-normalised vectors. Cosine similarity is therefore the same as the dot product.

## 3. Generation parameters (project defaults)

| Parameter | Default | Why |
|---|---|---|
| `num_ctx` | 8192 | Ollama's default context depends on the version and is often 4096. A 4096 window silently truncates long RAG prompts, so always set it. |
| `temperature` | 0.2 for QA, judge and extraction; 0.7 only for stability tests | Low variance for grounded answers |
| `top_p` | 0.9 | |
| `seed` | 42 | Repeatable runs. Not guaranteed bit-identical across Ollama versions. |
| `num_predict` | 1024 with think off, **4096** with think on (kit 0.2.1) | Caps runtime. Hitting the cap shows up as `done_reason = length`. 2048 was too low once (run 191910). |
| `format` | **JSON schema by default for structured output** | Round 2 (prompt 1.1.0): schema mode was 1.00 valid with domain recall 0.94. Prompt-only was 0.83 / 0.83 and produced one malformed JSON. |
| `keep_alive` | `10m` | Avoids reloading the model between calls. `0` unloads it. |

## 4. qwen3 thinking mode

- **API switch:** `"think": true|false` on `/api/chat` (Ollama ≥ 0.9). With `true`, the reasoning arrives in `message.thinking` and the answer in `message.content`.
- **Soft switch:** add `/think` or `/no_think` at the end of the user turn. Older servers return the reasoning inline as `<think>…</think>`. The kit strips these blocks before scoring. `strip_think()` must stay in the production LLM adapter too.
- **Project rule (decided in Phase 2):** thinking is **off by default** for every task type. In run `20261109-184242`, think-on gave the same quality on 11 of 12 paired cases and fixed one over-cautious refusal (FA-18). It costs 3–7× the wall time:
  - first answer token p50: 5.94 s with think on vs 0.34 s with think off
  - wall p50: 7.53 s vs 1.36 s
- **Retry with `think: true`** only when:
  - the think-off answer is `INSUFFICIENT_CONTEXT` although retrieval returned a high-scoring chunk (FA-18; reproduced in round 2).

  For a JSON output that fails validation, retry with **think off + schema `format`**, not think on. Log both attempts.
- Thinking tokens count toward `num_predict`. Measured mean: 506 output tokens per think-on call, 1,405 thinking characters.
- In run 191910, one English decomposition with think on used all 2,048 tokens while still thinking (8,596 characters). It returned no answer and took 37.4 s, versus 9.8 s and valid output with think off.
- Rule: use `num_predict` ≥ 4096 for think-on calls. If `done_reason = length` with an empty answer, fall back to think off + schema instead of raising the budget again.
- Do not use think on for decomposition.
- Measured decode speed: 57.8 tok/s with think off, 56.7 tok/s with think on.

## 5. VRAM budget (RTX 3060 12 GB)

| Item | Value | Source |
|---|---|---|
| Desktop (Xorg, GNOME, v2rayN) | 490 MiB | measured, nvidia-smi before the run |
| bge-m3 (ctx 4096) | 633 MB `/api/ps`; +832 MiB nvidia-smi | measured |
| qwen3:8b Q4_K_M, ctx 8192 | 6,004 MB `/api/ps`, all on GPU; 6,711 MiB total nvidia-smi | measured |
| qwen2.5vl:3b, ctx 8192 | 2,997 MB alone in run 184242; 2,429 MB on GPU when co-loaded, partly on the CPU | measured |
| **Embedding + LLM resident** | **7,496 MiB** in nvidia-smi (empty GPU 587); qwen3 6,004 MB + bge-m3 633 MB, no offload | measured, run `20261109-192721` |
| All three models | **11,347 MiB** (peak 11,351), with **qwen2.5vl:3b partly on the CPU** | measured, run `20261109-192721`; all three do **not** fit cleanly |

**Residency plan.**
- Keep bge-m3 and qwen3:8b resident during work sessions (`keep_alive: 30m`).
- Load the LVM only for batch ingestion of visual documents, then unload it (`keep_alive: 0`).
- Server settings, via `systemctl edit ollama` under `[Service] Environment=`:
  - `OLLAMA_MAX_LOADED_MODELS=2`
  - `OLLAMA_KEEP_ALIVE=30m`
  - optionally `OLLAMA_FLASH_ATTENTION=1`
  - optionally `OLLAMA_KV_CACHE_TYPE=q8_0`
- Re-run `--only vram` after changing any of these.

**Unloading is asynchronous.** A `keep_alive: 0` request returns before the memory is freed, and Ollama 0.40.2 can hold more than one runner of the same model. Always verify with `/api/ps` (`Ollama.unload()` in `common.py` does this), or a "free" GPU may still hold a model. If an operation needs memory that is not free, Ollama silently puts part of a model on the CPU. Check `size_vram < size` in `/api/ps`, or the PROCESSOR column of `ollama ps`.

## 6. How the code uses the models (Phase 3+ contract)

In DDD terms, models sit behind ports in the Model & Prompt context. Domain code never calls Ollama directly.

| Port | Method | Adapter |
|---|---|---|
| `EmbeddingPort` | `embed(texts) -> list[vector]` | `OllamaEmbeddingAdapter` |
| `LlmPort` | `complete(prompt_id, version, variables, schema?, think?) -> LlmResult` (text, parsed JSON, tokens, latency) | `OllamaLlmAdapter` |
| `LvmPort` | `read(image, task_prompt) -> LvmResult` | `OllamaLvmAdapter` |

Unit tests use deterministic fakes for these ports (Phase 1 unit-test policy). `experiments/phase-02/common.py` is the prototype adapter: retries, timeouts, think-mode fallback, `<think>` stripping and JSON extraction. `tools/mock_ollama.py` is the prototype fake server.

## 7. Troubleshooting

| Symptom | Fix |
|---|---|
| `connection refused` | `sudo systemctl start ollama` |
| `model not found` | `ollama pull <name>`, then check `ollama list` |
| Same model listed twice in `/api/ps` / `ollama ps` | Unload until it disappears: `curl localhost:11434/api/generate -d '{"model":"qwen2.5vl:3b","keep_alive":0}'` (repeat), or `sudo systemctl restart ollama` |
| Very low tokens/s (< 10) | Model is partly on CPU. Check `ollama ps` (PROCESSOR column) and free VRAM. |
| Empty answer with think on | Thinking used up `num_predict`. Raise it or turn think off. |
| `HTTP 400 … think` | Old Ollama. The kit falls back to `/no_think` automatically. Upgrading is recommended. |
| Garbled Persian in terminal | Use a UTF-8 locale: `export LANG=C.UTF-8`. |
