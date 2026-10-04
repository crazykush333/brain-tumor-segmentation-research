# 13 — Final Pre-Freeze Audit (adversarial)

| Field | Value |
|---|---|
| Audit date | **2026-09-27** |
| Object | [FINAL_RESEARCH_PROTOCOL.md](archive/FINAL_RESEARCH_PROTOCOL_v0.5_SUPERSEDED.md) v0.1 (not modified by this audit) |
| Mandate | Attempt to falsify the research question. Audit statistics, datasets and compute. |
| **Verdict** | **B. PROTOCOL REQUIRES REVISION** |

Tag legend used throughout:

- **[VERIFIED]** — checked against the primary source (full text, dataset metadata file or official page).
- **[LIT]** — a verified literature result.
- **[ESTIMATE]** — a projection, not a measurement.
- **[INFERENCE]** — our reasoning from verified facts.
- **[UNRESOLVED]** — could not be established.

`FINAL_PRE_FREEZE_AUDIT.md` was **not** created, because the verdict is not "ready for freeze" (instruction Phase 8).

---

## 1. Executive conclusion

1. **The research question is not invalidated.** No study found performs case-level failure detection under missing MRI sequences. None tests whether uncertainty adds information beyond the known identity of the missing sequence, and none tests reliability or threshold transfer to held-out-institution or external data under missingness.
2. **One component is now closed by prior work.**
   - *Lee et al., "Missing Modality-Aware Calibration for Trustworthy Brain Tumor Segmentation", MICCAI 2026* (MMA-LTS) already evaluates **voxel-level calibration (ECE) per missing-modality combination and per region (WT/TC/ET)** [VERIFIED, full text].
   - It also shows that conditioning calibration on *which* modality is missing, rather than *how many*, improves ECE.
   - Consequences:
     - our secondary endpoint S4 becomes a replication;
     - hypothesis H2 is largely pre-empted at the voxel level;
     - "missingness-conditioned calibration" can no longer be claimed as a contribution in any form.
3. **One methodological flaw was found in the primary hypothesis H-REL.**
   - H-REL compares pooled AURC of U1 against the missingness indicator I, pooled across the five C5 conditions.
   - A 2026 UNSURE paper (Joham et al.) shows that **pooled risk–coverage rankings reward ordering groups by difficulty and can mask within-group failure detection** [VERIFIED, full text]. The pooled comparison therefore mixes two things: between-condition ordering (which I encodes by construction) and within-condition discrimination (which I cannot provide).
   - Its outcome also depends on the arbitrary equal weighting of conditions.
   - The question "does uncertainty add information beyond the missing-sequence identity?" is answered cleanly **only by a within-condition analysis**. That analysis is currently the secondary endpoint S11.
4. **A dataset fact in the protocol is wrong.**
   - BraTS 2021 training contains **511** UPenn-origin cases (site 1): 403 labelled `UPENN-GBM` plus 108 labelled `UPENN-GBM_Additional`. The protocol's figure was 403 [VERIFIED, official TCIA crosswalk].
   - Excluding only the 403 would leave 108 same-institution cases in development, i.e. site leakage.
5. **The smallest defensible modification:**
   - promote within-condition failure discrimination to the single primary reliability endpoint;
   - demote H-SEG and the pooled comparison to supporting/secondary roles;
   - redefine the held-out institution as all 511 site-1 cases;
   - reframe voxel-ECE analyses as a replication of MMA-LTS;
   - fix the threshold-transfer definition.

---

## 2. Literature searched (2026-09-27)

Full query and source record: [search_log.md](search_log.md), round 3.

