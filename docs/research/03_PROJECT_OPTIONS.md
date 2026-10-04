# 03 — Project Options (Research Directions)

Five directions, derived from gaps G1–G5 in [02_RESEARCH_GAP_ANALYSIS.md](02_RESEARCH_GAP_ANALYSIS.md). **They are listed in gap order, not ranked.** No scores are assigned. The choice is the PI's.

Compute figures are **[ESTIMATE]s**, order-of-magnitude only. They must be replaced by measurements from a pilot run (see [05](05_EXPERIMENTAL_DESIGN.md) §7). Baseline and metric details are in [06](06_BASELINE_STRATEGY.md) and [05](05_EXPERIMENTAL_DESIGN.md).

---

## Direction 1 — Reliability under missing MRI sequences

1. **Working title:** *Does the model know when a sequence is missing? Calibration and failure detection of glioma segmentation under incomplete MRI.*
2. **Research question:** When one or more of T1/T1c/T2/FLAIR is missing at inference, do voxel calibration and case-level failure detection remain valid? Is degradation specific to the missing sequence and tumour sub-region, and does it persist on external cohorts?
3. **Hypothesis (falsifiable):**
   - H1a: AURC for case-level failure detection is worse for subsets lacking T1c than for full input, beyond what the Dice drop alone explains. This is measured with the normalized/excess AURC relative to the optimal ranking.
   - H1b: pixel-level calibration error on ET increases when T1c is absent.
   - H1c: these effects are larger on external than internal data.
4. **Motivation:** missingness is common and observable [A12, C8]. Accuracy can be recovered [C7], but silent failures are the clinical risk.
5. **Existing literature:** [C1–C11], [D1–D4], [C9] closest.
6. **Gap:** G1.
7. **Proposed contribution:**
   - (i) a controlled empirical characterization;
   - (ii) *conditional on (i) finding a systematic failure*, a minimal remedy (e.g. missingness-conditioned temperature scaling or subset-specific failure thresholds fitted on validation data only), ablated against no remedy.
8. **Why existing work does not solve it:** missing-modality papers evaluate Dice only. Failure-detection benchmarks [D2] do not include missing-sequence shift. [C9] models missing-evidence uncertainty but, per its abstract, evaluates internally on BraTS 2018/2020 (to verify).
9. **Datasets:** source is de-duplicated BraTS 2021 training. External: UPenn-GBM (manually revised subset, de-duplicated) and BraTS-Africa. Optionally UCSF-PDGM (de-duplicated) and EGD (WT only).
10. **Baselines:**
    - segmentation: nnU-Net (full-modality) and nnU-Net + modality dropout; optionally per-subset nnU-Net [C6] on a reduced set of subsets
    - uncertainty: softmax entropy, MC-dropout, deep ensemble (M=5 if affordable), TTA
    - failure detection: mean-aggregated uncertainty, pairwise-DSC [D2]
11. **Experiments:** all 15 subsets × {internal, external} × {UQ methods}. Missingness is simulated by channel zeroing (and, as a check, by mean-imputation) — see [05](05_EXPERIMENTAL_DESIGN.md).
12. **Ablations (only if a remedy is proposed):** remedy on/off; conditioning variable (subset identity vs number of missing sequences); calibration fitted on internal validation only.
13. **Metrics:**
    - segmentation: Dice / HD95 per region (ET/TC/WT), lesion-wise variants
    - reliability: AURC and e-AURC, ECE (with binning caveats), Brier score, Spearman ρ(confidence, Dice)
    - clinical: absolute volume error
14. **Statistics:**
    - patient-level paired comparisons (Wilcoxon signed-rank with Holm correction across subsets)
    - patient-bootstrap 95% CIs for AURC/ECE differences
    - 3 seeds; seed variance reported separately
