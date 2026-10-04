# 05 — Experimental Design

This document defines (1) a **shared experimental backbone** that applies to Directions 1, 2, 3 and 5, and (2) **direction-specific experiment matrices**. The final matrix is fixed only in `FINAL_RESEARCH_PROTOCOL.md`, after a direction is chosen.

**No experiment has been run.** All IDs below are *planned* IDs. Every expected outcome is labelled **[EXPECTED]**.

## 1. Pipeline logic

```
BASELINE ─► PROPOSED/STUDIED CONDITION ─► CONTROLLED COMPARISON ─► ABLATION
   ─► ROBUSTNESS (missingness / site / TTA) ─► FAILURE ANALYSIS
   ─► STATISTICAL ANALYSIS ─► EXTERNAL VALIDATION
```

Each experiment must name the research question it answers. Experiments that answer none are removed.

## 2. Shared backbone

| Element | Specification |
|---|---|
| Source data | BraTS 2021 training set, de-duplicated; split per [04](04_DATASET_STRATEGY.md) §2 |
| Input | 4 channels in fixed order `[T1, T1c, T2, FLAIR]`, asserted by unit test |
| Preprocessing | BraTS-provided co-registration/skull-strip. Per-case, per-channel z-score within the brain mask. Crop to the non-zero bounding box. |
| Missing-sequence simulation | Channel set to 0 after normalization (primary). Sensitivity analysis: channel set to the mean of the other available channels. Both documented. |
| Model framework | nnU-Net v2 (3d_fullres) as the primary engine. A MONAI SegResNet config serves as a lightweight fallback for low-compute pilots. |
| Training schedule | Pre-registered epochs (full: nnU-Net default; reduced: e.g. 250 epochs if compute requires). **Identical across compared arms.** |
| Seeds | 3 training seeds per arm (0, 1, 2). Ensembles are formed from seeds. |
| Evaluation regions | ET, TC, WT (region-based) |
| Output | `results/EXP-xxx/{config.yaml, metrics.json, per_case.csv, environment.json, training_log.json}` |

## 3. Metrics (chosen with Metrics Reloaded [D11])

**Segmentation:**

- Dice per region, and HD95 per region with a documented rule for empty prediction or empty reference (BraTS convention: penalty value; to verify).
- Lesion-wise Dice/HD95 (BraTS 2023 definition [B8]) as a secondary metric.
- Absolute and signed volume error (mL), because it is clinically interpretable [C7].
- NSD (normalized surface distance) at a pre-set tolerance (e.g. 1 mm).

**Reliability:**

- Voxel-level: ECE (equal-mass bins; report the bin count), Brier score, reliability diagrams. The ECE computed over a ROI (dilated union of GT and prediction) is reported separately from whole-volume ECE, because background voxels dominate otherwise.
- Case-level failure detection: AURC and e-AURC [D2], with risk = 1 − Dice (per region) and alternative risk = volume error. AUROC for binary failure (Dice < pre-registered threshold).
- Spearman ρ between case confidence and Dice.
- Voxel-level QU-BraTS score [D1] for comparability with the BraTS UQ literature.

**Efficiency:** parameters (counted), measured wall-clock training/inference time, and peak GPU memory. These are **recorded from real runs only**.

## 4. Statistical methodology

- **Unit of analysis:** patient. Seeds are a nuisance factor, not independent samples.
- **Primary comparisons:** paired per-patient differences between arms, with per-patient values averaged over seeds.
  - Test: two-sided Wilcoxon signed-rank (no normality assumption; Dice differences are bounded and skewed).
  - Effect size: median difference with Hodges–Lehmann CI, plus a patient-bootstrap 95% CI (10,000 resamples) of the mean difference.
  - A t-test is not used by default.
- **Multiplicity:** Holm–Bonferroni within each pre-registered family (e.g. the 15 subsets × 3 regions for one comparison). Families are declared in the protocol.
- **Seed variability:** report mean ± SD across seeds of the dataset-level metric. Optionally, a linear mixed model with patient and seed random effects as a sensitivity analysis.
- **Equivalence (D2 only):** TOST with a pre-registered margin, justified from inter-rater variability literature (to be sourced).
- **AURC/ECE comparisons:** patient-bootstrap CIs of the difference (paired resampling of the same patients for both arms).
- **External sets:** analysed separately, never pooled with internal results.
- **Small samples:** BraTS-Africa has a small labelled set, so report CIs and avoid dichotomous "significant" language.
- **Pre-registration:** the hypotheses, primary metrics, families and thresholds are frozen in `FINAL_RESEARCH_PROTOCOL.md` **before** any internal-test or external evaluation.

## 5. Direction-specific experiment matrices (planned)

### Direction 1 — Reliability under missing sequences