| Source | Method | Coverage |
|---|---|---|
| **MICCAI 2026 main** | Full BibTeX title list from papers.miccai.org (1,165 papers), keyword-screened, then manual reading of hits | Complete title screen |
| **MICCAI 2026 satellite events** (incl. UNSURE 2026, BrainWorks, BraTS 2026 tracks) | Full title list (1,607 papers). All **38 UNSURE 2026** titles and all BrainWorks/BraTS titles listed and read. | Complete title screen |
| **MICCAI 2025 main** | Full title list (1,027 papers), keyword-screened | Complete title screen |
| **UNSURE 2025** (LNCS 16166) | All **22** chapter titles via Crossref | Complete |
| **BrainLes 2023 / BraTS 2023 proceedings** (LNCS, pub. 2024) | All 16 + 36 chapter titles via Crossref | Complete |
| **BraTS 2025 / BrainLes 2025 proceedings** ("Segmentation, Classification, and Synthesis for Brain Tumors and TBI", 2 vols, 2026) | All 48 + 33 chapter titles via Crossref | Complete |
| **BrainLes 2024 / BraTS 2024 proceedings** | Not found in Crossref, Springer search or researchr | **[UNRESOLVED] — could not be screened** |
| **MIDL 2025** (PMLR v301, 110 papers) and **MIDL 2026** (PMLR v315, 221 papers) | Full title lists, keyword-screened | Complete title screen |
| **MELBA 2025–2026** | 120 paper titles (2025:001–060, 2026:001–060) | Complete title screen |
| **MoFe-loss / DOI 10.1109/TMI.2025.3526818** | DOI resolution plus full text | Resolved; see §3 (a correction) |
| Targeted web searches | ~15 new query combinations | See log |

**Limitations:**

- Google Scholar, dblp and OpenReview blocked automated access. MIDL was covered via PMLR instead.
- Keyword screening of large title lists could miss papers whose titles use none of the terms "missing / incomplete / modality / uncertainty / calibration / failure / reliability / quality control / selective / risk / conformal / trust".
- BrainLes/BraTS 2024 remains unscreened.
- Journal articles are covered only through web search, not by exhaustive database queries.

---

## 3. Papers that came closest (full-text audit)

"Read" states what was read: FT = full text; ABS = abstract only; UNVERIFIED = no access.

### 3.1 MMA-LTS — Lee S., Kim H., Hong S., Han D., Yi M. Y. *Missing Modality-Aware Calibration for Trustworthy Brain Tumor Segmentation.* MICCAI 2026. [FT]

Sources: https://papers.miccai.org/miccai-2026/0659-Paper1236.html (paper and reviews); full-text PDF read.

- **Relevant experiment:** post-hoc voxel-wise temperature scaling conditioned on a learnable modality-availability token and a voxel difficulty score. It is evaluated on all **15 combinations** × **WT/TC/ET**.
- **Data:** BraTS 2020 (219/50/100) and FeTS 2024 (1,251 cases; 1000/125/126). FeTS 2024 has the same case count as BraTS 2021 training.
- **Missingness:** simulated. ModDrop during calibrator training.
- **Backbones:** DC-Seg, RobustSeg, mmFormer.
- **Metrics:** DSC and **ECE (foreground voxels, 10 bins, averaged over volumes)**. Baselines include TS, DirS, LTS, SelS, MC-dropout, mL1-ACE and SDC.
- **Level:** **voxel-level only.** There is no case-level confidence, no AURC and no failure detection.
- **External data:** none; reviewers also note no external validation and no statistical testing. **No site holdout.**
- **Missing-sequence identity:** *used as a conditioning input* for calibration. An ablation shows an availability token beats a count-based token for ECE. This is **not** a failure-ranking baseline.
- **Within-condition reliability:** not evaluated.
- **Threshold transfer:** not evaluated.
- **Code:** N/A.
- **Stated future work:** extending validation, statistical testing, clinical validation.
- **Effect on our study:** closes voxel-ECE per condition and region (our S4 and H2 at voxel level) and missingness-conditioned calibration (the old D1 remedy idea). It does **not** close case-level failure detection, within-condition discrimination, comparison to an indicator rule, external/held-out-institution transfer, or thresholds.

### 3.2 SimMLM / MoFe loss — Li S., Chen C., Han J. arXiv:2507.19264 (listed as ICCV 2025 by a secondary source; venue to verify) [FT]

- **Correction:** our earlier documents attributed "MoFe loss" to DOI 10.1109/TMI.2025.3526818. That was **wrong**.
  - MoFe ("More vs. Fewer") loss belongs to SimMLM.
  - The TMI DOI is PNDC (§3.3).
- **Data and missingness:** BraTS 2018, all 15 subsets. Evaluated on the official BraTS 2018 validation set (66 cases).
- **Calibration:** **ECE/SCE per region (ET/TC/WT), averaged across the 15 configurations**. There is no per-configuration breakdown.
- **Not evaluated:** case-level uncertainty, AURC, external data, indicator baseline.
- **Effect on our study:** partial overlap on region-specific calibration under missingness (aggregated only).

