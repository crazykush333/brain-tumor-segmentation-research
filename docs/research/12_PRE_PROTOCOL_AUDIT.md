# 12 — Pre-Protocol Novelty and Feasibility Audit

**Audit date:** 2026-09-27
**Candidate direction:** reliability of glioma segmentation under incomplete MRI acquisition
**Search log:** [search_log.md](search_log.md)

No experiments have been run. Every number in this document is either a **[LITERATURE RESULT]** quoted from the cited paper or an **[ESTIMATE]**.

---

## Phase 1 — New literature found in this audit

These are additions to the [09 matrix](09_LITERATURE_MATRIX.md), section H.

| ID | Work | Why it matters |
|---|---|---|
| H1 | **Reliability analysis for BraTS-GoAT segmentation: a controlled robustness study of deep-ensemble uncertainty.** arXiv:2608.13223, Aug 2026. Code: github.com/riyashet-hds/brats-goat-reliability | **Methodologically the closest study found.** nnU-Net ResEnc-L with a 3-seed deep ensemble; ECE and reliability diagrams; per-case AURC; **per-region ET/TC/WT**; Wilcoxon tests. Its shifts are **synthetic corruptions only**. It evaluates **no missing sequences** and no real site shift. |
| H2 | **Confidence is Not Reliability: Rethinking MC Dropout in Brain Tumour Segmentation.** Wong X. C. et al., MIUA 2026, arXiv:2606.19300 | Region-specific (ET) calibration failure hidden by high global AUROC [LITERATURE RESULT: ET ECE 0.915 for one model]. BraTS21 internal test of 126 cases, complete inputs, no external data. |
| H3 | **BMDS-Net.** Zhou et al., arXiv:2601.17504 (2026) | Bayesian calibration (ECE) on **complete** inputs. Tests single-sequence removal for **Dice only**. No failure detection, no per-region calibration, no seeds. |
| H4 | **GlioMODA.** Canisius J. et al., Neuro-Oncology Advances 2026. Code: github.com/BrainLesion/GlioMODA | 11 sequence protocols, **volumetric error** vs ground truth per protocol. No uncertainty or failure detection. |
| H5 | **AI-powered segmentation and prognosis with missing MRI in pediatric brain tumors.** npj Precision Oncology 2026 | Dropout-trained model for missing FLAIR/T1w in a pediatric cohort. Accuracy and prognosis only. |
| H6 | **Modality redundancy for MRI-based glioblastoma segmentation.** De Sutter S. et al., IJCARS 2024 | nnU-Net per input combination; accuracy only. |
| H7 | **Öchsner et al.**, peer-reviewed version in Frontiers in Neurology, 28 July 2026 (doi 10.3389/fneur.2026.1889198) | Same study as [C7]. |
| H8 | **Efficient Bayesian Uncertainty Estimation for nnU-Net.** Zhao Y. et al., MICCAI 2022 | Checkpoint-ensemble uncertainty for nnU-Net. Cardiac data only. |
| H9 | **MoFe loss.** IEEE TMI 2025 (doi 10.1109/tmi.2025.3526818) | Snippet mentions ECE/SCE together with missing modalities. **Not read (access blocked): an open risk.** |

---

## Phase 2 — Full-text closest-work audit

"Read" states the source actually read:

- **FT** — full text
- **FT-partial** — full text, but some sections could not be retrieved
- **ABS+** — abstract plus secondary summaries only

### 2.1 SIUM — Set-Inclusive Uncertainty Modeling (Baek et al., arXiv:2606.30374, 2026)

Read: FT (arXiv HTML).

- **Research question:** how to represent the uncertainty caused by missing modalities within the network, as a method contribution.
- **Data:** BraTS 2018 (199/29/57) and BraTS 2020 (219/50/100). Internal splits only.
- **Missingness:** all 15 subsets, via Bernoulli masking of modality embeddings.
- **Model:** RFNet backbone plus Gaussian embeddings.
- **Uncertainty:** embedding variance, used as a training regularizer.
- **Calibration:** ✗ (no ECE, Brier or reliability diagrams).
- **Failure detection, AURC/e-AURC:** ✗.
- **Confidence vs Dice:** ◐. Configuration-level only: mean variance vs summed DSC across the 15 configurations (Fig. 4), not per case.
- **ET/TC/WT separately:** ✔ for Dice. Uncertainty is analysed summed over regions.
- **Volume error:** ✗.
- **External data:** ✗.
- **Threshold transfer:** ✗.
- **Code:** github.com/atlas-sky/SIUM.
- **Limitations:** none stated.
- **Overlap with our study:** shares the idea that missing evidence should raise uncertainty, and shows this at the configuration level. It does **not** test whether uncertainty ranks *cases* by error, is calibrated, or transfers externally.

