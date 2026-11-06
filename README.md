# Weight-space programming experiments

A task-based monorepo for exploring what can be built by writing neural-network parameters directly, without gradient descent or an optimizer.

These are research experiments. Supplied knowledge, memorization, generalization, architecture changes, and failures are reported separately.

## Tasks

| Task | Current result | Evidence |
| --- | --- | --- |
| [ABAP](tasks/abap/README.md) | 18/25 correct in a small, unblinded static review; random controls 0/25. Includes 7 supplied-answer recall cases. **Not an expert ABAP model.** | [Same-problem comparison](tasks/abap/COMPARISON.md) |

## Layout

```text
tasks/
  abap/
    task.json          # Objective, method, metrics, limitations
    README.md          # Setup and reproduction
    COMPARISON.md      # Random and edited answers to identical problems
    model/             # Runnable selected model and release-weight manifest
    experiments/       # Sources, reference data, raw outputs, historical failures
scripts/
  validate.py          # Lightweight repository and evidence checks
```

Add each future task as `tasks/<task-id>/`, with its own model, evaluation, and task manifest. Keep task-specific knowledge and results inside that task. Only move code into a shared package after multiple tasks actually need it.

## Setup

Python 3.11 was used for the recorded runs. Apple MPS was used for inference; CPU fallback is available. Reconstructing the 0.8B random foundation requires several GB of memory.

```sh
uv venv .venv --python 3.11
uv pip install --python .venv/bin/python -r requirements.lock.txt
.venv/bin/python tasks/abap/model/download_weights.py
.venv/bin/python tasks/abap/model/run.py "Explain empty FOR ALL ENTRIES in ABAP."
python3 scripts/validate.py
```

The 42 MiB selected weight patch is distributed through the [ABAP v0.1.0 release](https://github.com/allthingssecurity/weight_space_programming/releases/tag/abap-v0.1.0). The downloader verifies its SHA-256. Large generated model files are excluded from Git.

## Provenance

Inspired by [Weight-Space Programming](https://rikiyat.github.io/blog/weight-space-programming/). The ABAP experiments reuse the architecture configuration and tokenizer of [Qwen3.5-0.8B](https://huggingface.co/Qwen/Qwen3.5-0.8B), but initialize the neural weights randomly. Later experiments explicitly encode hand-authored reference answers and concept features. They are **not zero-data learning**.

No license is currently specified for this repository's original code and generated artifacts. Third-party models, configurations, tokenizers, and libraries retain their respective upstream terms.