### 3.3 PNDC — Qiu Y. et al. *Does Adding a Modality Really Make Positive Impacts in Incomplete Multi-Modal Brain Tumor Segmentation?* IEEE TMI 2025, DOI 10.1109/TMI.2025.3526818 [ABS; full text **UNVERIFIED**]

- IEEE Xplore and PubMed were not accessible.
- Per the abstract, "double calibration" is a **region-level fusion correction** (Reverse Audit / Forward Checksum), not probabilistic calibration or failure detection.
- **All reliability columns are marked UNVERIFIED.** This is a residual risk, judged low from the abstract.

### 3.4 Joham S. J., Guglielmo G., Kozinski M., Urschler M. *Foundation Model and Radiomics Distance Scores for Post-Hoc Segmentation Failure Detection.* UNSURE 2026 [FT]

- Data: prostate and hippocampus MRI; no missing modalities.
- **Key methodological finding:** they report both pooled E-AURC and mean within-site E-AURC. They show that pooled evaluation "can reward between-site" difficulty ordering and mask within-site failure detection.
- **Effect on our study:** does not overlap the research question. It **directly exposes the weakness of pooled H-REL** (§8).

### 3.5 Badr M. A. M. et al. *Reliability, Not Accuracy, Is the Bottleneck in AI-assisted Post-Treatment Glioma Segmentation: Region-Aware Recalibration and Risk-Controlled Triage.* UNSURE 2026 [FT]

- Data: BraTS 2024 post-treatment glioma, using the public winning-ensemble checkpoints.
- Contribution: region-conditional (resection-cavity) calibration, plus distribution-free risk-controlled triage whose realized risk is tested on held-out patients.
- **No missing sequences** (full-text search).
- **Effect on our study:** establishes precedent for region-aware risk-controlled triage in glioma. It is a methodological neighbour; the research question does not overlap.

### 3.6 Ajit A. *Guarantees That Survive a Missing Scan: Modality-Conditional Conformal Prediction for Multimodal Medical Diagnosis.* MLMI 2026 [ABS]

- **Classification**, not segmentation (mammography and cardiac CT).
- Stratifies conformal calibration by the modality-availability pattern.
- **Effect on our study:** a conceptual analogue of conditioning on missingness identity, in a different task. It should be cited as related work.

### 3.7 Previously audited papers (details in [12](12_PRE_PROTOCOL_AUDIT.md) §2)

- SIUM (MICCAI 2026, confirmed in the MICCAI 2026 list) [FT]
- UAF-AIMM [FT]
- Zenk et al. 2025 [FT]
- QCResUNet [FT-partial; Appendix E numbers UNVERIFIED]
- QU-BraTS [FT]
- Ruffle 2023 [FT]
- Öchsner 2026 [FT]
- BraTS-GoAT reliability study (MICCAI 2026 satellite) [FT]
- Wong et al. MIUA 2026 [FT]
- BMDS-Net [FT]
- GlioMODA [ABS+]
- **Pemberton 2023:** now **[FT via Europe PMC XML]**. It contains no uncertainty, calibration or failure-detection analysis; "quality control" refers only to visual checks of the data.

### 3.8 Screened and judged non-overlapping (title/abstract)

These are accuracy-only or unrelated to reliability under missingness:

- MICCAI 2026: SAR-Net, HK-Fuse, MoCaf-Mamba, BrainAnytime
- MICCAI 2026 satellite: BrainWorks "Reliability-aware Multimodal Fusion" (FT: complete inputs, fusion method), BraTS-GoAT 013 (modality-dropout ensembling, accuracy)
- MICCAI 2025: MST-KDNet, DC-Seg, IM-Fuse, FedAMM
- BraTS 2025 proceedings: BRAIN-CATS (calibration-aware training on 60 BraTS-Africa cases, no missingness), "Enabling Uncertainty Measurement… BraTS 2025 Pediatrics" (voxel ensembles, no missingness), MAPS-Glioma
- UNSURE 2025: all 22 titles
- MIDL 2025/2026 and MELBA 2025/2026: no missing-modality reliability paper

---

## 4. Full falsification matrix

Values: **Y** = directly evaluated; **P** = related but not equivalent; **N** = not evaluated; **U** = could not verify.

