# Compute

All numbers here are the protocol's **ESTIMATES** (§17) until EXP-001 measures them. Nothing has been run.

**Remote execution infrastructure is ready; scientific training has not been executed.** The local machine was measured NOT_READY (no CUDA GPU). All execution runs in a private remote GPU environment; see [REMOTE_COMPUTE.md](REMOTE_COMPUTE.md) for requirements, run isolation, resume rules, gates, the nnU-Net dataset writer and result synchronisation, and [GITHUB_SETUP.md](GITHUB_SETUP.md).

## Budget (protocol §17.1)

| Item | Estimate |
|---|---|
| Cap | 220 GPU-h (Kaggle free tier, about 4–8 weeks) |
| Training: 6 runs × 250 epochs | ≈ 75–150 GPU-h |
| Planned C5 inference: ≈ 828 cases × 5 conditions × 6 models | ≈ 21–55 GPU-h |
| C15 (internal test, arm B) | ≈ 4–10 GPU-h |
| Total | ≈ 100–215 GPU-h |

Softmax maps are not stored except for ≤ 20 pre-selected figure cases. Metrics are computed on the fly.

## EXP-001 (gate D; PLANNED, not authorized)

[docs/experiments/EXP-001_COMPUTE_PILOT_SPEC.md](../experiments/EXP-001_COMPUTE_PILOT_SPEC.md) and `configs/experiments/EXP-001.yaml`:

- 40 development (site ≠ 1) cases;
- 5-epoch runs;
- capped at 10 GPU-h;
- no label-based metrics.

It measures epoch time (P100, T4, 2×T4), GPU utilization, peak memory, preprocessing time and disk, resume correctness, per-case inference time, quota, session limit and seed variability. Its outputs decide SR1 (150 epochs if > 25 GPU-h per run) and SR6 (ordered reductions if the projection exceeds 220 GPU-h).

## Before the first GPU job

1. B1 closed (data route) and B2 (data acquired). EXP-001 also needs D1–D2.
2. Pin nnU-Net v2, PyTorch, CUDA and Python. Record them.
3. **Verify `models/nnunet_trainers.py` against the pinned nnU-Net version.** It is a template: the dropout hook must act after augmentation on the training batches only, and seeds must propagate. Do this with a synthetic 1-epoch smoke run.
4. Notebooks clone an exact commit or tag (§24). Credentials come from notebook secrets only.
6. Each run gets its own namespace, `<results>/<experiment>/arm_<a>_seed_<s>`, and a `run_manifest.json`. Resuming needs an explicit `--resume` and a verified checkpoint (REMOTE_COMPUTE.md §1–§2).
5. Every run starts with `require_action(...)`. It fails until the gates are closed.
