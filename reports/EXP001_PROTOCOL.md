# EXP-001 and main-training configuration (as frozen; for execution)

This document only reads the configuration; it changes nothing.

**Sources:**
- frozen protocol v1.0, §8–§11, §17 and SR1/SR6;
- `docs/experiments/EXP-001_COMPUTE_PILOT_SPEC.md`;
- `configs/experiments/EXP-001.yaml`;
- `configs/experiments/main_training.yaml`;
- `src/brats_uncertainty/models/nnunet.py`;
- `src/brats_uncertainty/models/nnunet_trainers.py`.

**Execution status (2026-10-07): run.** EXP-001 ran on Kaggle (Tesla T4) after the verified A5 split. The measurements are in `results/EXP-001/`, and gates D3–D5 are closed. Main results:
- median epoch 248.26 s;
- projected 19.41 GPU-h per run and 125.71 GPU-h in total, so SR1 and SR6 do not apply and 250 epochs stand.

The first R1 resume test was invalid because of a harness defect: the child process's output was block-buffered. R1 is re-run once in the next session. D6 closes only after R1 passes (`docs/research/execution/D6_OWNER_DECISION.yaml`).

An earlier attempt failed at start-up because of a trainer-signature defect (`KeyError: 'args'`). It produced no measurements and has been fixed.

## 1. EXP-001 is a compute pilot, not an accuracy experiment

**Purpose** (spec, header): "Replace the compute ESTIMATES in §17 with measurements, and decide SR1/SR6." It **produces no scientific findings**.

| Item | Frozen value |
|---|---|
| Cases | 40 development cases (site ≠ 1), chosen by `numpy.random.default_rng(101)` on sorted IDs, independent of the final split |
| Runs | P1 (P100, arm B, seed 0), P2 (T4, B, 0), P3 (2×T4 concurrent, B, seeds 0/1), P4 (T4, A, 0), P5 (T4, B, seeds 1, 2), R1 (resume test), I1 (inference timing) |
| Epochs | 5 per run × 250 iterations (epoch time extrapolates to 250 epochs) |
| Cap | 10 GPU-h total |
| Measured | s/epoch (median, IQR, epochs 2–5); GPU utilisation; peak GPU memory; preprocessing time; disk use; resume correctness; ensemble inference time per case and condition; Kaggle quota and session limit; writable disk; seed variability of epoch time |
| Outputs | `results/EXP-001/{config.yaml, environment.json, timings.csv, gpu_monitor.csv, disk.csv, resume_check.json, budget_projection.json, README.md}` |
| **Forbidden** | any Dice, calibration, AURC or reliability metric; site-1 or BraTS-Africa data; hyperparameter tuning; creating the final split |

**Why no accuracy metrics are computed in the pilot (spec §1).** The 40 pilot cases are later assigned to train, validation or test by the normal split. Any label-based metric on them would leak test information.

Therefore the pilot **will not report** training-set Dice, IoU, sensitivity, specificity or Hausdorff distance. It reports training loss curves (descriptive only), timings, memory, parameter count and resume behaviour.

**Compute decision (spec §3–§4):**
- T_train_run = median s/epoch × 250 / 3600 × (1 + overhead).
- **SR1:** if T_train_run > 25 GPU-h, all six runs use 150 epochs.
- **SR6:** if the projected total exceeds 220 GPU-h, apply the ordered reductions; the last of them is to consult the owner.
- The pilot passes only if peak memory fits the default plan without changing the patch or batch size.

## 2. Main study models (protocol §9–§10)

| Item | Frozen value | Source |
|---|---|---|
| Architecture | nnU-Net v2 `3d_fullres`, region-based (sigmoid WT/TC/ET); no new architecture, MC-dropout, attention or fusion module | §9 |
| Preprocessing | BraTS-preprocessed images (SRI24, 1 mm, skull-stripped), no re-registration; nnU-Net z-score within the non-zero mask; channel order `[T1, T1c, T2, FLAIR]` (unit-tested) | §8 |
| Raw nnU-Net dataset | train + validation only; fingerprint and plans never see test data | §8, `main_training.yaml` |
| Augmentation | nnU-Net v2 default data augmentation (not overridden); arm B additionally applies the §10 modality dropout **after** augmentation | §10, `nnunet_trainers.py` |
| Missing-sequence dropout (arm B) | per sample p = 0.5 full input; otherwise one of the 14 non-full, non-empty subsets, uniformly; the normalized channel is set to 0; fixed a priori, not tuned | §10 |
| Loss | nnU-Net v2 default for region-based training (soft Dice + BCE, deep supervision); not overridden | trainers inherit `nnUNetTrainer` |
| Optimizer / LR | nnU-Net v2 default (SGD with Nesterov momentum, poly learning-rate schedule); not overridden. The exact values come from the nnU-Net version pinned at EXP-001 and are recorded in `environment.json` | trainers inherit `nnUNetTrainer` |
| Batch and patch size | from the nnU-Net plan generated on the train + validation dataset; recorded from the plan, not chosen | §8 |
| Epochs | 250 (`save_every` = 5); 150 only if SR1/SR6 require it (logged) | §9, SR1 |
| Seeds | 0, 1, 2 per arm (`BRATS_UNC_SEED`; Python, NumPy and torch are seeded) | §9, `nnunet_trainers.py` |
| Runs | 6 = arms A/B × seeds 0/1/2 | §9 |
| Checkpointing | **`checkpoint_final`** (pre-specified); checkpoints every 5 epochs for resume | §9 |
| Early stopping / best checkpoint | **none** (fixed schedule; the final checkpoint is used) | §9 |
| Validation set use | nnU-Net's training-time monitoring on the frozen validation partition (fold 0 = frozen `splits_final.json`); SR2 sanity check (arm A ensemble Full ET Dice ≥ 0.75); the indicator baseline I; the τ_q thresholds (C5) | §9, §11, §20 |
| Inference | sliding window, step 0.5, mirroring off, threshold 0.5; ensemble = mean of the 3 members' sigmoid probabilities | §9 |
| Evaluation conditions | C5 = {Full, −T1, −T1c, −T2, −FLAIR}; C4 is the primary estimand subset; C15 secondary (internal test, arm B) | §10 |
| Primary endpoint | within-condition ET ΔAURC (U1 vs I) over C4, internal test, arm B; patient-group bootstrap (seed 12345, 10,000 replicates) | §4 |
| Segmentation metrics | Dice per region; HD95 via the BraTS evaluator pinned at C6; volumes and failure categories as in §12 | §4, §12 |

**There is no "single final selected model".** The study evaluates the two arms' three-member ensembles. **No model selection** is made on validation or test data; the checkpoint is fixed in advance.

IoU, specificity and precision are not protocol metrics. Adding them would be a protocol change, so they are not part of the pre-registered evaluation.

## 3. Test-set isolation (enforced in code)

- The nnU-Net raw dataset contains only train + validation cases (§8).
- The internal test set and the external sets (UPenn HOI, BraTS-Africa) are evaluated **once**:
  - with code tagged `eval-v1` (SR4);
  - recorded in the evaluation ledger;
  - and only after gates C4–C6 (`require_action("evaluate_internal_test")` and related actions).
- τ_q and I come from validation only. No test or external data enter training, thresholds or model choice.
- Results are published only after independent verification (`docs/research/execution/RESULT_VERIFICATION_PROTOCOL.md`).