Columns:

- **A** accuracy under missing sequences
- **B** volume accuracy/error under missing sequences
- **C** case-level uncertainty under missing sequences
- **D** case-level failure detection under missing sequences
- **E** AURC / risk–coverage under missing sequences
- **F** missing-sequence-specific calibration
- **G** region-specific reliability, especially ET
- **H** within-condition reliability
- **I** comparison against a missingness-indicator baseline
- **J** external validation of reliability under missingness
- **K** held-out-institution reliability
- **L** transfer of a reliability threshold to another domain
- **M** comparison across T1/T1c/T2/FLAIR missingness
- **N** volume-error failure detection under missingness
- **O** uncertainty information beyond knowing which modality is missing

| Paper | Read | A | B | C | D | E | F | G | H | I | J | K | L | M | N | O |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **MMA-LTS (MICCAI 2026)** | FT | Y | N | N | N | N | **Y** (voxel ECE ×15 combos) | **Y** (voxel, per region, under missingness) | N | P (ablation: availability vs count token, for ECE only) | N | N | N | **Y** | N | P (for calibration, not failure ranking) |
| SimMLM / MoFe (2025) | FT | Y | N | N | N | N | P (ECE averaged over 15 combos) | P (per region, aggregated) | N | N | N | N | N | P | N | N |
| PNDC (TMI 2025) | ABS | Y | U | U | U | U | U | U | U | U | U | U | U | U | U | U |
| SIUM (MICCAI 2026) | FT | Y | N | P (config-level variance) | N | N | N | N | N | N | N | N | N | Y | N | N |
| UAF-AIMM (2026) | FT | Y | N | N | N | N | N | N | N | N | N | N | N | P | N | N |
| BMDS-Net (2026) | FT | Y | N | N | N | N | N (ECE full input only) | N | N | N | N | N | N | Y | N | N |
| QCResUNet | FT-partial | P | N | N | P (QC targets from missing-input models; QC net needs 4 inputs) | N | N | P (full input) | N | N | P (external QC, full input) | N | N | N | N | N |
| Zenk 2025 | FT | N | N | N | N | N | N | N (mean-class risk) | N | N | N | N | N | N | N | N |
| BraTS-GoAT reliability (2026) | FT | N | N | N | N | N | N | Y (complete input) | N | N | N | N | N | N | N | N |
| Wong, MIUA 2026 | FT | N | N | N | N | N | N | Y (complete input) | N | N | N | N | N | N | N | N |
| QU-BraTS | FT | N | N | N | N | N | N | P (voxel, complete) | N | N | N | N | N | N | N | N |
| Joham, UNSURE 2026 | FT | N | N | N | N | N | N | N | P (within-site, no missingness) | N | N | P (multi-site) | N | N | N | N |
| Badr, UNSURE 2026 | FT | N | N | N | N | N | N | Y (cavity, complete) | N | N | N | N | P (held-out patients, same domain) | N | N | N |
| Ajit, MLMI 2026 | ABS | P (classification) | N | P (classification) | N | N | P (conformal, per pattern) | N | P | N | N | N | N | N | N | P |
| Ruffle 2023 | FT | Y | Y | N | N | N | N | N | N | N | N | N | N | Y | N | N |
| Öchsner 2026 | FT | Y (FLAIR only) | Y | N | N | N | N | N | N | N | N | N | N | N | N | N |
| Pemberton 2023 | FT | Y | N (not found) | N | N | N | N | N | N | N | N | N | N | P | N | N |
| GlioMODA 2026 | ABS+ | Y | Y | N | N | N | N | N | N | N | N | N | N | Y | N | N |

---

## 5. What prior literature already establishes [LIT]

- **Accuracy and volumetry under missing sequences** can be largely recovered by per-subset or dropout-trained nnU-Nets, including on external data (Ruffle, Öchsner, Pemberton, GlioMODA).
- **Voxel-level calibration degrades in a combination-specific way.** The identity of the missing modality matters more than the count, and conditioning a post-hoc calibrator on availability reduces ECE per region (MMA-LTS; internal BraTS 2020 / FeTS 2024 only).
- **Region-specific ET miscalibration can hide behind good global metrics** on complete inputs (Wong MIUA 2026; BraTS-GoAT reliability 2026).
- **Ensemble pairwise-DSC is a strong case-level failure detector** on complete inputs under synthetic or population shift (Zenk 2025).
- **Pooled risk–coverage evaluation can reward between-group difficulty ordering** rather than within-group detection (Joham, UNSURE 2026).

