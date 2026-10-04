# 02 — Research Gap Analysis

Each candidate gap is checked against the seven criteria in the project brief:

1. evidence of the problem
2. existing methods insufficient
3. scientifically meaningful
4. testable
5. public data
6. feasible compute
7. distinguishable from prior work

Citations are matrix IDs from [09_LITERATURE_MATRIX.md](09_LITERATURE_MATRIX.md).

**Important:** "insufficient" is judged from the literature found in a targeted, non-systematic search. Any gap below can be invalidated by a paper we have not found. Each gap therefore ends with the specific search that could falsify it.

---

## G1. Reliability of segmentation under missing MRI sequences is not characterized

- **Evidence the problem exists:**
  - Sequences are missing in routine practice. The BraTS organizers created a synthesis task because of this [A12], and real-world multi-center data contains missing sequences [C8].
  - Accuracy under missingness can be restored by dropout training [C7, C8], but a model that is *accurate on average* can still fail silently on individual cases.
- **Existing approaches:**
  - Accuracy-oriented missing-modality architectures [C1–C11].
  - Generic failure detection [D2, D3] and learned QC [D4], evaluated with *complete* inputs.
  - One method models variance from missing evidence [C9]; one uses uncertainty-gated fusion for missing T1c [C10].
- **Limitation:**
  - We found no evaluation of whether pixel uncertainty, case-level failure scores or calibration **remain valid when sequences are missing**, and whether they degrade differently per missing sequence (T1c absence is expected to hurt ET specifically).
  - [D2]'s shifts are corruptions and LGG population shift, not missing sequences.
  - [C9] evaluates internally on BraTS 2018/2020. Its reliability evaluation is to be checked in the full text.
- **Why it matters:** if a clinician is told "this segmentation is reliable" for a FLAIR-less or T1c-less scan and it is not, uncertainty is worse than useless. Missingness is a *known, observable* input condition, unlike generic shift, so it is a natural conditioning variable for QC.
- **Research question:** When MRI sequences are missing at inference, do standard uncertainty and failure-detection methods (MC-dropout, ensembles, TTA; mean/pairwise-DSC aggregation) keep their calibration and risk–coverage performance? Is degradation specific to the missing sequence and tumour sub-region?
- **Feasible experiment:**
  - Train dropout-nnU-Net-style models on de-duplicated BraTS 2021.
  - Evaluate all 15 subsets on an internal test set and external sets (UPenn-GBM manual subset, BraTS-Africa).
  - Measure AURC, ECE / reliability diagrams, and Spearman correlation between confidence and Dice, per subset and per region.
- **Expected contribution** [EXPECTED]: an empirical characterization. If a specific failure is found, a targeted remedy may follow, for example subset-conditioned calibration or missingness-aware failure scores. The remedy is secondary and must be justified by the characterization.
- **Novelty risk:** medium. [C9] and [C10] are close. A reviewer may see "evaluation under missing modality" as incremental unless the findings are non-obvious and the external validation is solid.
- **Falsifying search:** "calibration" OR "failure detection" OR "quality control" AND "missing sequence/modality" AND glioma, 2023–2026, in MICCAI and UNSURE workshop proceedings, MELBA, MedIA, TMI; plus the full texts of [C9, C10, D4].
- **Criteria:** 1 ✔ 2 ✔(provisional) 3 ✔ 4 ✔ 5 ✔ 6 ✔ 7 ◐

## G2. Specialized missing-modality architectures lack fair, external comparison against strong simple baselines

- **Evidence:**
  - [B2] shows architecture claims often collapse under fair baselines in general 3D segmentation.
  - Missing-modality papers mostly compare with each other on inconsistent BraTS 2018/2020 splits (W1, W2 in [01](01_RESEARCH_LANDSCAPE.md)).
  - Simple baselines are strong: [C6] per-subset nnU-Net; [C7] dropout nnU-Net, externally validated; [C8] sparsified training.
- **Existing approaches:** the architectures in [C1–C11]. We found no head-to-head comparison of those architectures against dropout-nnU-Net on external data.
- **Limitation:** it is unknown whether the claimed gains survive (a) a tuned nnU-Net-dropout baseline, (b) multiple seeds with paired statistics, and (c) external data.
- **Why it matters:** practitioners need to know whether the added complexity is justified. Resources are also being spent on a possibly illusory research line.
- **Research question:** Under identical data, splits, preprocessing, training budget and evaluation, do representative missing-modality architectures (e.g. RFNet, mmFormer, M3AE/ShaSpec, selected by code availability) outperform nnU-Net with modality dropout, internally and externally, across all 15 subsets?
- **Feasible experiment:** re-train 3–4 methods from official code plus baselines, with 3 seeds each. Evaluate with paired tests over patients.
- **Expected contribution** [EXPECTED]: a rigorous benchmark and a reproducible protocol. The finding could go either way, and both outcomes are publishable if done rigorously.
- **Novelty risk:** medium. Benchmark papers are accepted (e.g. [B2], [D2]), but reviewers expect breadth. Compute is the binding constraint (see [05](05_EXPERIMENTAL_DESIGN.md)).
- **Falsifying search:** "benchmark" / "revisit" / "fair comparison" + missing-modality brain tumour, 2024–2026.
- **Criteria:** 1 ✔ 2 ✔ 3 ✔ 4 ✔ 5 ✔ 6 ◐ (heavy) 7 ✔

