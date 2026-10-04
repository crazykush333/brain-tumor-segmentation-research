# EXP-001 — Compute Pilot Specification (PLAN ONLY — NOT EXECUTED)

| Field | Value |
|---|---|
| Status | **Specification only. Not authorized to run.** |
| Protocol | [FINAL_RESEARCH_PROTOCOL_v1.0.md](../research/FINAL_RESEARCH_PROTOCOL_v1.0.md) v1.0 (frozen; authoritative), lifecycle gate D, §17.2, SR1, SR6–SR8 |
| Prepared | 2026-09-28 |
| Purpose | Replace the compute **ESTIMATES** in §17 with measurements, and decide SR1/SR6 **before** v1.0. |
| Not a purpose | Any accuracy, calibration or reliability result. EXP-001 produces **no scientific findings**. |

## 0. Preconditions (all must hold before running)

1. Owner authorization of EXP-001.
2. Owner-approved data-acquisition and storage route (checklist item 5 / SR7). Credentials are handled as notebook secrets and never committed.
3. **A1 condition (protocol v0.4, gates D3–D5).** "A1 resolved" means, for EXP-001 only:
   - the pilot uses only site ≠ 1 development cases;
   - it computes no label-based scientific metrics;
   - it does not require the final scientific split;
   - it cannot alter the final analysis (pilot models are discarded, and no pilot output feeds any threshold, grouping or split decision).

   Completion of the §6.2 patient-grouping gate is **not** required for EXP-001.
4. Pinned software: nnU-Net v2 version, PyTorch, CUDA and Python recorded. The same versions are intended for the main study.

## 1. Workload

**Pilot case pool:**

- **N_pilot = 40** BraTS 2021 training cases drawn **only from the development pool** (site ≠ 1). Selection uses a fixed seed (`101`), by sorted BraTS ID, before and independently of the final split.
- **No site-1 (UPenn) case and no BraTS-Africa case is touched.**
- The pilot cases will later be assigned to train/validation/test by the normal split procedure. To avoid information leakage, **no segmentation metric is computed on any pilot case** (see §4).

**Configuration:** exactly the §9 protocol configuration:

- nnU-Net v2 3d_fullres, region-based;
- arm B dropout policy (§10) for the timing runs;
- arm A is timed for one short run only, to confirm equal cost.

**Durations:** short runs of **E_pilot = 5 epochs** × 250 iterations. Epoch time is independent of dataset size, so it extrapolates to 250 epochs.

**Measurement matrix:**

| Run | Hardware | Arm | Seeds | Epochs |
|---|---|---|---|---|
| P1 | P100 (single) | B | 0 | 5 |
| P2 | T4 (single) | B | 0 | 5 |
| P3 | 2×T4, two concurrent processes (one per GPU) | B | 0 and 1 | 5 each |
| P4 | T4 (single) | A | 0 | 5 |
| P5 | T4 (single) | B | 1, 2 (sequential) | 5 each (seed variability) |
| R1 | T4 | B | 0 | resume test (§2.8) |
| I1 | T4 | B (3 members = P2/P5 checkpoints) | — | inference timing (§2.9) |

Total pilot GPU use is capped at **10 GPU-h** (protocol §17). Stop if it is exceeded.

## 2. Measurements and procedures