## 6. What remains genuinely untested

Based on the searches in §2 and their stated limitations:

1. Whether **case-level** uncertainty identifies ET segmentation failures **within a fixed missing-sequence condition**. This is the information beyond the known missingness identity (columns H, O).
2. How that within-condition discrimination varies **across which sequence is missing**, especially −T1c for ET (columns D/E × M).
3. Whether case-level reliability under missingness holds on a **held-out institution** and an **external population** (columns J, K).
4. Whether **operating thresholds** chosen on internal validation keep their selective risk and coverage under those shifts (column L).
5. **Volume-error-defined failures** under missingness (column N).

Items 1–4 are scientifically meaningful:

- In deployment, the missing sequence is known. A QC signal is only useful if it separates good from bad cases *given* that knowledge.
- Voxel-ECE improvements (MMA-LTS) do not show case-level triage utility. Maganti 2026 and Wong 2026 argue that calibration and decision utility can diverge.

---

## 7. Dataset verification

| # | Item | Finding | Status |
|---|---|---|---|
| 1 | BraTS 2021 → UPenn mapping | The official TCIA crosswalk `BraTS2021_MappingToTCIA.xlsx` (78 KB, IDs only; inspected in scratch space, not committed) gives source collection **and site ID** for every case. The CBICA page describes a mapping for TCGA/IvyGAP/CPTAC only; the TCIA crosswalk is the complete one. | **VERIFIED** |
| 2 | UPenn-origin cases in BraTS 2021 **training** | **511**: `UPENN-GBM` 403 + `UPENN-GBM_Additional` 108, all **site 1**. A further 44 UPenn cases are in the (unlabelled) validation cohort. Development without site 1 = **740**. Site 18 (UCSF) = 382 training cases; the remaining 22 sites contribute 358. | **VERIFIED** |
| 2b | Öchsner et al. external set | 1,251 − 403 = 848 exactly matches their development n. This implies the 108 `UPENN-GBM_Additional` site-1 cases stayed in their development set. | **INFERENCE** (possible same-institution leakage in [C7]; do not repeat it) |
| 3 | BraTS-Africa adult glioma with public labels | TCIA metadata `BraTS-Africa_TCIA_datainfo_v2.xlsx` has two sheets, **"95 Glioma"** and **"51 OtherNeoplasms"**. TCIA states that labels are provided for all 146. Glioma cases span 4 centres (NKDC 48, CRV 28, MEDHUB 14, LASUTH 5) and 3 scanner models. Label count per case: 3 labels = 89, 2 = 5, 1 = 1 (one row blank; to confirm on files). | **VERIFIED (metadata)**; file-level confirmation at the data milestone |
| 4 | Why 60 / 75 / 95 | **60:** labelled training cases released for the 2023 challenge (secondary reports). **75:** public cases during the challenge after 20 were withheld for testing (PMC RYAI paper). **95:** all glioma cases in the post-challenge TCIA release. | **PARTIALLY VERIFIED** (the 60 is from secondary sources) |
| 5 | Eligible under our criteria | Adult glioma with 4 sequences and a label: **up to 95**. Cases with no ET label are *eligible* but must be handled by the pre-specified empty-mask Dice rule. The 51 non-glioma cases are excluded. | VERIFIED (metadata) |
| 6 | Label convention | BraTS 2023-style: **1 = NETC, 2 = SNFH, 3 = ET** (BraTS 2023 challenge descriptions, including BraTS-Africa). BraTS 2021 uses 1 = NCR, 2 = ED, **4** = ET. | VERIFIED (documentation); confirm on files |
| 7 | BraTS-Africa ↔ BraTS 2021 overlap | Different institutions (Nigeria vs the 2021 contributing sites). No Nigerian site appears in the 2021 crosswalk's named collections. | **INFERENCE**: overlap very unlikely; the image-hash check stays in the protocol |
| 8 | RANO 2.0 volumetric threshold | RANO 2.0 (Wen et al., JCO 2023) defines volumetric **progression as ≥ 40% increase** and **partial response as ≥ 65% decrease** in tumour burden (confirmed via AJNR 2024 and KJR 2024 summaries; primary text not read). | VERIFIED (secondary) |
| 9 | Is 40% adequate as a segmentation-failure threshold? | The 40% threshold is a *longitudinal change* criterion, not a segmentation-error criterion. A cross-sectional error of ≥ 40% could by itself cross the progression threshold in a paired comparison, so it is **defensible as "RANO-motivated", not "RANO-defined"**. The ≥ 1 mL minimum ET volume is our own choice, not RANO. | **Change required** (§11) |