## G3. Case-level failure detection for glioma segmentation under *real* acquisition shift is under-tested

- **Evidence:**
  - [D2]'s brain-tumour shifts are synthetic corruptions (FeTS) and a grade shift (BraTS 2019).
  - BraTS-Africa shows real acquisition/population shift [A5, E3].
  - [D4] (learned QC) does test on BraTS-SSA, so this gap is **partially closed**.
- **Existing approaches:** [D2] ensemble + pairwise-DSC; [D3] spatial aggregation; [D4] learned QC regressors.
- **Limitation:**
  - Region-specific failure (ET vs WT) is not well covered.
  - Clinically defined failures (e.g. volume error that changes a RANO-style assessment) are not well covered either.
  - Nobody has compared unsupervised confidence scores against learned QC under the *same* real shift.
- **Research question:** On real external glioma cohorts, which failure-detection approach (ensemble pairwise-DSC, aggregated pixel uncertainty, learned QC) best ranks cases by clinically relevant error (per-region Dice, absolute volume error), and does the ranking transfer from internal to external data?
- **Novelty risk:** **high.** [D2, D3, D4] come from strong groups and cover much of this space. A contribution would need a clearly different angle, such as clinical failure definitions or transfer of QC thresholds.
- **Criteria:** 1 ✔ 2 ◐ 3 ✔ 4 ✔ 5 ✔ 6 ✔ 7 ◐/✗

## G4. Pre-operative models on post-treatment MRI: accuracy and reliability under label-schema and anatomy shift

- **Evidence:** BraTS 2024 introduced post-treatment glioma segmentation with a resection-cavity label [A4]. Large post-treatment data now exists [A11].
- **Existing approaches:** challenge submissions trained directly on post-treatment data; "combined pre/post" nnU-Net training (medRxiv 2023, see search record); architecture benchmarks [B7].
- **Limitation:** there is little evidence on whether *reliability signals* flag the characteristic post-treatment failures (cavity vs necrosis confusion, treatment-related enhancement). The benefit of pre/post mixing on reliability is also unknown.
- **Research question:** Do uncertainty and failure-detection signals identify post-treatment-specific errors, and does training-data composition (pre-only, post-only, mixed) change reliability as well as accuracy?
- **Novelty risk:** medium. The area is new but moving quickly (BraTS 2024–2025).
- **Practical risks:**
  - label harmonization (RC/SNFH vs the pre-op schema)
  - data access terms for BraTS 2024 / MU-Glioma-Post, to verify
  - the larger dataset raises compute
- **Criteria:** 1 ✔ 2 ◐ 3 ✔ 4 ✔ 5 ◐ (verify access) 6 ◐ 7 ◐

## G5. Test-time adaptation may improve Dice while silently degrading reliability

- **Evidence:**
  - TTA is increasingly proposed for brain-tumour shift [E1, C10].
  - A large benchmark finds TTA methods can deteriorate under strong inter-center shift [E2].
  - Entropy-minimizing TTA [E5] directly manipulates the confidence signal that failure detection relies on (a mechanistic argument, not yet an observation).
- **Existing approaches:** TTA papers report Dice/HD95. [E2] benchmarks accuracy across paradigms.
- **Limitation:** we found no evaluation of whether TTA preserves calibration and failure detectability for brain-tumour segmentation. This is a *plausible* but unconfirmed gap.
- **Research question:** On BraTS-Africa and other external cohorts, does applying TTA (entropy minimization, normalization-statistics adaptation, augmentation-consistency) change calibration and AURC, and can TTA-induced overconfidence hide failures?
- **Novelty risk:** medium. There is general-ML literature on TTA calibration (to be searched), and applying it to BraTS may be seen as incremental.
- **Criteria:** 1 ◐ 2 ◐ 3 ✔ 4 ✔ 5 ✔ 6 ✔ 7 ◐

---

## Gaps considered and rejected

| Candidate | Reason rejected |
|---|---|
| New attention/transformer/Mamba backbone for BraTS | Saturated; fails criterion 2 ([B2]). |
| New missing-modality fusion architecture | Saturated [C11]; simple baselines strong [C6–C8]. |
| MC-dropout on BraTS | Saturated [D1, D5, D6]. |
| BraTS-Africa domain adaptation for accuracy | Crowded [E3]. |
| Federated training | Requires multi-node infrastructure; FeTS already large-scale [E4]; not reproducible on free-tier GPUs. |
| Foundation-model pretraining | Compute far exceeds budget [F1]. Using released foundation weights as a baseline remains possible. |
| Explainability maps | No clear falsifiable hypothesis linked to segmentation quality in our setting. |