### 2.2 UAF-AIMM (Liu et al., Front. Neurosci. 2026)

Read: FT.

- **Research question:** an architecture for missing-T1c segmentation.
- **Data:** BraTS 2021 (7:3 split) and the BraTS 2023 validation set as "cross-dataset". Overlap with BraTS 2021 was not checked.
- **Missingness:** primarily −T1c. Extended analysis covers single removals and two pairs.
- **Model:** SegResNet with MR-Mapper, UAA and SITA.
- **Uncertainty:** MC-dropout (K=10), used internally to gate feature fusion.
- **Calibration:** ✗. **Failure detection, AURC:** ✗. **Confidence vs Dice:** ✗.
- **ET/TC/WT separately:** ✔ (Dice only).
- **Volume error:** ✗.
- **External data:** ◐ (BraTS 2023 validation; likely the same source population).
- **Threshold transfer:** ✗.
- **Seeds/statistics:** single runs, no CIs.
- **Code:** not available.
- **Limitations (stated):** T1c-centred; benchmark-only evidence; inference overhead; possible degenerate TTA.
- **Overlap with our study:** in the method, uncertainty is a *feature-weighting tool*, **not an evaluated output**. No overlap with a reliability evaluation.

### 2.3 Zenk et al. — Failure detection benchmark (MedIA 2025, arXiv:2406.03323)

Read: FT (arXiv HTML).

- **Research question:** which failure-detection methods work for 3D segmentation, and does confidence aggregation matter?
- **Data (brain):**
  - FeTS 2022 2D: 939 train / 313 test × 5 artificial corruptions.
  - BraTS 2019 3D: 193 train / 100 test, with an LGG-enriched population shift.
  - Other organs: heart, prostate, COVID CT, kidney.
- **Missingness:** ✗. All four sequences are always present.
- **Model:** U-Net-based.
- **Uncertainty and aggregation:** single, MC-dropout and ensemble; mean, non-boundary, patch and regression-forest aggregation; pairwise DSC; quality regression; Mahalanobis; VAE.
- **Calibration (ECE):** ✗. It is mentioned only as a "secondary goal".
- **Failure detection:** ✔. **AURC is the primary metric**, with Spearman correlation reported.
- **Risk:** 1 − DSC **averaged over classes**. There is **no per-region (ET) risk**.
- **Volume error:** ✗. **Threshold transfer:** ✗.
- **External data:** ✔ for some organs; for brain, only a population shift.
- **Code:** stated as public.
- **Limitations (stated):** image-level only; re-implementations; annotation shift.
- **Overlap with our study:** the **evaluation methodology** (AURC, pairwise-DSC). We adopt it. Our study differs in shift type (missing sequences), per-region risk and threshold transfer.

### 2.4 QCResUNet (Qiu et al., arXiv:2412.07156, MedIA per listing)

Read: FT-partial (Appendix E text not retrieved).

- **Research question:** learned prediction of segmentation quality at subject and voxel level.
- **Data:**
  - Internal: BraTS 2021 (667/333/251 per fold).
  - External: BraTS-SSA (40 cases) and WUSM (175 cases).
  - Also ACDC cardiac data.
- **Missingness:** the **segmentations being quality-controlled** were produced by nnU-Net, nnFormer and DeepMedic trained on **7 modality combinations**, to create quality diversity. The **QC network itself requires all 4 sequences**. The authors state that absent modalities cause a "dramatic drop in QC performance" (Appendix E; numbers not retrieved).
- **Calibration:** ✗.
- **Failure detection:** ◐. It is quality *regression* (MAE, Pearson r), not risk–coverage.
- **ET/TC/WT separately:** ✔.
- **Volume error:** ✗. **Threshold transfer:** ✗.
- **External data:** ✔ (BraTS-SSA, WUSM).
- **Code:** github.com/sotiraslab/QCResUNet.
- **Overlap with our study:** partial and important.
  1. External QC on BraTS-SSA already exists.
  2. The authors report that missing inputs break *their* QC model. This is **supporting evidence** for our problem.
  3. However, they do not study whether the **segmentation model's own uncertainty** remains a valid QC signal when inputs are missing.