15. **Compute** [ESTIMATE]: base models ≈ 3 seeds × (1 full + 1 dropout model), each several GPU-days on a T4/P100 at full nnU-Net schedule. Kaggle's quota (≈30 GPU-h/week, 12 h/session) makes this **tight**. It is likely to need a reduced epoch schedule, fold-0 only, and an ensemble built from the seeds. Inference over 15 subsets × ≈1,000+ cases × UQ passes is significant but splittable across sessions.
16. **Risks:**
    - the effect may be null (reliability is preserved), which is a valid but less exciting result
    - external label quality (UPenn automated vs manual)
    - compute
17. **Novelty risks:** [C9], [C10]. An unseen 2025–2026 paper on "calibration under missing modality" would narrow the contribution to external validation.
18. **Reproducibility requirements:**
    - fixed de-duplication list, published as IDs only
    - fixed splits
    - subset-generation code
    - a UQ inference seed per pass
19. **Possible venues** (see [07](07_PUBLICATION_STRATEGY.md)): UNSURE workshop at MICCAI, MIDL, MELBA; with strong external results, MedIA/TMI.
20. **Evidence required before a novelty claim:**
    - a structured search returning no equivalent evaluation
    - a full-text read of [C9, C10, D4]
    - confirmation that the external sets are truly non-overlapping

---

## Direction 2 — Fair external benchmark of missing-modality architectures

1. **Working title:** *Do specialized missing-modality networks beat a dropout-trained nnU-Net? A controlled, externally validated comparison for glioma segmentation.*
2. **Research question:** Under identical data, splits, preprocessing, budget and evaluation, do representative missing-modality architectures outperform nnU-Net with modality dropout across the 15 subsets, internally and externally?
3. **Hypothesis:** H2: the mean Dice difference (specialized − dropout-nnU-Net) is ≤ a pre-registered equivalence margin (e.g. 1 Dice point; to be justified) on most subsets. This is tested with TOST equivalence plus superiority tests. The opposite finding would be equally reportable.
4. **Motivation:** [B2] in general 3D segmentation; W1/W2 weaknesses in missing-modality work.
5. **Existing literature:** [C1–C11], [C6–C8], [B2].
6. **Gap:** G2.
7. **Contribution:** benchmark, protocol, fixed public split IDs, and a reproducible code harness.
8. **Why not already solved:** no head-to-head, externally validated, multi-seed comparison found.
9. **Datasets:** same as Direction 1.
10. **Baselines:** nnU-Net full, nnU-Net + dropout, per-subset nnU-Net (subset of subsets); specialized models selected by *official code availability and licence*: candidates RFNet, mmFormer, M3AE, ShaSpec.
11. **Experiments:** each method × 3 seeds × 15 subsets × {internal, external}. Each method trained with (a) its published recipe and (b) a matched budget.
12. **Ablations:** the dropout rate / schedule in the nnU-Net baseline, and the effect of the published vs matched training budget.
13. **Metrics:** Dice/HD95 per region, lesion-wise metrics, volume error, parameters, measured train/inference time and memory.
14. **Statistics:** paired Wilcoxon / TOST over patients per subset, Holm correction, bootstrap CIs, and rank stability across seeds (bootstrap rankings as in challenge analyses).
15. **Compute** [ESTIMATE]: **the heaviest option.** 4–6 methods × 3 seeds of 3D training exceeds a free Kaggle quota over any reasonable timeline unless training is shortened. A paid GPU (e.g. Colab Pro / cloud A100 hours) or a reduced scope (2 specialized methods, fold-0) is likely necessary.
16. **Risks:** re-implementing or porting other groups' code (bugs attributed to the method); fairness disputes; compute.
17. **Novelty risk:** medium. The benchmark must be broad enough to be convincing. Critics may ask why the newest 2025–2026 methods are missing (many lack code).
18. **Reproducibility:** pinned commit hashes of third-party repos, licence compliance, identical preprocessing.
19. **Venues:** MELBA, MIDL, MICCAI main track (benchmark papers, cf. [B2]), MedIA.
20. **Evidence required:** a structured search for existing missing-modality benchmarks, and confirmation that the official code reproduces published internal numbers (a sanity check, reported honestly).