| # | Quantity | Procedure | Recorded as |
|---|---|---|---|
| 1 | P100 s/epoch | Wall-clock per epoch from nnU-Net logs, epochs 2–5 (epoch 1 excluded as warm-up); median and IQR | `epoch_time_s` |
| 2 | Single-T4 s/epoch | As 1, run P2 | same |
| 3 | 2×T4 concurrent s/epoch | As 1 for both processes simultaneously (P3); slowdown factor vs P2 | same + `concurrency_factor` |
| 4 | GPU utilisation | `nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv -l 5` during epochs 2–5; mean utilisation; flag CPU-bound if mean < 70% | `gpu_util_mean` |
| 5 | Peak GPU memory | `torch.cuda.max_memory_allocated()` plus nvidia-smi peak | `peak_mem_gb` |
| 6 | Preprocessing time | Wall-clock of `nnUNetv2_plan_and_preprocess` on N_pilot cases; extrapolated linearly to ~592 train+val cases [ESTIMATE] | `preproc_s_per_case` |
| 7 | Disk usage | `du -sh` of raw, preprocessed and results folders; per-case preprocessed size × planned case count | `disk_gb` |
| 8 | Checkpoint/resume correctness | Run R1 to epoch 3, kill the process, resume with `--c`. Pass if training continues from the saved epoch, the optimizer/LR schedule state is restored (logged LR at the resumed epoch equals the expected schedule value) and no crash occurs. Loss continuity is inspected, not compared numerically (non-determinism). | `resume_pass` |
| 9 | Per-case 3-member ensemble inference time | Sliding window, step 0.5, mirroring **off**, three members loaded; time per case per missingness condition on 10 pilot cases × C5, **without computing any metric against labels**. Metric-computation cost is timed separately on **synthetic volumes** of identical shape. | `infer_s_per_case_condition`, `metric_s_per_case` |
| 10 | Kaggle weekly quota | Read from the Kaggle account UI at run time; record the date | `quota_h_week` |
| 11 | Kaggle session limit | Documented limit plus observed behaviour | `session_limit_h` |
| 12 | Writable disk | `df -h /kaggle/working /kaggle/tmp` (or platform equivalents) | `disk_writable_gb` |
| 13 | Short-run seed variability | P2 vs P5 seeds: epoch-time variation and training-loss curves over 5 epochs. **Descriptive only; not an accuracy measure.** | `seed_epoch_time_cv`, loss curves |

All outputs go to `results/EXP-001/`:

- `config.yaml`
- `environment.json` (GPU, driver, CUDA, PyTorch, nnU-Net, Python, platform)
- `timings.csv`
- `gpu_monitor.csv`
- `disk.csv`
- `resume_check.json`
- `budget_projection.json`
- `README.md` summarising pass/fail

**No predictions, images or checkpoints are committed.**

## 3. Budget update (how results change the 220 GPU-h cap)

```
T_train_run   = median_epoch_s(platform) × 250 / 3600 × (1 + overhead_frac)   # overhead_frac measured: validation/checkpoint time share
T_train_total = 6 × T_train_run            (÷ concurrency gain if P3 shows ≥1.6× throughput and CPU not bound)
T_infer_prim  = infer_s_per_case_condition × 828 cases × 5 conditions × 6 models / 3 (members loaded together) / 3600
                (+ metric_s_per_case term, CPU; counted only if on the GPU clock)
T_infer_C15   = infer_s × 148 × 10 × 3 / 3 / 3600
T_total       = T_train_total + T_infer_prim + T_infer_C15 + T_preproc_gpu(≈0)
```

The inference formula counts ensemble passes per member. The exact count convention is recorded in `budget_projection.json`.

**Decision rules (from the protocol):**

- **SR1:** if T_train_run > 25 GPU-h on the chosen platform, switch all six runs to 150 epochs (recompute).
- **SR6:** if T_total > 220 GPU-h, apply in order, re-projecting after each:
  1. arm A external inference on Full / −T1c / −FLAIR only;
  2. drop C15;
  3. 150 epochs;
  4. consult the owner.
- **SR7:** if the approved data route cannot hold the data within the measured writable/persistent disk, halt.
- **SR8:** if the quota or hardware differs materially from the planning assumptions (~30 GPU-h/week, 12 h sessions), recompute the calendar-time projection.

Calendar projection = T_total / measured weekly quota, reported with the assumption stated.

## 4. Acceptance criteria

EXP-001 **passes** if all of the following hold:

- all 13 quantities are recorded;
- the resume check passes;
- peak memory fits the chosen GPU at the default plan without changing patch or batch size (a change would be a protocol amendment);
- `budget_projection.json` shows T_total ≤ 220 GPU-h after at most the SR6/SR1 reductions permitted without owner consultation.

EXP-001 **fails**, and the project returns to the owner, if:

- any of those conditions fails;
- the platform cannot hold the required data;
- a planned change would alter the analysis plan.

## 5. Stopping criteria during the pilot

- The GPU time used exceeds 10 GPU-h.
- Any out-of-memory error at the default plan (record it and stop; do not tune).
- A data-integrity failure (missing sequence or label in a pilot case). Record the IDs; do not substitute cases ad hoc.
- Any accidental access to site-1, BraTS-Africa or label-based metrics on pilot cases: stop and log it as a deviation.

## 6. Explicitly out of scope

Out of scope for EXP-001:

- accuracy, Dice, calibration, AURC or any reliability metric;
- hyperparameter tuning;
- any selection among configurations based on segmentation quality;
- creating the final split;
- touching site-1 or BraTS-Africa data;
- producing figures for publication.