### 2.5 QU-BraTS (Mehta et al., MELBA 2022)

Read: FT (arXiv HTML).

- **Research question:** how to rank voxel-wise uncertainty for BraTS.
- **Data:** BraTS 2020 (369 train / 125 validation / 166 test).
- **Missingness:** ✗.
- **Uncertainty:** team-dependent.
- **Calibration:** ✗ (ECE only mentioned).
- **Metric:** filtered-DSC / FTP / FTN AUC score. This is voxel-level, **not case-level** failure detection.
- **ET/TC/WT separately:** ✔. **Volume error:** ✗. **External data:** ✗. **Threshold transfer:** ✗.
- **Code:** github.com/RagMeh11/QU-BraTS.
- **Overlap with our study:** a voxel-level UQ score that we will report as a secondary metric for comparability.

### 2.6 Ruffle et al. (Brain Communications 2023)

Read: FT (Oxford Academic).

- **Research question:** can models trained on incomplete sequence sets segment tumours accurately?
- **Data:** BraTS 2021 (1,251 cases, 5-fold CV), plus an independent institutional cohort of 50 patients (11 scanners, 1.5T/3T, 10 post-operative cases).
- **Missingness:** a **separate nnU-Net per combination** (30 models reported).
- **Uncertainty, calibration, failure detection:** ✗.
- **ET/TC/WT separately:** ✔ (tissue-level Dice).
- **Volume:** ✔. ET volume agreement R² 0.953–0.976 without contrast [LITERATURE RESULT].
- **External data:** ✔ (n=50).
- **Code and weights:** github.com/high-dimensional/tumour-seg.
- **Overlap with our study:** accuracy and volume under missingness are **already established**. It provides no reliability evidence.

### 2.7 Öchsner et al. (arXiv:2602.20218; Frontiers in Neurology 2026)

Read: FT (arXiv PDF).

- **Research question:** does targeted FLAIR dropout preserve segmentation and volumetry without FLAIR, on external data?
- **Data:** BraTS 2021 **minus UPenn** (n=848) for development; the **UPenn-GBM subset of BraTS 2021** (n=403) as external test, with BraTS-provided preprocessing and expert-revised labels.
- **Missingness:** FLAIR only. Zeroed after preprocessing; dropout rate r ∈ {0, 0.35, 0.5}.
- **Model:** nnU-Net 3d_fullres, 1,000 epochs, 5-fold CV ensemble.
- **Uncertainty, calibration, failure detection:** ✗.
- **ET/TC/WT separately:** ✔.
- **Volume:** ✔. WT volume bias −45.6 mL without dropout vs 0.83 mL with dropout (Bland–Altman) [LITERATURE RESULT].
- **Statistics:** patient bootstrap (2,000 resamples); TOST with ±1.5 DSC-point margin.
- **Threshold transfer:** ✗.
- **Code:** github.com/LMU-NRAD/FLAIR-dropout (private during review per the preprint; the Frontiers version reportedly has no code link).
- **Limitations (stated):**
  - simulated missingness
  - single-institution external set drawn from BraTS
  - FLAIR only
  - no dedicated 3-sequence comparator in the preprint
- **Overlap with our study:** the **training design** (dropout nnU-Net, UPenn held out as external). **No reliability analysis.**
- **Key facts for our protocol:**
  - The UPenn cohort *inside* BraTS 2021 can serve as a held-out-institution test with identical preprocessing and label conventions.
  - Reported external Dice was high (overall median 95.0% with full input) [LITERATURE RESULT]. This suggests UPenn is a **mild** shift.

### 2.8 Pemberton et al. (Scientific Reports 2023)

Read: ABS+ (full text blocked).

- **Research question:** do BraTS models generalize to real-world multi-center data with missing sequences?
- **Data:** BraTS 2021 plus 480 clinical cases from 12 hospitals. External set: 158 GBM + 69 LGG.
- **Missingness:** real-world missing sequences; "Sparsified training".
- **Models:** DeepMedic, nnU-Net, NVIDIA-net.
- **Uncertainty, calibration, failure detection:** ✗, as far as the abstract shows.
- **ET/TC/WT separately:** ✔ (tumour classes).
- **Volume:** not stated in the abstract.
- **External data:** ✔.
- **Code:** unknown.
- **Overlap with our study:** accuracy under *real* missingness is established. Reliability is not evaluated (to confirm from the full text).