| ID | Question | Data | Model(s) | Varied | Controlled | Metrics | Runs | Interpretation criterion |
|---|---|---|---|---|---|---|---|---|
| EXP-001 | Pilot: pipeline correctness and cost | 20–50 train cases | SegResNet / nnU-Net short | — | — | Dice, time, memory | 1 | Pipeline runs end-to-end; cost measured |
| EXP-010 | Full-input baseline accuracy | BraTS21 split | nnU-Net full | seed | schedule | Dice/HD95/vol | 3 | Sanity: comparable to published nnU-Net BraTS 2021 range (literature, not target) |
| EXP-011 | Dropout baseline accuracy per subset | same | nnU-Net + dropout | seed, subset (15) | schedule | same | 3 | Replicates the direction of [C6, C7] or not |
| EXP-020 | Voxel calibration vs subset | internal test | EXP-011 models + {entropy, MC-drop, ensemble, TTA} | subset, UQ method | model weights | ECE (ROI), Brier, QU-BraTS | 3 | H1b supported if ET ECE increase without T1c has a CI excluding 0 |
| EXP-021 | Failure detection vs subset | internal test | same | subset, aggregation | same | AURC, e-AURC, AUROC | 3 | H1a supported if e-AURC increase (−T1c vs full) has a CI excluding 0 |
| EXP-030 | External replication | BraTS-Africa, UPenn | same | dataset | no re-tuning | all above | 3 | H1c supported if effect size is larger externally (bootstrap CI of interaction) |
| EXP-040 | Remedy (only if EXP-020/021 show a failure) | val → test | + subset-conditioned calibration | remedy on/off | base model | ECE, AURC | 3 | Remedy kept only if it improves on internal **and** external without Dice loss |
| EXP-050 | Sensitivity: missingness simulation | internal test | same | zero vs mean-imputation | — | all | 3 | Conclusions robust if the sign of effects is unchanged |
| EXP-060 | Failure analysis | all test sets | best config | — | — | case lists, error types | — | Qualitative + categorized counts |

### Direction 2 — Missing-modality benchmark

EXP-010/011 as above, plus EXP-1xx: one block per specialized method (official code, pinned commit) × 3 seeds × {published recipe, matched budget}. Evaluation follows EXP-011 and EXP-030. The primary test is TOST equivalence plus superiority per subset.

### Direction 3 — Failure detection under real shift

EXP-010 ensemble (seeds as members). EXP-3xx: {entropy, MC-drop, pairwise-DSC, learned QC, Mahalanobis} × {internal, BraTS-Africa, UPenn} × {risk definitions}, plus threshold-transfer analysis with thresholds fixed on validation.

### Direction 4 — Pre→post-treatment

Training regimes {pre, post, mixed} × 3 seeds. Test on pre-internal, post-internal and RHUH. Accuracy and reliability metrics use the harmonized labels.

### Direction 5 — TTA reliability

EXP-010 source models. EXP-5xx: {none, norm-stats, entropy-min, aug-consistency} × {BraTS-Africa, UPenn}. TTA hyperparameters are chosen **only** on internal validation with synthetic shifts. The target sets are never used for tuning.

## 6. Failure-analysis pipeline (all directions)

Automated per-case categorization using pre-defined, code-implemented rules:

- **false-negative region:** GT region present, prediction empty
- **false-positive region:** prediction present, GT empty
- **small-lesion failure:** GT ET volume below a threshold
- **boundary error:** high HD95 with acceptable Dice
- **modality-related:** failure appears only in certain subsets
- **domain-related:** failure rate by dataset
- **uncertainty-related:** confident failures, i.e. low-uncertainty cases in the worst Dice decile

Qualitative figures are sampled by rule (e.g. worst-k per category, fixed seed), **not hand-picked**.

## 7. Compute plan

All figures are **[ESTIMATE]s to be replaced by EXP-001 measurements.**

- **Kaggle:**
  - ≈30 GPU-h/week shared across P100 and 2×T4 (per Kaggle documentation and secondary reports; verify at start)
  - ≈12 h max per session (verify)
  - ≈20 GB persistent `/kaggle/working` output (verify)
- **Colab free:** unreliable GPU availability and session limits. It is a fallback only.
- **Implication:**
  - A full-schedule nnU-Net 3d_fullres training on ~900 BraTS cases likely needs multiple 12 h sessions on a T4/P100, which requires **checkpoint/resume**.
  - 3 seeds × 2 arms may consume several weeks of free quota.
  - Options: a reduced, pre-registered schedule identical across arms; fold-0 only; or paid GPU hours.
  - The choice must be made in the protocol **before** training and reported honestly in the paper.
- **Local laptop (Ryzen 7, no NVIDIA GPU):** unit tests, synthetic-data tests, metric code, statistics, figure generation from saved per-case CSVs. No 3D training.
