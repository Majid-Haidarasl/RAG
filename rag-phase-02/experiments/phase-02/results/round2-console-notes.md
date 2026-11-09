# Round 2 console notes (transcribed; no raw files were sent)

These two runs were reported by the user as console summary blocks only. The numbers below are transcribed as reported. Nothing is estimated.

## 20261109-190709: offline LLM run (C-17)

- Kit 0.1.0, LLM stage only (EMB and LVM not run)
- Run on the same PC (Ubuntu 24.04.5, RTX 3060 12 GB, Ollama 0.40.2) with the **internet disconnected**
- LLM calls 86/86 ok, 0 errors, 57.4 tok/s
- Quality scores identical to run 20261109-184242
- Verdict: C-17 (offline operation) passes for the LLM stage

## 20261109-192721: VRAM co-residency (kit 0.2.0, `--only vram`)

| Snapshot | /api/ps | nvidia-smi used | Flags |
|---|---|---|---|
| Empty GPU | — | 587 MiB | — |
| embed + llm | qwen3:8b 6004 MB + bge-m3 633 MB | 7496 MiB | fully on GPU, no offload |
| embed + llm + lvm | qwen2.5vl:3b 2429 MB + qwen3:8b 6004 MB + bge-m3 633 MB | 11347 MiB | CPU-OFFLOAD = ['qwen2.5vl:3b'] |

Peak co-resident: 11351 MiB.