---

## Phase 3 — Falsification test

✔ = does it; ◐ = partially; ✗ = does not (in the text we could read).

| # | Test | SIUM | UAF-AIMM | Zenk | QCResUNet | QU-BraTS | Ruffle | Öchsner | Pemberton* | GoAT 2026 | MIUA 2026 | BMDS-Net |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Systematic reliability evaluation under missing sequences | ◐ config-level variance only | ✗ | ✗ | ◐ QC model breaks with missing inputs | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| 2 | Missing-sequence-specific calibration | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ (ECE on full input only) |
| 3 | Missing-sequence-specific failure detection | ✗ | ✗ | ✗ | ◐ (see 1) | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| 4 | AURC / risk–coverage under missing sequences | ✗ | ✗ | ✗ (AURC, no missingness) | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ (AURC, no missingness) | ✗ | ✗ |
| 5 | External validation of reliability under missingness | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| 6 | Comparison across T1/T1c/T2/FLAIR missingness | ✔ Dice; ◐ variance | ◐ Dice | ✗ | ✗ | ✗ | ✔ Dice | ✗ FLAIR only | ◐ | ✗ | ✗ | ✔ Dice |
| 7 | Region-specific reliability, especially ET | ✗ | ✗ | ✗ (mean-class risk) | ✔ QC per region | ✔ voxel UQ | ✗ | ✗ | ✗ | ✔ **(complete input)** | ✔ **(complete input)** | ✗ |
| 8 | Confidence vs Dice under missingness | ◐ config-level | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| 9 | External transfer of reliability thresholds | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| 10 | Volume-error failure detection under missingness | ✗ | ✗ | ✗ | ✗ | ✗ | ◐ volume accuracy | ◐ volume accuracy | ? | ✗ | ✗ | ✗ |

\*Pemberton: abstract only.

### Verdict

**The gap is not closed, but it is narrower than stated in [02](02_RESEARCH_GAP_ANALYSIS.md).**

What already exists:

- Accuracy under missingness, including volume error and external data [C6, C7, C8, H4].
- Case-level AURC failure-detection methodology [D2].
- **Region-specific (ET) calibration and AURC for nnU-Net deep ensembles on complete input** [H1, H2].
- Configuration-level evidence that missing inputs raise learned variance [C9].
- Evidence that a learned QC model fails when its inputs are missing [D4].

What we did not find (based on the search on 2026-09-27, with the gaps listed in [search_log.md](search_log.md)):

- (a) case-level failure detection and calibration of a segmentation model **conditioned on which sequence is missing**;
- (b) whether model uncertainty carries information **beyond the trivially known identity of the missing sequence**;
- (c) such reliability analysis on held-out-institution and external cohorts;
- (d) transfer of selective-prediction thresholds across domains under missingness.

**Largest residual risks:** the unread MoFe-loss paper (TMI 2025, H9), unscreened UNSURE/BrainLes 2025 and MICCAI 2026 proceedings, and a reviewer judging the work an "obvious combination" of H1/H2 with missing inputs.

---

## Phase 4 — Redesign

The original D1 question, "does reliability degrade under missingness?", has a near-obvious answer and is too close to combining H1 with [C6]/[C7]. It is therefore **sharpened** rather than abandoned.

**Key design insight.** At inference, *which* sequence is missing is **known** from the DICOM header or protocol. Any reliability signal must therefore beat a trivial quality-control rule that ranks cases by the identity of the missing sequence. This rule is the **missingness-indicator baseline**: the expected risk of each missingness condition, estimated on validation data.

No study we found tests uncertainty against this baseline. It turns "does uncertainty work?" into a falsifiable, non-trivial question with a meaningful negative outcome: if uncertainty does not beat the indicator, uncertainty-based QC adds nothing beyond reading the protocol.

**Revised research question.** When MRI sequences are missing at inference, does the ensemble uncertainty of a modality-dropout nnU-Net identify unreliable enhancing-tumour segmentations:

1. better than a rule based only on which sequence is missing;
2. consistently across missing-sequence conditions and tumour regions;
3. with operating thresholds that transfer from internal to held-out-institution and external cohorts?

This keeps the owner's core question and adds (1) as the discriminating test and (3) as the deployment test. It is not a new architecture.