---

## Direction 3 — Clinically defined failure detection under real acquisition shift

1. **Working title:** *From Dice to decisions: case-level failure detection for glioma segmentation on real external cohorts.*
2. **Research question:** Which failure-detection approach best ranks cases by clinically relevant error (region-wise Dice, absolute volume error) on real external cohorts? Do thresholds chosen internally transfer?
3. **Hypothesis:** H3: thresholds that achieve a target selective risk internally violate that target externally (coverage–risk miscalibration). Pairwise-DSC ensembles degrade less than learned QC.
4. **Motivation:** QC is needed for deployment; [D2, D4].
5. **Literature:** [D1–D4, D9].
6. **Gap:** G3.
7. **Contribution:** evaluation under real shift with clinical failure definitions, plus threshold transfer analysis.
8. **Why not solved:** [D2] uses synthetic or grade shifts; [D4] uses BraTS-SSA but a learned-QC-only perspective. Partially solved — see novelty risk.
9. **Datasets:** BraTS 2021 (source), BraTS-Africa, UPenn-GBM, optionally EGD.
10. **Baselines:** entropy, MC-dropout, ensemble pairwise-DSC, a learned QC regressor (re-implemented simply), and a Mahalanobis OOD score.
11. **Experiments:** fit on internal validation, test on internal test and each external set.
12. **Ablations:** aggregation choice; failure definition (Dice threshold vs volume error).
13. **Metrics:** AURC / e-AURC, selective risk at fixed coverage, threshold-transfer error.
14. **Statistics:** bootstrap CIs over patients; DeLong or bootstrap tests for AUROC of binary failure detection.
15. **Compute** [ESTIMATE]: moderate (one ensemble of 3–5 models).
16. **Risks:** small external sample (BraTS-Africa labelled cases), so wide CIs.
17. **Novelty risk:** **high** ([D2, D3, D4]).
18. **Reproducibility:** fixed failure definitions pre-registered before looking at external results.
19. **Venues:** UNSURE workshop, MIDL, MELBA.
20. **Evidence required:** full-text review of [D2, D4] and demonstration of a result they do not cover.

---

## Direction 4 — Pre-operative → post-treatment shift

1. **Working title:** *Do segmentation models know they are looking at a resection cavity? Accuracy and reliability of glioma segmentation across the treatment timeline.*
2. **Research question:** How do accuracy and reliability signals change when pre-operative-trained models see post-treatment MRI? Does mixing pre- and post-treatment training data restore both?
3. **Hypothesis:** H4: pre-op-trained models produce confidently wrong labels in resection cavities (low uncertainty on erroneous voxels), and mixing restores accuracy faster than calibration.
4. **Motivation:** post-treatment monitoring is the main clinical use [A4].
5. **Literature:** [A4, A11, B7], plus pre/post mixing nnU-Net work (medRxiv 2023; verify).
6. **Gap:** G4.
7. **Contribution:** a reliability-focused analysis of the treatment-timeline shift.
8. **Why not solved:** challenge work focuses on accuracy.
9. **Datasets:** BraTS 2021 (pre-op), BraTS 2024 post-treatment training data / MU-Glioma-Post (**access and licence to verify**), RHUH-GBM (external, both timepoints).
10. **Baselines:** nnU-Net trained pre-only, post-only, and mixed.
11. **Experiments:** 3 training regimes × 3 seeds × test on pre/post internal and RHUH external.
12. **Ablations:** mixing ratio; label-harmonization choice.
13. **Metrics:** region Dice/HD95 under a harmonized schema, RC-specific error, AURC, ECE.
14. **Statistics:** as in Direction 1.
15. **Compute** [ESTIMATE]: high (two large training sets).
16. **Risks:** the label schemas differ (RC, SNFH), so harmonization choices can dominate results; data access.
17. **Novelty risk:** medium, in a fast-moving area.
18. **Reproducibility:** a published harmonization mapping.
19. **Venues:** BrainLes workshop, MIDL, Radiology: AI (if clinically framed).
20. **Evidence required:** a search of BraTS 2024/2025 proceedings for reliability analyses.