---

## 8. Statistical audit

| # | Question | Finding | Required action |
|---|---|---|---|
| 1 | Is H-REL coherent? | Formally yes: the two rankers share predictions, so ΔAURC = Δe-AURC. **But the pooled comparison conflates** between-condition ordering (which I captures by construction) with within-condition discrimination (which I cannot provide, since I is constant within a condition). It does not isolate "information beyond missingness identity" [§3.4]. | Replace as primary (see 7–8). |
| 2 | Patient-level bootstrap for AURC(U1) vs AURC(I)? | Appropriate: paired, clustered by patient, non-parametric for a non-linear statistic. Percentile CI with BCa sensitivity is acceptable. | Keep for all AURC contrasts. |
| 3 | Pooling C5 defensible? | Only as a **hypothetical deployment mixture**. Equal weights are arbitrary and the result depends on them. | Demote pooled analysis to secondary. Add a pre-specified mixture-weight sensitivity (e.g. 80% full / 5% each single-missing). |
| 4 | Resampling correctly specified? | Yes: all conditions of a patient are resampled together. For within-condition endpoints, compute the per-condition AURCs on each bootstrap sample, then average. | State explicitly in v1.0. |
| 5 | 97.5% CI for α = 0.025 co-primary | Correct for Bonferroni over two co-primaries. | If H-SEG is demoted (item 7), the single primary uses α = 0.05 and a 95% CI. |
| 6 | Multiplicity families | Families are internally correct, but FWER is not controlled across secondary families. H2 overlaps MMA-LTS findings. | Declare that secondary families are Holm-controlled within family only and are interpreted as supportive. Reclassify H2 as a replication (descriptive CIs). |
| 7 | H-SEG co-primary? | It replicates [C6–C8] and spends half the α. | **Demote to supporting** (no α). Keep the full-input TOST as a sanity check. |
| 8 | Promote S11? | **Yes.** It is the only endpoint that directly tests "beyond missingness identity". Within a condition, I is constant, so its expected AURC equals the condition's mean risk (random ranking). | Promote to the **single primary reliability endpoint** (§9). |
| 9 | Indicator leakage | None, provided I's per-condition risks are estimated on validation only (as specified). | Keep. Also report I's transfer error (validation risk vs realized external risk per condition). |
| 10 | 80% validation coverage | A design choice ("refer 1 in 5 cases"), not a clinical standard. | Keep 80% as primary, with 70% and 90% sensitivity. Label it as a design choice. |
| 11 | Threshold-transfer definition | Flawed: it treats the validation selective risk as fixed, ignoring its sampling error (validation n ≈ 74). It also ignores coverage drift. | Define two quantities, each with a CI from independent bootstraps of both sets: **Δrisk** (target − validation selective risk) and **Δcoverage**. "Unsafe transfer" = Δrisk CI entirely > 0. "Inefficient transfer" = Δcoverage CI entirely < 0. |
| 12 | Redundant endpoints | Several endpoints add analysis without answering the question. | Remove the QU-BraTS score, lesion-wise Dice and mirroring-TTA from the plan (or mark optional/unreported). Keep U3 exploratory. S4 ECE becomes a replication of MMA-LTS in our setting. S10 (C15) is limited to the internal test set. |

**Additional issue: small-group precision.** Within-condition AURC on about 148 internal-test patients per condition is estimable. Per-condition estimates on BraTS-Africa (≤ 95 cases) will be imprecise and should be reported with CIs only.

---

## 9. Phase 9 — revision (smallest defensible modification)