---

## Phase 5 — Computational audit (ALL values are ESTIMATES)

Assumptions:

- Kaggle ≈ 30 GPU-h/week, ≤ 12 h/session, GPU = P100 16 GB or 2×T4, ~4 vCPU, ~20 GB persistent output. Verify at the start.
- nnU-Net v2 3d_fullres default: 250 iterations/epoch, batch 2, patch ~128³.
- nnU-Net's CPU-heavy augmentation may make Kaggle's ~4 vCPUs the bottleneck.
- Every ESTIMATE is replaced by a measured value from pilot EXP-001 before the budget is final.

| Item | Quantity | ESTIMATE |
|---|---|---|
| Training runs (minimum) | 2 arms (A full, B dropout) × 3 seeds = **6** | — |
| Time per epoch on T4/P100 | — | 3–6 min |
| Run at 1,000 epochs (nnU-Net default) | 6 runs | 50–100 h each → **300–600 GPU-h** → 10–20 weeks of free quota. **Not feasible on the free tier.** |
| Run at 250 epochs (`nnUNetTrainer_250epochs`) | 6 runs | 12–25 h each → **75–150 GPU-h** → 2.5–5 weeks; each run spans 2–3 sessions and needs resume |
| Parallelism | 2×T4: two runs per session, one per GPU | Up to ~2× wall-clock gain if CPU is not the bottleneck (uncertain) |
| Checkpoint interval | Reduce nnU-Net's `save_every` (default 50 epochs) to ~5 | Limits loss at a session cutoff |
| Preprocessing (nnU-Net plan + preprocess, ~700 dev cases) | Once, CPU | 1–3 h CPU; preprocessed size **30–60 GB**, above Kaggle's persistent output limit. Store as a **private** Kaggle dataset (if data terms allow) or regenerate per session. |
| Raw BraTS 2021 training data | 1,251 cases | ~12–16 GB compressed |
| Checkpoints | 6 × (weights + optimizer) | ~0.2–0.5 GB each → ≤ 3 GB. Not committed to git. |
| Inference: primary | ~753 cases (val ~85, internal test ~170, UPenn ~403, BraTS-Africa ≤95) × 5 conditions × 6 models, **no mirroring** | 3–8 s per case-model → **19–50 GPU-h** |
| Inference: 15-subset secondary | arm B only; val + internal test + Africa (~350) × 10 extra conditions × 3 models | **9–23 GPU-h** |
| Ensemble cost | Seeds serve as members | 0 extra training; pairwise-DSC computed on the fly |
| TTA (mirroring, 8×) | Exploratory; arm B; internal test; full and −T1c only | ~170 × 2 × 3 × 8 × 3–8 s ≈ **7–18 GPU-h** — only if budget remains |
| Storing full softmax | ~70 MB per case-condition-model (float16) | **Infeasible for all.** Compute metrics on the fly; store softmax for ≤20 pre-selected figure cases only. |
| Metrics / statistics / figures | CPU | Local laptop |
| **Total GPU (minimum design, 250 epochs)** | | **~100–220 GPU-h** → **4–8 weeks** of free Kaggle quota |

**Minimum scientifically sufficient design.** Six trainings. **No** per-subset models, because the question concerns a single deployable model. MC-dropout is **excluded**: nnU-Net has no dropout, and adding it would change the architecture being evaluated. Deep ensembles come from the seed runs.

**Option if paid GPU becomes available.** One full 1,000-epoch run per arm as an "anchor" sensitivity check that the 250-epoch schedule does not change conclusions. Not required.

---

## Correction notice (2026-09-27, pre-freeze audit)

See [13_PRE_FREEZE_AUDIT.md](13_PRE_FREEZE_AUDIT.md). The following statements above are superseded:

1. **UPenn count.** The UPenn-origin set inside BraTS 2021 training is **511 cases (site 1)**, not 403. The 403 figure counts only the `UPENN-GBM` collection label and misses 108 `UPENN-GBM_Additional` cases.
2. **H9 attribution.** DOI 10.1109/TMI.2025.3526818 is PNDC, not the MoFe loss (which is from SimMLM, arXiv:2507.19264).
3. **Falsification table.** It must now include **MMA-LTS (MICCAI 2026)**, which evaluates voxel-level calibration per missing-modality combination and per region. This closes item 2 ("missing-sequence-specific calibration") at the voxel level.