---

## Direction 5 — Does test-time adaptation silently break reliability?

1. **Working title:** *Adapted but overconfident? Effects of test-time adaptation on calibration and failure detection in cross-site glioma segmentation.*
2. **Research question:** Do common TTA methods change calibration and failure detectability on external glioma cohorts, and can they increase the rate of confident failures?
3. **Hypothesis:** H5: entropy-minimizing TTA improves or preserves mean Dice but worsens AURC and ECE. Normalization-statistics TTA does not.
4. **Motivation:** TTA is proposed for BraTS-Africa-type shift [E1]; [E2] shows fragility.
5. **Literature:** [E1, E2, E5, C10, D2].
6. **Gap:** G5.
7. **Contribution:** a reliability audit of TTA with a mechanistic hypothesis.
8. **Why not solved:** TTA papers report accuracy only (per the abstracts checked).
9. **Datasets:** BraTS 2021 source; BraTS-Africa, UPenn-GBM external.
10. **Baselines:** no adaptation; BN/IN-statistics adaptation; TENT-style entropy minimization; augmentation-consistency TTA. SmaRT [E1] if code is available.
11. **Experiments:** each TTA × each external set × 3 seeds of the source model.
12. **Ablations:** adaptation steps / learning rate (tuned on internal validation only), updated parameters.
13. **Metrics:** Dice/HD95, AURC, ECE, fraction of "confident failures" (predefined).
14. **Statistics:** paired per-patient tests and bootstrap CIs.
15. **Compute** [ESTIMATE]: low to moderate — only the source models need training; TTA is inference-time.
16. **Risks:**
    - TTA hyperparameters are hard to set without touching target data. The protocol must forbid target tuning.
    - The net effect may be null.
17. **Novelty risk:** medium. General-ML work on TTA calibration may already make the point. Search required.
18. **Reproducibility:** TTA state reset per case (or per dataset), stated explicitly.
19. **Venues:** UNSURE workshop, MIDL, DART workshop (Domain Adaptation and Representation Transfer; verify it is still held).
20. **Evidence required:** a search for "test-time adaptation calibration segmentation".

---

## Factual comparison (not a ranking)

| Aspect | D1 Missing-seq reliability | D2 Missing-modality benchmark | D3 Failure detection under real shift | D4 Pre→post treatment | D5 TTA reliability |
|---|---|---|---|---|---|
| Type of contribution | Empirical characterization (± small remedy) | Benchmark | Evaluation | Evaluation (± training-regime study) | Evaluation / audit |
| Closest prior work | [C9], [C10], [D2] | [B2], [C6–C8] | [D2], [D3], [D4] | [A4], [B7] | [E1], [E2] |
| Datasets needing new access | TCIA restricted licence (BraTS 2021), TCIA (UPenn, BraTS-Africa) | Same | Same | + BraTS 2024 post-tx / MU-Glioma-Post (verify) | Same as D1 |
| Models to train (min.) | 2 configs × 3 seeds | 4–6 methods × 3 seeds | 3–5 (ensemble) | 3 regimes × 3 seeds | 1 config × 3 seeds |
| Third-party code dependency | Low (nnU-Net / MONAI) | High (multiple research repos) | Low | Low | Medium (TTA methods) |
| Free-tier feasibility [ESTIMATE] | Tight | Unlikely without paid GPU or reduced scope | Feasible | Tight to unlikely | Feasible |
| Null result still publishable? | Yes, if rigorous | Yes | Weaker | Yes | Yes |
| Main novelty threat | Unfound 2025–26 paper; [C9] | Existing benchmark we missed | [D2]/[D4] | Fast-moving BraTS 2024–25 work | General-ML TTA-calibration work |

Directions can be combined only if a single research question requires it. For example, D1 and D5 share infrastructure (the source models and reliability metrics), but combining them into one paper would need one hypothesis that links them.