| # | Item | Content |
|---|---|---|
| 1 | Which prior paper closes which part | MMA-LTS: voxel-level calibration per missing combination and region (F, G, M), including missingness-conditioned calibration. SimMLM: aggregated region ECE under missingness. Joham 2026: pooled vs within-group ranking methodology. Accuracy and volumetry: Ruffle, Öchsner, Pemberton, GlioMODA. |
| 2 | What remains unique | Case-level ET failure discrimination **within** each missing-sequence condition; its variation by missing sequence; held-out-institution and external transfer of discrimination and of operating thresholds under missingness; volume-defined failures. |
| 3 | Scientifically meaningful? | **Yes.** The missing sequence is known at deployment, so only within-condition information is actionable for case-level QC. Voxel-ECE gains do not demonstrate triage utility. |
| 4 | Smallest defensible modification | Re-target the primary reliability endpoint from the pooled U1-vs-I comparison to within-condition discrimination. Demote H-SEG. Fix the held-out-institution definition and threshold transfer. Reframe the voxel-ECE work as replication. **No new models and no new training runs.** |
| 5 | **Revised research question** | When MRI sequences are missing at inference, does the case-level ensemble uncertainty of a modality-dropout nnU-Net discriminate unreliable enhancing-tumour segmentations **within a given missing-sequence condition**, i.e. beyond what the known identity of the missing sequence provides? How does this vary with which sequence is missing, and do the discrimination and operating thresholds transfer to a held-out institution and an external population? |
| 6 | **Revised primary hypothesis (single, α = 0.05)** | **H-W.** On the internal test set, for the modality-dropout ensemble, the mean over the five C5 conditions of the within-condition ET ΔAURC is < 0. Within-condition ΔAURC = AURC_c(U1) − AURC_c(I), and AURC_c(I) equals that condition's mean ET risk. Test: patient-bootstrap 95% CI entirely below 0. |
| 7 | **Revised primary endpoint** | Mean within-condition ET ΔAURC (as above), reported with each per-condition component. **Key secondaries:** the −T1c-condition component; the same endpoint on the held-out institution and BraTS-Africa; the threshold transfer Δrisk and Δcoverage; pooled AURC(U1) vs AURC(I) and vs a lexicographic "I-then-U1" ranker, with mixture-weight sensitivity. **Supporting (no α):** H-SEG, full-input TOST, voxel ECE/Brier (replication of MMA-LTS), volume-failure AURC. |
| 8 | Remove | Mirroring-TTA exploratory arm; QU-BraTS score; lesion-wise Dice; H2 as a confirmatory hypothesis (becomes descriptive replication); C15 inference outside the internal test set; any missingness-conditioned calibration remedy (already excluded). |
| 9 | Add (no extra training) | Within-condition analysis (becomes primary); lexicographic "I-then-U1" ranker; mixture-weight sensitivity; two-sided threshold-transfer definition; held-out institution = **all 511 site-1 cases**; reporting of I's own transfer error; exact empty-ET handling rule for BraTS-Africa cases with fewer than 3 labels. |

**Novelty risk after revision.** The contribution is a reliability evaluation (not a method), sitting between MMA-LTS (voxel calibration under missingness) and Zenk / BraTS-GoAT (case-level failure detection on complete inputs). A reviewer may still call it incremental. It is defensible only if the within-condition and transfer results are reported rigorously, including null or negative findings.

---

## 10. Compute audit

**Findings:**

- **Training cost is essentially unchanged by the smaller development set.** nnU-Net's epoch is a fixed number of iterations (250), not a pass over the data. Six runs × 250 epochs remains **75–150 GPU-h [ESTIMATE, unmeasured]**.
- **Inference grows:** the held-out institution is now 511 cases instead of 403.
  - Primary inference: val (~74) + internal test (~148) + held-out institution (511) + Africa (≤ 95) ≈ 828 cases × 5 conditions × 6 models ≈ 24,800 case-model passes → **21–55 GPU-h [ESTIMATE]**.
  - Reduction option: run arm A only on the internal test set and on full/−T1c/−FLAIR externally → about −35%.
- **C15 (internal test only, arm B):** 148 × 10 × 3 ≈ 4,400 passes → **4–10 GPU-h [ESTIMATE]**.
- **Total:** about **100–215 GPU-h [ESTIMATE]**, still roughly 4–8 weeks of free Kaggle quota. The Kaggle quota and session limits themselves were not re-verified today.

**Executability** [INFERENCE]: plausible but **not established**. The main unknowns are:

- CPU-bound nnU-Net augmentation on ~4 vCPUs;
- storage of preprocessed data (30–60 GB [ESTIMATE]) versus Kaggle output limits;
- **the licence question:** whether BraTS 2021 data obtained under the TCIA Restricted License Agreement may be re-hosted even as a *private* Kaggle dataset **[UNRESOLVED; must be answered before M5]**.

**EXP-001 must measure:**

1. seconds/epoch on P100, on a single T4, and for two concurrent runs on 2×T4;
2. GPU utilisation, to detect a CPU/dataloader bottleneck;
3. peak GPU memory at the default plan's patch and batch size;
4. preprocessing wall-time and on-disk size;
5. checkpoint/resume correctness after a forced session kill;
6. per-case inference time (no mirroring) for a 3-member ensemble, including on-the-fly metric computation;
7. the actual Kaggle weekly quota, session limit and writable disk;
8. seed-to-seed variability on a short run (to calibrate expectations, not for analysis).

**Stopping rules — additions required:**

- **SR6 (projected total).** If EXP-001 projects more than 220 GPU-h in total, apply pre-declared reductions **in this order**:
  1. arm A external inference only on full / −T1c / −FLAIR;
  2. drop C15;
  3. 150-epoch schedule for all runs;
  4. consult the owner.
- **SR7 (data terms).** If the licence does not permit the storage route chosen for preprocessed data, halt compute until a compliant workflow exists (e.g. re-preprocessing per session).
- **SR8 (platform change).** If Kaggle quota or hardware changes materially, re-run the SR6 projection before continuing.

Existing SR1–SR5 are adequate otherwise.

---

## 11. Exact changes required before v1.0

Report only; **FINAL_RESEARCH_PROTOCOL.md has not been modified.**

1. **§1–§3:** replace the research question, hypotheses and primary endpoint with §9 items 5–7. Single primary H-W at α = 0.05 with a 95% CI. H-SEG becomes supporting.
2. **§4:**
   - reclassify S4 (ECE/Brier) as a replication of MMA-LTS;
   - remove QU-BraTS, lesion-wise Dice and TTA;
   - limit S10 to the internal test set;
   - add the lexicographic ranker, mixture-weight sensitivity and I's transfer error.
3. **§5–§7:**
   - held-out institution = **all 511 site-1 (UPenn-origin) training cases** per the TCIA crosswalk; development = **740**;
   - record the crosswalk file name and its hash;
   - cite the Öchsner discrepancy as a reason.
4. **§5:** BraTS-Africa = the **95 glioma** cases from the TCIA v2 release (the 51 non-glioma excluded). Record the label convention 1/2/3 with ET = 3, to be confirmed on files.
5. **§4 S5:** rename to "RANO 2.0-motivated relative ET volume error ≥ 40%" (with a sensitivity analysis at 65% for under-segmentation). State that the 1 mL minimum is a study choice.
6. **§4 S7 and §21:** replace the threshold-transfer definition with the Δrisk / Δcoverage definition (§8 item 11). Add the 70% and 90% coverage sensitivities.
7. **§13–§15:** single-primary statistics; within-condition bootstrap procedure; statement that secondary families are Holm-within-family only.
8. **§20:** add SR6–SR8.
9. **§23:** rewrite the novelty statement to acknowledge MMA-LTS, SimMLM, Joham 2026 and BraTS-GoAT, and to claim only the within-condition, case-level, transfer question, scoped with "to our knowledge, based on the search performed on 2026-09-27".
10. **Pre-freeze checklist:**
    - mark MoFe/TMI items resolved (with the correction);
    - add: BrainLes/BraTS 2024 proceedings unscreened; PNDC full text unverified; the licence question for private re-hosting.

## 12. Final recommendation

**B. PROTOCOL REQUIRES REVISION**

- The core question survives adversarial search, but only in the narrowed within-condition, case-level and transfer form.
- MMA-LTS (MICCAI 2026) closes the voxel-calibration component.
- The pooled primary comparison is methodologically weak.
- The held-out-institution definition contains a verified factual error.
- The required changes are confined to the protocol text. They need no new models and no additional training runs.

After the owner approves the §11 changes, a short re-check (BrainLes/BraTS 2024 proceedings and the licence question) is the only remaining work before a "ready for freeze" verdict can be considered.
