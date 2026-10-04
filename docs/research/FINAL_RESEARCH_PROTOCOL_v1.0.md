# FINAL RESEARCH PROTOCOL (pre-registration)

| Field | Value |
|---|---|
| Protocol version | **v1.0 — FROZEN** |
| Freeze date | **2026-09-28** |
| Freeze basis | **A9 owner approval completed (2026-09-28):** the owner approved the v0.5 text (commit `7bb9e15`, file `FINAL_RESEARCH_PROTOCOL.md`) as the final frozen protocol. This v1.0 text is identical to that v0.5 text except for the protocol identity/state fields (header, freeze rule, gate A9, provenance note on the freeze, and the §25 v1.0 entry). |
| Date of last pre-freeze revision | 2026-09-28 (v0.5) |
| Reason for v0.5 revision | **Substantive:** the S7 threshold-transfer validation population changes from C5 to C4; Full is excluded from τ estimation; S13 applies to S12 only. See [18_PROTOCOL_V0.4_TO_V0.5_CHANGELOG.md](18_PROTOCOL_V0.4_TO_V0.5_CHANGELOG.md). H-W is unchanged from v0.4. |
| Previous versions | v0.5 (2026-09-28; frozen as v1.0), v0.4 (2026-09-28), v0.3 (2026-09-28), v0.2 (2026-09-27; approved by the owner for pre-freeze verification), v0.1 (2026-09-27); all superseded |
| v0.4 revision history (retained) | **Substantive** owner-approved amendment following [17_V0.3_FINAL_CONSISTENCY_AUDIT.md](17_V0.3_FINAL_CONSISTENCY_AUDIT.md). The primary H-W estimand now averages only the four single-missing conditions; Full becomes a supporting/control condition. Also: H4 is made descriptive; §19 is defined via τ_0.20; case vs patient-group terminology; the T_screen rule and manual-review procedure are fixed; the lifecycle is restructured into gates A–D. The research question (§1) is unchanged. Changes are listed in §25 and [17_V0.3_TO_V0.4_CHANGELOG.md](17_V0.3_TO_V0.4_CHANGELOG.md). Earlier changelogs: [16](16_PROTOCOL_V0.3_CHANGELOG.md), [14](14_PROTOCOL_REVISION_SUMMARY.md). |
| Freeze rule | **This protocol is FROZEN as v1.0 (2026-09-28)** and is git-tagged `protocol-v1.0`. All gate-A items are closed or owner-waived, and the owner approved the text (A9). **Any subsequent change requires a logged amendment in §25** (date, version, sections, change, reason, and whether any test data had been seen). No change is allowed after any test-set evaluation. Gates B–D are post-freeze execution gates. Their execution records (hashes, counts, T_screen value, patient groups, split hashes, EXP-001 measurements) are appended as logged administrative entries in §25 and do not change the pre-registered design. |
| Basis | [12_PRE_PROTOCOL_AUDIT.md](12_PRE_PROTOCOL_AUDIT.md), [13_PRE_FREEZE_AUDIT.md](13_PRE_FREEZE_AUDIT.md), [15_PREFREEZE_VERIFICATION_REPORT.md](15_PREFREEZE_VERIFICATION_REPORT.md), [17_V0.3_FINAL_CONSISTENCY_AUDIT.md](17_V0.3_FINAL_CONSISTENCY_AUDIT.md), [search_log.md](search_log.md) |

No study imaging dataset or label-volume data have been downloaded. During prior verification, only public identifier/metadata files were retrieved. No training, final split creation, test evaluation, held-out-institution evaluation, BraTS-Africa evaluation, or EXP-001 has been performed (status at freeze, 2026-09-28). This document contains no results. Numbers are design parameters, **[LITERATURE RESULT]**s, **[VERIFIED]** metadata facts or **[ESTIMATE]**s.

### Lifecycle gates

**Final split creation remains forbidden until v1.0 is approved AND the A1 grouping gate (B7–B9) is complete.**

**A. v1.0 FREEZE BLOCKERS** (must be complete before v1.0)

- [x] **A1.** Primary-endpoint decision implemented. H-W averages the four single-missing conditions; Full is a supporting/control condition (§2.1, §3, §13). *Specified in v0.4; binding at v1.0.*
- [x] **A2.** H4 wording resolved. It is descriptive, not confirmatory (§2.2, §14 F5). *Specified in v0.4.*
- [x] **A3.** §19 confident-failure threshold resolved (τ_0.20). *Specified in v0.4.*
- [x] **A4.** Case / patient-group terminology resolved (§3, §13, §19, §24). *Specified in v0.4.*
- [x] **A5.** T_screen **rule** frozen (§6.2): minimum WT-label Dice over the two verified positive-control pairs. The numerical value is computed at gate B7. *Specified in v0.4.*
- [x] **A6.** Manual-review procedure frozen (§6.2). The procedure is specified in v0.4. Reviewer identities were confirmed by the owner on 2026-09-28 and are also recorded in the experiment metadata:
  - **Primary reviewer:** Ayush Kushwaha
  - **Second reviewer:** Dr. Sreenivasa Chakravarthi
- [x] **A7.** BrainLes / BraTS 2024 literature status. **OWNER-WAIVED (2026-09-28).**
  - The official LNCS 15354 volume ("Traumatic Brain Injuries, Medical Image De-identification, and Brain Tumor Segmentation", MICCAI 2024 Challenges, including BraTS 2024) was verified by the owner via the official Springer page, but its chapter-level table of contents could not be independently accessed.
  - A surrogate screen found no material overlap with the exact novelty question (case-level reliability under missing MRI sequences + fixed, known missing-sequence condition + uncertainty/ensemble signal + within-condition failure discrimination + threshold/external transfer). The surrogate screen covered MICCAI 2024 (all 856 titles), BraTS-2024-related arXiv/OpenAlex results and targeted recent literature ([19_GATE_A_CLOSURE_AUDIT.md](19_GATE_A_CLOSURE_AUDIT.md) §2).
  - **Mandatory pre-submission re-check:** the relevant BraTS 2024 / BrainLes chapters must be screened before manuscript submission.
- [x] **A8.** PNDC (Qiu et al., IEEE TMI 2025, doi 10.1109/TMI.2025.3526818). **OWNER-WAIVED (2026-09-28).**
  - The full text was not accessible (**FULL TEXT UNVERIFIED**).
  - The official abstract and the authors' public code (github.com/yansheng-qiu/PNDC) show incomplete-modality segmentation and training-time region-level reliability. They show no evidence of case-level uncertainty/failure detection, AURC/risk-coverage, threshold transfer or external transfer ([19_GATE_A_CLOSURE_AUDIT.md](19_GATE_A_CLOSURE_AUDIT.md) §3).
  - **Mandatory full-text re-check** before manuscript submission if institutional access becomes available.
- [x] **A9.** **CLOSED — OWNER APPROVED / FROZEN (2026-09-28).** The owner approved the v0.5 text as the final frozen protocol; frozen as v1.0 and tagged `protocol-v1.0`.

**B. POST-FREEZE / PRE-SPLIT DATA GATES** (after v1.0, before the split, in this order)

- [ ] **B1.** Approved data route: TCIA confirmation on private third-party re-hosting (or an owner-approved alternative), per §5.1 and SR7.
- [ ] **B2.** Official data acquired via the approved route.
- [ ] **B3.** Exact SHA-256 recorded for `BraTS2021_MappingToTCIA.xlsx` as used.
- [ ] **B4.** SHA-256 recorded for `UCSF-PDGM-metadata_v5.csv` as used.
- [ ] **B5.** Data manifest and hashes recorded.
- [ ] **B6.** Counts re-derived from the hashed crosswalk (1,251 / 511 / 740). SR3 applies on failure.
- [ ] **B7.** A1 screen executed (§6.2): T_screen computed from the positive controls, then the pairwise screen run.
- [ ] **B8.** Flagged pairs manually reviewed per §6.2.
- [ ] **B9.** Patient groups frozen and committed (IDs only).
- [ ] **B10.** Final split created **once** (§6.3).
- [ ] **B11.** Split assertions pass (§6.3).
- [ ] **B12.** Split hashes recorded.

**C. PRE-EXTERNAL-EVALUATION GATES** (before any UPenn HOI or BraTS-Africa evaluation)

- [ ] **C1.** BraTS-Africa file-level label verification (expected 1 = NETC, 2 = SNFH, 3 = ET) and the sub-region presence per case.
- [ ] **C2.** BraTS-Africa four-sequence verification.
- [ ] **C3.** BraTS-Africa eligible count frozen (≤ 95), without any model output.
- [ ] **C4.** HOI patient grouping frozen (same frozen §6.2 rule and procedure).
- [ ] **C5.** Validation-derived τ_q (q = 0.80, 0.70, 0.90, and τ_0.20 for §19) and I frozen.
- [ ] **C6.** Evaluation code tagged `eval-v1`.

**D. EXP-001 / COMPUTE GATES** (after B1 approval; before main training)

- [ ] **D1.** Owner authorization of EXP-001 ([EXP-001_COMPUTE_PILOT_SPEC.md](../experiments/EXP-001_COMPUTE_PILOT_SPEC.md)).
- [ ] **D2.** Approved data route (B1).
- [ ] **D3.** Pilot restricted to permitted development cases (site ≠ 1).
- [ ] **D4.** The pilot computes no label-based scientific metrics.
- [ ] **D5.** No site-1 or BraTS-Africa data in the pilot.
- [ ] **D6.** Compute consequences follow SR1, SR6 and SR8 (§20) before main training.

---

## 1. Research question

> When MRI sequences are missing at inference, does the case-level ensemble uncertainty of a modality-dropout nnU-Net discriminate unreliable enhancing-tumour segmentations within a given missing-sequence condition, i.e. beyond what the known identity of the missing sequence provides? How does this vary with which sequence is missing, and do the discrimination and operating thresholds transfer to a held-out institution and an external population?

**The central scientific question is:** *among cases with the same missing sequence, can ensemble disagreement identify which cases are likely to fail?*

Why the question is framed this way:

- In deployment, the identity of the missing sequence is known from the protocol or DICOM header.
- A quality-control signal is therefore only useful if it separates good from bad cases **given** that knowledge.
- Within a fixed condition, the missingness-indicator rule (I) assigns every case the same score. Any discrimination there must come from the uncertainty signal itself.

## 2. Hypotheses

### 2.1 Primary hypothesis (single; α = 0.05, two-sided 95% CI)

**H-W.** On the internal test set, for the modality-dropout (arm B) ensemble, the mean over the **four single-missing conditions C4 = {−T1, −T1c, −T2, −FLAIR}** (§10) of the within-condition ET ΔAURC is < 0.

Definitions:

- ΔAURC_c = AURC_c(U1) − AURC_c(I), with equal weighting of the four conditions.
- U1 = ensemble pairwise-Dice confidence (§11).
- I = missingness-indicator baseline (§11).
- Risk = 1 − ET Dice.
- Within a fixed missing-sequence condition c, I is constant. Its expected AURC under random tie-breaking therefore equals the **mean ET risk of condition c** (random ranking). ΔAURC_c < 0 means that U1 ranks failures within condition c better than chance, i.e. better than knowing only the missing sequence.

**Full condition.** Full is a **supporting/control condition, not part of the primary H-W estimand**. It stays in C5 and is reported separately (ΔAURC_Full, descriptive). Full does **not** test "information beyond missingness identity", because nothing is missing. It serves as a complete-input reference for the four missing-condition components.

### 2.2 Key secondary hypotheses

These are tested within the families of §14.

- **H-W(−T1c).** The −T1c component ΔAURC_−T1c < 0. It is reported separately as the key secondary result, because T1c is the sequence on which ET delineation most depends.
- **H-W-ext.** The mean over C4 of the within-condition ET ΔAURC < 0 on the held-out institution (UPenn, 511 cases) and on BraTS-Africa, analysed **separately** and never pooled.
- **H-T (threshold transfer).** This analysis assesses whether there is **evidence of adverse transfer**. The confidence threshold τ_0.80 is fixed on the internal validation C4 units (§4 S7) and applied unchanged to the C4 units of the internal test, UPenn and BraTS-Africa sets. For q = 0.80:
  - **Evidence of unsafe transfer** = Holm-adjusted p < 0.05 **and** Δrisk > 0 (family F3).
  - **Evidence of inefficient transfer** = Holm-adjusted p < 0.05 **and** Δcoverage < 0 (family F3b).
  - Otherwise, the report states **no evidence of unsafe/inefficient transfer**.
  - A non-significant result does **not** establish that transfer is safe, and does **not** establish equivalence.
  - The bootstrap p-value and Holm procedures are those of §13–§14.
- **H4 (descriptive; not confirmatory).** Arm A within-condition ΔAURC_c for the four single-missing conditions is reported descriptively to characterize reliability without modality-dropout training. The comparison between arm A and arm B is descriptive; no confirmatory B-versus-A hypothesis test is made (§14 F5; no α is spent).

### 2.3 Supporting and replication analyses (not confirmatory; no α spent)

- **Supporting / sanity (formerly H-SEG).** Compare arm B and arm A on ET Dice across the C5 conditions, to show that the modality-dropout model is usable under incomplete inputs. This replicates known findings [C6, C7, C8] and is **not** the scientific contribution. A full-input sanity analysis reports the 95% confidence interval for the B-versus-A ET Dice difference against the pre-specified ±1.5 Dice-point margin (following [C7]). This is descriptive only; no equivalence hypothesis is formally tested and no α is spent.
- **Replication (formerly H2).** Voxel-level calibration (ECE/Brier) per condition and region. MMA-LTS (Lee et al., MICCAI 2026) has already evaluated voxel-level calibration across missing-modality combinations and tumour regions. This protocol tests only **whether that published behaviour is reproduced** in a modality-dropout nnU-Net setting. Missing-sequence-specific calibration is **not** claimed as a contribution.

## 3. Primary endpoint and justification

| Endpoint | Definition | Justification |
|---|---|---|
| **Mean within-condition ET ΔAURC over the four single-missing conditions** | ΔAURC = (1/4) Σ_c∈C4 [AURC_c(U1) − AURC_c(I)], C4 = {−T1, −T1c, −T2, −FLAIR}, on the internal test set, B ensemble. Equal condition weighting. Evaluation units within condition c = BraTS cases; bootstrap unit = patient group (§6.1). Full is excluded from the estimand and reported separately as a control. Risk = 1 − ET Dice. Dice convention: both masks empty → 1; exactly one empty → 0. | It isolates within-condition discrimination, the only component that cannot be supplied by knowing the missing sequence. A pooled comparison mixes between-condition difficulty ordering with within-condition discrimination (Joham et al., UNSURE 2026 [13 §3.4]), so it cannot test the research question. ET is the region most dependent on a single sequence (T1c), drives response assessment, and is the least robust region [H1, H2]. |

**AURC computation.**

- For n units ranked by descending confidence, AURC is the mean selective risk over the coverages k/n, for k = 1…n.
- Ties are handled by the expected value under random tie-breaking. For I within a condition, this gives exactly the mean risk.
- Because U1 and I score the same predictions, ΔAURC_c equals Δe-AURC_c.

## 4. Secondary endpoints

**Tested within the families of §14:**

- **S1.** ΔAURC_c for each of the four single-missing conditions in C4 (ET), with −T1c highlighted (H-W(−T1c)). The Full component ΔAURC_Full is reported alongside as a **descriptive control** and is not tested in F1.
- **S2.** The primary endpoint (mean over C4) computed for TC and WT.
- **S8.** The primary endpoint and S1 on the UPenn held-out institution (511 cases) and on BraTS-Africa (≤ 95 cases), separately (H-W-ext). External per-condition components are descriptive and are not treated as additional inferential tests; only the pre-specified external means are tested in F2.
- **S7.** Threshold transfer (H-T):
  - **Deterministic threshold rule (A3).** For target coverage q, τ_q is the **largest observed U1 value** such that coverage(validation, U1 ≥ τ_q) ≥ q.
    - Coverage is computed only on the validation C4 units {−T1, −T1c, −T2, −FLAIR}, using equal condition weighting.
    - **Full is NOT used to estimate τ_q.** Full remains a supporting/control condition, may be reported separately, and must not influence the primary missing-sequence threshold.
    - Interpretation: S7 evaluates **a single operating threshold learned from the four missing-sequence validation conditions and transferred unchanged** across the missing-sequence target conditions and external datasets.
    - There is no interpolation between U1 values and no random tie-breaking. All units with U1 ≥ τ_q are accepted, so the realized validation coverage may exceed q when U1 has ties.
  - q = 0.80 (primary); q = 0.70 and q = 0.90 (sensitivity).
  - τ_q is estimated **once, on internal validation only**. It is never re-estimated on the internal test, UPenn or BraTS-Africa sets, and never estimated from test or external data.
  - For each target set (internal test, UPenn, BraTS-Africa), on that set's **C4 units** (equal condition weighting; Full excluded), with the same U1 ≥ τ_q rule, compute:
    - **Δrisk** = target selective ET risk − validation selective ET risk (**Δrisk > 0 means the target risk is worse than validation**);
    - **Δcoverage** = target coverage − validation coverage (**Δcoverage < 0 means fewer cases are accepted on the target**).
  - Report τ_q, the realized validation coverage and the realized target coverage for every q and target.
  - CIs come from **independent** bootstraps (patient-group level, §6) of the validation set and the target set, 10,000 replicates, each resampling both sets independently.
  - Two-sided bootstrap p-values use the §13 construction, applied to Δrisk and Δcoverage.
  - **Unsafe transfer (A2)** is declared only when the Holm-adjusted p-value for the relevant F3 hypothesis is < 0.05 **and** the estimated Δrisk is > 0.
  - **Inefficient transfer** is declared only when the Holm-adjusted p-value for the relevant F3b hypothesis is < 0.05 **and** the estimated Δcoverage is < 0.
  - Unadjusted 95% CIs are reported descriptively. Neither label is applied otherwise, and **no equivalence is claimed**.
  - τ_q is not re-estimated within the bootstrap. This is a stated limitation (§22).
- **S9 (descriptive; H4).** Arm A within-condition ΔAURC_c for the four single-missing conditions, with 95% CIs. Shown alongside arm B's values; the A-versus-B comparison is descriptive only and carries no inferential claim.

**Secondary, descriptive only** (reported with 95% CIs, no hypothesis test):

- **S3.** WT and TC Dice; HD95 per region. HD95 uses the BraTS evaluation convention implemented by the exact evaluation code pinned at gate C6. The empty-mask behavior is verified before eval-v1 is tagged.
- **S4 (replication of MMA-LTS).** ECE and Brier score per region per condition:
  - computed on the ensemble-mean probability;
  - ROI = union of GT and predicted region, dilated by 3 voxels;
  - 15 equal-width bins; per-case values averaged over cases.
  - Interpreted only as consistency or inconsistency with published voxel-level findings.
- **S5.** Volume failure:
  - absolute ET volume error (mL);
  - **"RANO 2.0-motivated relative ET volume error ≥ 40%"** as a binary failure definition, for cases with GT ET ≥ 1 mL, with AURC computed on this risk;
  - sensitivity analysis at **65%**.
  - RANO 2.0's 40% (progression) and 65% (partial response) thresholds concern **longitudinal change in tumour burden**. They are **not** segmentation-error criteria. They are used here only as clinically motivated secondary error thresholds.
  - The ≥ 1 mL minimum is a **study-defined choice**.
- **S6.** Spearman ρ between U1 and ET Dice, per condition.
- **S10.** Fifteen-subset (C15) analysis, **internal test set and arm B only**: ET Dice, within-condition ET ΔAURC and ECE per subset. C15 is not run on external datasets unless approved later as an amendment.
- **S12. Pooled analyses (descriptive only; they must not drive the main conclusion).** The pooled C5 units are ranked by:
  1. U1;
  2. I (validation-estimated condition risk);
  3. the lexicographic **"I-then-U1"** ranker: rank first by the condition's validation-estimated ET risk, then break ties within a condition by U1.

  Comparing I, U1 and I-then-U1 separates information carried by the missingness condition from information carried by uncertainty within the condition, and shows their combination. Pooled AURC mixes **between-condition difficulty** with **within-condition discrimination**. It therefore cannot serve as the primary test of information beyond missingness identity.
- **S13. Mixture-weight sensitivity for S12 only.** S12 is descriptive and uses C5 because it intentionally examines pooled information across Full and the missingness conditions. The threshold-transfer analysis S7 is excluded from this mixture-weight sensitivity and uses equal weighting across the four C4 missing-sequence conditions. No alternative C4 weighting is specified. For S12, weights are applied by case-weighting the pooled units:
  - (a) equal weights over C5;
  - (b) 80% Full + 5% for each single-missing condition.

  Both are **hypothetical deployment mixtures**. Neither is claimed to be clinically representative. Equal weighting is arbitrary.
- **S14. Indicator transfer error.** For each condition, report the validation-estimated ET risk minus the realized target risk, on the internal test, UPenn and BraTS-Africa sets.
- **Supporting:** arm B vs arm A ET Dice over C5, and the descriptive full-input sanity analysis (95% CI against the ±1.5 Dice-point margin; §2.3).

**Exploratory** (no inference): U3 single-model confidence (§11).

**Removed from the planned analysis** (possible future work only):

- mirroring test-time augmentation
- QU-BraTS uncertainty score
- lesion-wise Dice

## 5. Datasets

| Role | Dataset | Inclusion | n |
|---|---|---|---|
| **Development** (train / validation / internal test) | BraTS 2021 training set (see §5.1 for licence and access) | All training cases **not** from site 1 (UPenn) | **740 cases** before patient grouping [VERIFIED from crosswalk metadata]; ≤ 738 patients (§6) |
| **Held-out institution (HOI)** | UPenn-origin cases **within** BraTS 2021 training: `UPENN-GBM` (403) + `UPENN-GBM_Additional` (108), all **site 1** | All with 4 sequences and labels | **511** [VERIFIED from crosswalk metadata] |
| **External** | TCIA BraTS-Africa collection (**Version 1, updated 2024-09-04**; metadata file `BraTS-Africa_TCIA_datainfo_v2.xlsx`); processed release, CC BY 4.0. Metadata sheets: "95 Glioma", "51 OtherNeoplasms". | The **95** adult glioma cases with 4 sequences and labels. **51 OtherNeoplasms cases excluded.** | **≤ 95** (eligible count pending file-level verification) |

### 5.1 Licence, access and data route (A4)

**BraTS 2021** [VERIFIED from official pages, 2026-09-27/28]:

- The TCIA analysis result "RSNA-ASNR-MICCAI-BraTS-2021" (DOI 10.7937/jc8x-9874) lists the challenge package ("Challenge data both tasks", 142 GB) and the ID crosswalk as **CC BY 4.0**.
- The linked original source DICOMs of some collections fall under the NIH Controlled Data Access Policy. They are not needed.
- Synapse access (syn25829067 / syn25829070) requires an authenticated account and is subject to the Synapse Terms and Conditions of Use and the BraTS 2021 "Rules & Resources" citation and acknowledgement requirements.
- The **TCIA Data Usage Policy** applies:
  - no re-identification;
  - no facial renderings;
  - dataset DOI citation;
  - review of TCIA's Data Analysis Centers page before any mirroring or third-party access.
- Required citations (BraTS 2021 papers and the TCIA DOIs) and the Synapse acknowledgement sentence must be followed.

**Private third-party re-hosting:** "Private third-party re-hosting (including private Kaggle dataset storage) requires confirmation from TCIA before use." The published terms do not explicitly address it (**ambiguous**). This protocol makes no legal conclusion.

**Other data-handling rules:**

- The project will **not** use or create a **public Kaggle mirror**. Unofficial mirrors are never a source of record.
- The operational data route is **pending owner confirmation** after the TCIA reply (gates B1/D2; SR7). No compute begins until the route is approved.
- Trained checkpoints are not published unless the providers confirm this is acceptable.

**BraTS-Africa:** the processed release is CC BY 4.0. Unprocessed images are under limited access and are not needed. TCIA citation (DOI 10.7937/v8h6-8x67) is required.

### 5.2 Verification status of dataset facts (A5)

| Fact | Metadata / documentation verification | File-level verification |
|---|---|---|
| BraTS 2021: 1,251 training; site 1 = 511 (403 + 108); development = 740 | VERIFIED (TCIA crosswalk) | Pending (gates B3–B6; hash of the file used) |
| BraTS-Africa: 95 Glioma / 51 OtherNeoplasms | VERIFIED (TCIA metadata spreadsheet) | Pending |
| BraTS-Africa sequences T1, T1 CE, T2, T2 FLAIR | VERIFIED (TCIA collection description; 146 subjects / 730 processed series) | Pending (per-case completeness) |
| BraTS-Africa labels 1 = NETC, 2 = SNFH, 3 = ET | VERIFIED from BraTS 2023 challenge documentation only | Pending |
| Some BraTS-Africa glioma cases have fewer than 3 labelled sub-regions (metadata: 3 labels = 89, 2 = 5, 1 = 1, one blank row), so ET may be absent | VERIFIED (metadata) | Pending |
| BraTS-Africa eligible count (≤ 95) | Design parameter | Pending (gates C1–C3); the final count is only knowable after file inspection |

Notes on the held-out institution:

- **Source:** the official TCIA crosswalk `BraTS2021_MappingToTCIA.xlsx`, which gives source collection and site ID for every BraTS 2021 case.
- The crosswalk was inspected as identifier metadata only. It is **not committed** to this repository unless its licence explicitly permits redistribution. Its SHA-256 is recorded at gate B3.
- **Why all 511 cases:** holding out the entire institution prevents same-institution leakage. Excluding only the 403 `UPENN-GBM` cases (as implied by the development n = 848 in [C7]) would leave 108 site-1 cases in development [INFERENCE from 1,251 − 403 = 848].

**Shift characteristics:**

- **HOI:** same BraTS preprocessing and curation, different institution. It is likely a mild shift; [C7] reports ~95% external Dice [LITERATURE RESULT].
- **BraTS-Africa:** population and acquisition shift. Four Nigerian centres and three scanner models (Siemens Magnetom Essenza, GE SIGNA Creator, Philips Achieva) per the collection's metadata spreadsheet `BraTS-Africa_TCIA_datainfo_v2.xlsx` [VERIFIED metadata]. Native slice thickness is 3–5 mm before resampling [VERIFIED, TCIA description]. Labels were refined from nnU-Net pre-segmentations with multi-stage expert review [A5].

**Not used:** UCSF-PDGM, EGD and standalone TCIA UPenn-GBM (possible future work).

## 6. Patient-level splits

**Not yet created.** Splits are created only after v1.0.

### 6.1 Unit of analysis: the patient group (A1)

The split unit, the stratification unit and the bootstrap unit are the **patient group**, not the BraTS subject/case.

Why:

- Patient identity is imperfectly observable in BraTS 2021.
- 243 development rows carry the placeholder TCIA ID "new-not-previously-in-TCIA".
- Grouping by TCIA ID alone cannot detect all same-patient relationships [VERIFIED, crosswalk].

Grouping keeps correlated follow-up scans of the same patient from crossing train/validation/test boundaries, and keeps them together in bootstrap resampling.

**Verified same-patient groups** [VERIFIED: TCIA `UCSF-PDGM-metadata_v5.csv` + crosswalk]. Both are site 18, so both are in development:

| Group | BraTS 2021 IDs | Source relation |
|---|---|---|
| **A** | BraTS2021_00626, BraTS2021_00758 | UCSF-PDGM-433 and its follow-up UCSF-PDGM-0433_FU007d (7 days) |
| **B** | BraTS2021_00639, BraTS2021_00557 | UCSF-PDGM-429 and its follow-up UCSF-PDGM-0429_FU003d (3 days) |

Groups A and B remain together in splitting, stratification and bootstrap resampling. The development pool is therefore 740 cases and at most 738 patient groups before the §6.2 screen.

Any case with a real TCIA patient ID shared with another case is also grouped. None is known in the training cohort [VERIFIED, crosswalk].

### 6.2 Pre-split label-only same-patient screen (safeguard for unidentified duplicates)

**Purpose and scope.** This screen is a **leakage-prevention safeguard**. It is **not** a substitute for complete patient-identity metadata, and it **cannot guarantee** detection of every same-patient relationship (for example, when follow-up anatomy or labels change substantially).

**Permitted inputs:** only ground-truth WT labels and permitted pre-split metadata (the TCIA crosswalk and TCIA collection metadata such as `UCSF-PDGM-metadata_v5.csv`). The screen never uses model predictions, segmentation performance, test results, calibration results, or any information generated after the split.

Procedure, in this order:

1. **Inputs.** Use only the ground-truth WT labels of the development cases (and, separately, of the HOI cases; see below) and the permitted metadata.
2. **Comparison.** Compare every unordered pair of development cases by the **WT-label Dice** of their ground-truth WT masks. All BraTS cases are in the same SRI24 space, so no registration is performed.
3. **Flagging.** Flag pairs with WT-label Dice ≥ **T_screen**.
   - **T_screen rule (frozen in v0.4): T_screen = the minimum WT-label Dice observed among the two verified same-patient positive-control pairs**:
     - A = BraTS2021_00626 + BraTS2021_00758
     - B = BraTS2021_00639 + BraTS2021_00557
   - **Only the rule is frozen pre-data.** The numerical value is calculated **once**, at gate B7, from these two positive controls, when the permitted label files are obtained.
   - The value is computed **before** the complete development pairwise similarity distribution is examined. No threshold-shopping is permitted.
   - No model prediction, test result or other study outcome may influence T_screen. By construction, both positive-control pairs are flagged.
4. **Manual review** (procedure frozen in v0.4). Each flagged pair is classified as follows.
   - **Reviewer:** primary reviewer **Ayush Kushwaha**; second reviewer for disagreements **Dr. Sreenivasa Chakravarthi**. Both are also recorded in the experiment metadata.
   - **Material inspected:** aligned/co-registered T1, T1c, T2 and FLAIR for both cases; their WT labels; TCIA crosswalk metadata; site and study date where available.
   - **Never inspected:** model predictions, Dice or any segmentation-performance result, calibration results, test results, or any post-split scientific outcome.
   - **Decision categories:** SAME PATIENT / DIFFERENT PATIENT / UNRESOLVED.
   - **Decision rule:**
     - SAME PATIENT requires concordant non-tumour anatomy and lesion location/morphology that support a shared patient identity.
     - DIFFERENT PATIENT requires sufficient evidence against shared identity.
     - UNRESOLVED is used when image quality or anatomy does not permit a defensible decision.
   - **Recorded per pair:** pair IDs, decision, reviewer, timestamp, reason, in a committed CSV (IDs only).
   - **Disagreements:** the second reviewer reviews independently. If the pair is still not resolved, it is classified as UNRESOLVED.
   - **For splitting, UNRESOLVED relationships are conservatively treated as linked**, so that potential leakage is not allowed across partitions.
5. **Grouping.** SAME PATIENT and UNRESOLVED pairs are merged into patient groups **transitively**, together with the verified groups A and B and any shared real TCIA IDs (§6.1).
6. **Freeze, then split.** The computed T_screen value, the review records and the resulting patient grouping are committed (IDs only) and frozen **before** the final split is created (gates B7–B9). **Only after the grouping is frozen may the 70/10/20 patient-group split (§6.3) be performed.**

The same screen, with the same T_screen value (derived from the development positive controls) and the same review procedure, is applied **within the HOI set (511 cases)** only to define bootstrap patient groups (gate C4). There, it has no effect on training.

BraTS-Africa subjects are treated as distinct patients, per the TCIA description of 146 patients.

### 6.3 Split procedure

- Development patient groups are split **70 / 10 / 20** into train / validation / internal test [ESTIMATE ≈ 518 / 74 / 148 cases].
- Stratification is at group level: ET present in any member vs absent in all members, and the tertile of the mean member WT volume. Both come from labels only.
- Split seed `20260927`. Randomization operates on patient groups. The split is performed once, before any training.
- **The split script must assert:**
  - no site-1 case enters development (selection by crosswalk `Site ID ≠ 1`, not by collection name);
  - the development count before grouping = **740**;
  - every confirmed same-patient group (including A and B) lies entirely within one partition.
- ID lists (IDs and group IDs only) are committed to `splits/`, and their hashes are recorded in the v1.0 protocol.
- **Site 18 (UCSF, 382 training cases) stays in development.** Site composition of each split is reported.

## 7. Deduplication

- **Development vs HOI:** disjoint by site, per the crosswalk.
- **Within development and within HOI:** patient grouping per §6.1–6.2.
- **BraTS-Africa vs BraTS 2021:** different institutions; overlap is very unlikely [INFERENCE]. An identical-image-hash check is performed as a safeguard.
- The deduplication and grouping output (IDs and counts) is committed, and the counts are reported in the paper.

## 8. Preprocessing

- Use the **BraTS-provided preprocessed** images: SRI24 space, 1 mm isotropic, skull-stripped. No re-registration.
- **nnU-Net v2**, version pinned at M1.
  - The raw dataset folder contains train + validation only, so the fingerprint and plans never see test data.
  - Default 3d_fullres plan and nnU-Net z-score normalization within the non-zero mask.
- Channel order is fixed as `[T1, T1c, T2, FLAIR]` and asserted by unit test.
- Region mapping:
  - BraTS 2021: ET = {4}, TC = {1, 4}, WT = {1, 2, 4}.
  - BraTS-Africa, **expected** labels 1 = NETC, 2 = SNFH, 3 = ET: ET = {3}, TC = {1, 3}, WT = {1, 2, 3}. **To be verified on files** (gate C1); the mapping is unit-tested.

## 9. Models

| | Arm A | Arm B |
|---|---|---|
| Framework | nnU-Net v2 3d_fullres, region-based (sigmoid WT/TC/ET) | same |
| Schedule | 250 epochs (`nnUNetTrainer_250epochs` semantics); `save_every` = 5 | same |
| Training data | train split | same |
| Missing-sequence dropout | none | §10 policy |
| Seeds | 0, 1, 2 | 0, 1, 2 |
| Checkpoint | `checkpoint_final` (pre-specified) | same |
| Inference | sliding window, step 0.5, **mirroring off**, threshold 0.5 | same |
| Ensemble | mean of the 3 members' sigmoid probabilities | same |

No new architecture, no MC-dropout and no attention or fusion module is used.

## 10. Missingness simulation

- A missing sequence is represented by setting its **normalized** channel to 0 (the brain-masked mean, equal to the background value). The same operation is used in training (arm B) and at inference.
- **C5 evaluation conditions:** {Full, −T1, −T1c, −T2, −FLAIR}. C5 is the full condition set, used for inference, for the supporting/control (Full) analyses and for the pooled descriptive analyses (S12/S13).
  - **C4 = {−T1, −T1c, −T2, −FLAIR}** is the **primary H-W estimand subset**. It is also the validation and target population of the S7 threshold-transfer analysis.
  - **Full** is evaluated as a supporting/control condition (§2.1). It is not part of H-W and not used for τ_q.
- **C15 (secondary, internal test and arm B only):** all 15 non-empty subsets.
- **Arm B training policy:** per sample, with probability 0.5 the input is full. Otherwise one of the 14 non-full, non-empty subsets is chosen uniformly, after augmentation. The policy is fixed a priori and **not tuned**.
- Zero-filling is not the same as a real missing or degraded acquisition (§22).

## 11. Confidence scores

Scores are computed per case and region r.

- **U1 (primary):** mean pairwise Dice between the three members' binary masks for r (each member thresholded at 0.5). Both empty → 1.
  - Properties (A3):
    - three members give only three pairwise comparisons;
    - U1 can take many distinct values, but is discrete because it is computed from finite binary masks;
    - it has a mass point at **1** when all members predict an empty region;
    - it has mass at **0** when at least one member predicts empty and another predicts non-empty;
    - discordant tiny-ET predictions can therefore produce false alarms;
    - U1 depends on the fixed 0.5 member threshold.
  - Operating thresholds on U1 use the deterministic ≥ rule of §4 S7.
- **U2 (secondary, descriptive):** negative mean binary entropy of the ensemble-mean probability within the ROI (union of member masks for r, dilated by 3 voxels). An empty ROI gives entropy 0.
- **U3 (exploratory):** single-model (seed 0) mean max-probability within the ROI.
- **I (baseline):** −(mean risk of that condition for r), estimated on the **validation** set for the same arm's ensemble.
  - Within a condition, I is constant (random-ranking baseline).
  - It is used across conditions only in S12 and S14 (the pooled/lexicographic analyses and the indicator transfer error).
  - No test or external data are used to estimate I.
- **I-then-U1 (secondary):** lexicographic, as defined in S12.
- **Not included:** temperature scaling and any missingness-conditioned calibrator. Voxel-level missingness-conditioned calibration is already addressed by MMA-LTS.

## 12. Failure definitions

- **Primary:** continuous risk = 1 − ET Dice.
- **Secondary:** the S5 binary volume failure (40%; 65% sensitivity).
- Risk–coverage curves use the tie handling of §3.
- Binary-failure AUROC may be reported as exploratory.

## 13. Statistical procedures

**Primary (H-W), 10,000 patient-group-level bootstrap replicates on the internal test set.** For each replicate:

1. Resample **patient groups** (§6.1) with replacement, keeping all cases of each sampled group and **all C5 conditions** of every case.
2. For each condition c ∈ C5, compute AURC_c(U1) and AURC_c(I) (the mean ET risk of condition c in the replicate), over the case-condition units of that condition.
3. Compute ΔAURC_c.
4. Average the **four single-missing** ΔAURC_c values (c ∈ C4) to obtain the primary statistic. ΔAURC_Full is computed in the same replicate but kept separate, as a control.

**Note on I in the primary bootstrap.** I is a constant-score random-ranking baseline within each condition. Its AURC equals the mean risk of the bootstrap replicate under the expected tie rule. This does not estimate the validation I score from test data. The validation-only definition of I (§11) is unchanged and is used only where I ranks across conditions (S12, S14).

**Reporting:**

- the point estimate (full sample) of the mean ΔAURC over C4, and each ΔAURC_c for c ∈ C4, with **−T1c** highlighted;
- ΔAURC_Full, reported separately as the complete-input control (descriptive);
- percentile 95% CIs, with BCa as a sensitivity analysis;
- a two-sided bootstrap p-value, 2 × min(P*(Δ ≥ 0), P*(Δ ≤ 0)), reported as approximate.

**Decision rule:** H-W is supported if the 95% CI of the mean ΔAURC over C4 lies entirely below 0.

**Other procedures:**

- **Secondary tested endpoints (A2):** the same patient-group bootstrap scheme on the relevant set. S7 uses independent validation and target bootstraps (§4).
  - Every tested secondary endpoint has a two-sided bootstrap p-value with the same construction as the primary: p = 2 × min[P*(Δ ≥ 0), P*(Δ ≤ 0)].
  - Holm correction is applied to these p-values **within each family** (§14).
  - Inferential claims within a secondary family use the **Holm-adjusted p-value** (< 0.05), together with the sign of the estimate in the hypothesised direction.
  - Unadjusted 95% CIs are reported descriptively.
- **Supporting (descriptive):**
  - Case-level ET Dice differences (B − A) are averaged over the C5 conditions of each case.
  - They are then averaged within each patient group, giving one value per patient group.
  - The patient-group bootstrap 95% CI of these differences is reported descriptively. No hypothesis-test statistic or p-value is reported for this sanity analysis.
  - The full-input sanity analysis uses the same patient-group-level differences (Full condition only). It reports their patient-group bootstrap 95% CI against the pre-specified ±1.5 Dice-point margin as a descriptive reference. No equivalence hypothesis is formally tested and no α is spent.
- **Seed variation:** single-member metrics are reported as mean ± SD over 3 seeds, descriptive only.
- External sets are never pooled with each other or with internal data. **No statistical equivalence is claimed** for any external result.

## 14. Multiplicity

- **Primary:** one hypothesis (H-W, mean over C4), α = 0.05, two-sided 95% CI; supported if the CI lies entirely below 0 (§13). No multiplicity adjustment is needed.
- **Secondary families**, each Holm-corrected **within the family only**, on the two-sided bootstrap p-values of §13 (A2):

| Family | Contents | Claim rule |
|---|---|---|
| F1 | S1: ΔAURC_c for the 4 single-missing conditions in C4, internal (4 tests). −T1c is reported as the key result. ΔAURC_Full is a descriptive control, **not** in F1. | ΔAURC_c < 0 claimed if Holm-adjusted p < 0.05 and estimate < 0 |
| F2 | S8: mean over C4 of within-condition ΔAURC on UPenn and on BraTS-Africa (2 tests) | as F1 |
| F3 | S7: Δrisk at q = 0.80 on internal test, UPenn and BraTS-Africa (3 tests) | "Unsafe transfer" if Holm-adjusted p < 0.05 **and** estimated Δrisk > 0 |
| F3b | S7: Δcoverage at q = 0.80 on internal test, UPenn and BraTS-Africa (3 tests) | "Inefficient transfer" if Holm-adjusted p < 0.05 **and** estimated Δcoverage < 0 |
| F4 | S2: TC and WT mean over C4 of within-condition ΔAURC (2 tests) | as F1 |
| F5 | S9: arm A ΔAURC_c for the 4 single-missing conditions: **descriptive only** (H4). No p-values are used for claims, no Holm correction, no α is spent, and there is no confirmatory A-versus-B test. | none (descriptive; 95% CIs) |

- The q = 0.70 and q = 0.90 transfer analyses are sensitivity analyses. They are reported with unadjusted 95% CIs and without inferential labels.
- **Holm correction is within family only. No global FWER control across the inferential families F1–F4 (including F3b) is claimed.** F5 is descriptive. Secondary results are interpreted as supporting evidence.
- Everything listed as descriptive, replication, supporting or exploratory is reported with CIs and without significance claims.

## 15. Confidence intervals

- Patient-group bootstrap (§6.1), 10,000 replicates, percentile method (BCa as a sensitivity analysis).
- 95% throughout.
- Bootstrap seed `12345`.

## 16. Seeds

| Seed | Value |
|---|---|
| Training | 0, 1, 2 |
| Split | 20260927 |
| Bootstrap | 12345 |
| Figure-case sampling | 7 |

- The split seed randomizes **patient groups**, not cases (§6.3).
- The §6.2 screen and the τ_q rule (§4 S7) are deterministic and use no random seed.
- cuDNN / nnU-Net non-determinism is acknowledged.

## 17. Compute budget (ESTIMATES until EXP-001)

### 17.1 Budget

- **Cap:** 220 GPU-h (Kaggle free tier, about 4–8 weeks).
- **Training:** 6 runs × 250 epochs ≈ 75–150 GPU-h [ESTIMATE]. The cost does not depend on development-set size, because nnU-Net epochs are a fixed 250 iterations.
- **Planned C5 inference/computation:** ≈ 828 cases (val ~74, test ~148, UPenn 511, Africa ≤ 95) × 5 conditions × 6 models ≈ 21–55 GPU-h [ESTIMATE].
- **C15** (internal test, arm B): ≈ 4–10 GPU-h [ESTIMATE].
- **Total:** ≈ 100–215 GPU-h [ESTIMATE].
- Softmax maps are not stored except for ≤ 20 pre-selected figure cases. Metrics are computed on the fly.

### 17.2 EXP-001 must measure

1. Seconds per epoch on P100, on a single T4, and with two concurrent runs on 2×T4.
2. GPU utilisation (to detect a CPU/dataloader bottleneck).
3. Peak GPU memory.
4. Preprocessing time and on-disk size.
5. Checkpoint/resume correctness after a forced session kill.
6. Per-case inference time (3-member ensemble, no mirroring, including on-the-fly metrics).
7. The actual Kaggle quota, session limit and writable disk.
8. Short-run seed variability.

## 18. External validation

- The UPenn HOI set and BraTS-Africa are used **only** for final evaluation.
- No training, tuning, threshold selection, indicator-risk estimation, calibration or checkpoint choice uses them.
- τ_q is estimated on internal validation only and applied unchanged (§4 S7). I is estimated on internal validation only (§11).
- Each set is evaluated once, with frozen code tagged `eval-v1`, and each is analysed separately.
- HOI bootstrap uses patient groups from the §6.2 screen. BraTS-Africa subjects are treated as distinct patients.

## 19. Failure analysis

A rule-based categorization of (case, condition) units per [05 §6](05_EXPERIMENTAL_DESIGN.md), plus:

- **Confident failure:** U1 ≥ τ_0.20 and ET Dice < 0.5.
  - τ_0.20 uses the §4 S7 deterministic rule with q = 0.20: the largest observed U1 value such that coverage(validation, U1 ≥ τ_0.20) ≥ 0.20. It therefore uses the same validation population as S7 (C4 units, equal condition weighting; Full not used).
  - It marks approximately the top 20% most-confident validation units, subject to U1 ties. It is estimated once on internal validation and never re-estimated.
  - **τ_0.80 is the primary deployment operating point** (§4 S7; unchanged). **τ_0.20 is only a descriptive high-confidence failure-analysis threshold** and plays no role in the transfer analysis.
- **Hallucinated ET:** GT ET empty but predicted ET present, broken down by condition, especially −T1c.
- **Missed ET:** the reverse case.

Counts are reported per condition and dataset. Figure cases are selected by rule (seed 7), not by hand.

## 20. Stopping rules

- **SR1 (per-run cost).** If the pilot-measured time exceeds 25 GPU-h per run, switch all 6 runs to 150 epochs before any evaluation. If still infeasible, consult the owner.
- **SR2 (sanity, validation only).** If arm A's full-input mean ET Dice on **validation** is < 0.75, stop and debug before any test evaluation. The threshold is set a priori as clearly below typical nnU-Net BraTS 2021 performance; it is not a target.
- **SR3 (data).**
  - If the site-1 cases cannot be reproducibly identified from the crosswalk: drop the HOI set, use all 1,251 cases for development, and log the deviation.
  - If BraTS-Africa has fewer than 30 eligible labelled glioma cases: its analyses become descriptive only.
  - If any §6.3 split-script assertion fails (site-1 case in development, development count ≠ 740 before grouping, or a patient group spanning partitions): stop, do not train, and log the deviation.
- **SR4 (integrity).** Test sets are evaluated once with tagged code. Any re-evaluation is logged, and both results are reported.
- **SR5 (bugs).** If a bug is found after evaluation: fix it, re-run everything affected, and report the deviation and both results.
- **SR6 (projected total compute).** If EXP-001 projects total compute > 220 GPU-h, apply these reductions **in order**, re-projecting after each:
  1. Arm A external inference only on Full, −T1c and −FLAIR.
  2. Drop C15.
  3. Switch all six runs to 150 epochs.
  4. Consult the owner.
- **SR7 (licensing).** If the BraTS licence or provider confirmation does not permit the planned storage or re-hosting route (e.g. a private Kaggle dataset), or if confirmation from TCIA has not been obtained, halt compute until a compliant workflow is established and approved by the owner (§5.1).
- **SR8 (platform change).** If Kaggle hardware or quota changes materially, recompute the project budget before continuing.

## 21. Interpretation rules

| Outcome | Interpretation |
|---|---|
| H-W: 95% CI entirely < 0 | Among internal cases with the same missing sequence, ensemble disagreement ranks ET failures better than chance on average over the four single-missing conditions (C4). Uncertainty adds information beyond the known missingness identity. |
| Full control (ΔAURC_Full) | Complete-input reference for the C4 components. Descriptive; it does not test information beyond missingness identity. |
| H4 / F5 (arm A) | Descriptive characterization of reliability without modality-dropout training. No confirmatory A-versus-B claim. |
| H-W: CI includes 0 | No evidence that uncertainty adds within-condition information. This is **not** evidence of equivalence. |
| H-W: CI entirely > 0 | Within-condition ranking is worse than chance. This is an important negative finding. |
| −T1c component differs from the others | Reported as condition-dependent reliability. It is a supporting (F1) result, not a primary claim. |
| External (F2) | The same wording, per dataset. Conclusions about transfer are made per dataset, never pooled. |
| Transfer (F3, F3b) | "Unsafe transfer" only if the Holm-adjusted p < 0.05 and Δrisk > 0. "Inefficient transfer" only if the Holm-adjusted p < 0.05 and Δcoverage < 0 (S7, §14). Otherwise "no evidence of unsafe/inefficient transfer". Never "equivalent". |
| Pooled analyses (S12–S13) | Descriptive. They must not override or substitute for the within-condition result. |
| ECE/Brier (S4) | Consistency with published voxel-level findings (MMA-LTS). No novelty claim. |

## 22. Limitations (pre-declared)

1. Missingness is **simulated by zeroing**. Real missing or degraded sequences are not studied.
2. The HOI set shares BraTS curation and preprocessing, so the institutional shift is likely mild. BraTS-Africa is small (≤ 95 cases, and fewer per condition component), which gives wide CIs.
3. The 250-epoch schedule is compute-limited. It is applied identically to both arms.
4. The 3-member ensemble comes from a single split, so the variance of ensemble-level results over retraining is not estimable. U1 rests on only three pairwise comparisons. It can take many distinct values but is discrete (computed from finite binary masks), and it has mass points at 1 (all members empty) and 0 (discordant empty/non-empty members), so discordant tiny-ET predictions can create false alarms. It depends on the fixed 0.5 member threshold.
5. Only pre-operative adult glioma is studied, with one architecture family.
6. There is no MC-dropout and no post-hoc calibration. Missingness-conditioned calibration is outside scope (see MMA-LTS).
7. Labels are expert-refined from automated pre-segmentations (BraTS, BraTS-Africa).
8. The volume-failure thresholds are RANO 2.0-motivated proxies, not validated segmentation-error criteria.
9. The threshold τ_q is fixed from the complete set of validation C4 units, and its estimation variability is not propagated into the transfer CIs. Selection uses a discrete ≥-coverage rule, so the realized validation coverage can exceed the nominal q when U1 has ties.
10. Within-condition AURC on the internal test set uses about 148 cases per condition. Per-condition external estimates will be imprecise.
11. Patient identity is imperfectly observable for some BraTS 2021 cases (placeholder TCIA IDs). Two verified same-patient follow-up pairs (groups A and B, §6.1) require grouping. The label-only pre-split similarity screen (§6.2) is a safeguard, not a guarantee, against unidentified same-patient cases. Its threshold is anchored on only two positive controls, both short-interval (3 and 7 days) pre-operative UCSF follow-ups, so same-patient pairs with larger anatomical or lesion change may fall below T_screen. Sensitivity and specificity of the screen cannot be estimated. UNRESOLVED pairs are grouped conservatively.
12. The primary estimand averages four simulated single-missing conditions with equal weight. This weighting is a design choice, not an estimate of real-world missingness frequencies. Full is reported only as a control.
13. Private third-party re-hosting of BraTS data remains pending provider (TCIA) confirmation (§5.1), which may constrain the compute route.

## 23. Novelty statement (conservative; re-check before submission)

> To our knowledge, based on searches performed on 2026-09-27 and 2026-09-28 (see `search_log.md`, rounds 1–3, and [19_GATE_A_CLOSURE_AUDIT.md](19_GATE_A_CLOSURE_AUDIT.md); literature items A7–A8 are owner-waived with mandatory pre-submission re-checks of the BraTS 2024 / BrainLes chapters and the PNDC full text), prior work has established that segmentation accuracy and volumetry can be largely preserved under missing MRI sequences by per-subset or dropout-trained nnU-Nets [Ruffle et al. 2023; Öchsner et al. 2026; Pemberton et al. 2023; GlioMODA 2026]; that voxel-level calibration under missing-modality combinations is combination- and region-specific and can be improved by availability-conditioned post-hoc calibration [MMA-LTS, Lee et al., MICCAI 2026]; that region-wise calibration can be reported under missing modalities averaged over configurations [SimMLM/MoFe, Li et al. 2025]; that ensemble pairwise-Dice and related scores detect case-level segmentation failures with complete inputs [Zenk et al. 2025; BraTS-GoAT reliability study 2026]; and that pooled risk–coverage evaluation can reward between-group difficulty ordering rather than within-group detection [Joham et al., UNSURE 2026]. We did not identify a study that evaluates **case-level** reliability under missing MRI sequences, specifically whether uncertainty discriminates segmentation failures **within a fixed missing-sequence condition**, and whether that discrimination and the associated operating thresholds transfer to a held-out institution and an external population. This study is limited to that evaluation; it does not propose a new segmentation or calibration method.

Operative summary of the claim (v0.5; the primary estimand and the threshold-transfer population are the four single-missing conditions C4, with Full as a supporting control):

> A pre-registered empirical evaluation of whether ensemble-disagreement confidence ranks case-level enhancing-tumour segmentation failures within fixed, simulated single-missing-sequence conditions for a modality-dropout nnU-Net, how this varies by which sequence is missing, and whether this ranking and a validation-derived operating threshold hold on a held-out institution and an external population.

Prior complete-input literature suggests a positive primary result is plausible. The per-condition, external and transfer analyses carry the scientific weight.

## 24. Reproducibility plan

- **Every run records:**
  - an `EXP-xxx` ID
  - git commit and config hash
  - nnU-Net version and plans file
  - split file hashes; the SHA-256 of the crosswalk and of `UCSF-PDGM-metadata_v5.csv` actually used; the §6.2 screen output (flagged pairs, decisions, final patient groups)
  - GPU, CUDA, PyTorch and Python versions
  - wall-clock time and peak memory
  - per-unit metric CSVs, one row per case-condition-region unit: case ID, patient-group ID, condition, region, metrics, U1/U2/U3 and I scores
- Only IDs and metrics are committed. No images, predictions, checkpoints or licensed metadata files are committed.
- Kaggle notebooks clone a tagged commit.

## 25. Revision and amendment log

| Date | Version | Section(s) | Change | Reason | Test data seen? |
|---|---|---|---|---|---|
| 2026-09-27 | v0.1 | all | Initial draft | [12_PRE_PROTOCOL_AUDIT.md](12_PRE_PROTOCOL_AUDIT.md) | No |
| 2026-09-27 | v0.2 | §1 | Research question replaced with the within-condition, case-level, transfer formulation | The pooled question cannot isolate information beyond missingness identity (13 §8) | No |
| 2026-09-27 | v0.2 | §2–3, §13–14 | Two co-primaries (H-SEG, H-REL pooled; α = 0.025 each) replaced by a single primary H-W (mean within-condition ET ΔAURC; α = 0.05; 95% CI). Former S11 promoted. Families redefined; Holm within family only. | Joham et al. UNSURE 2026 (pooled vs within-group ranking); 13 §8 items 1, 3, 5–8 | No |
| 2026-09-27 | v0.2 | §2.3, §4 | H-SEG demoted to supporting/sanity (full-input TOST retained). Pooled U1 vs I demoted to descriptive S12, with I-then-U1 ranker and S13 mixture-weight sensitivity added. | H-SEG replicates [C6–C8]; pooled AURC depends on arbitrary weights | No |
| 2026-09-27 | v0.2 | §2.3, §4 S4 | H2 and ECE/Brier reframed as replication | MMA-LTS (MICCAI 2026) already evaluates voxel-level calibration per missing combination and region | No |
| 2026-09-27 | v0.2 | §5–7 | HOI = all **511** site-1 UPenn-origin cases (403 + 108); development = **740**; crosswalk file recorded, not committed | TCIA crosswalk; prevents same-institution leakage | No |
| 2026-09-27 | v0.2 | §5, §8 | BraTS-Africa = 95 glioma (v2 release); 51 OtherNeoplasms excluded; expected labels 1/2/3 pending file verification | TCIA v2 metadata; BraTS 2023 label documentation | No |
| 2026-09-27 | v0.2 | §4 S7, §21 | Threshold transfer redefined: Δrisk / Δcoverage with independent bootstraps; 80% primary, 70% and 90% sensitivity; unsafe/inefficient transfer rules | The v0.1 rule ignored validation sampling error and coverage drift (13 §8 item 11) | No |
| 2026-09-27 | v0.2 | §4 S5 | Volume failure renamed "RANO 2.0-motivated…"; 65% sensitivity added; 1 mL labelled a study choice | RANO 2.0 thresholds concern longitudinal change (13 §7 item 9) | No |
| 2026-09-27 | v0.2 | §4 | Removed mirroring-TTA, QU-BraTS score and lesion-wise Dice. C15 limited to internal test and arm B. | Not needed for the research question; compute | No |
| 2026-09-27 | v0.2 | §17, §20 | Compute re-estimated for the 511-case HOI; SR6–SR8 added | 13 §10 | No |
| 2026-09-27 | v0.2 | §23 | Novelty statement rewritten to acknowledge MMA-LTS, SimMLM/MoFe, Joham 2026, Zenk 2025, BraTS-GoAT and the accuracy/volumetry literature | 13 §9 | No |
| 2026-09-27 | v0.2 | checklist | Checklist replaced with the 7 open items from 13 §11 | Earlier items resolved or superseded (MoFe/PNDC correction, UPenn count, Africa count, RANO check) | No |
| 2026-09-28 | v0.3 | §5–§7, §11, §13–§14, §16, §18, §22 and directly affected wording (header, checklist, §4 S7, §15, §20 SR3/SR7, §21, §23 summary, §24) | Added the patient-group split/bootstrap rule and the verified UCSF follow-up groups (A: 00626 + 00758; B: 00639 + 00557). Added the pre-split label-only same-patient screen (threshold and review procedure to be pre-specified before split creation). Resolved the secondary Holm/CI inconsistency (bootstrap p-values, Holm within family, F3b added for coverage). Defined deterministic U1 threshold tie handling (τ_q ≥ rule). Corrected the U1 limitation wording. Updated the BraTS 2021 licensing description and the private third-party re-hosting status. Corrected BraTS-Africa collection/version terminology. Updated limitations. Research question, H-W and primary endpoint **unchanged**. | [15_PREFREEZE_VERIFICATION_REPORT.md](15_PREFREEZE_VERIFICATION_REPORT.md) A1–A5; owner authorization 2026-09-28 | **No.** No test, held-out-institution or BraTS-Africa evaluation data were used. Only public identifier/metadata files were consulted. |
| 2026-09-28 | v0.3 (clarification, no version change) | §6.2, §11, §22 (item 4) | **U1 wording:** "continuous in general" replaced by "can take many distinct values, but is discrete because it is computed from finite binary masks" (no change to the U1 definition, the 0.5 threshold, empty-mask handling or the τ_q rule). **§6.2 wording:** the screen is made explicit as an ordered, label-only, pre-split procedure: permitted inputs; all development pairs; flagging with the frozen T_screen; pre-specified manual review; transitive grouping; freeze before the split. It is stated to be a safeguard that cannot guarantee complete duplicate detection. **T_screen and the review procedure remain TO BE PRE-SPECIFIED BEFORE SPLIT CREATION** (no project source supports a value; none invented). | Owner instruction 2026-09-28 (technical precision; A1 explicitness) | **No.** No data accessed; no experiment run. |
| 2026-09-28 | **v0.4 (substantive)** | Header, lifecycle gates (replacing the pre-freeze checklist), §2.1, §2.2 (H-W-ext, H4), §3, §4 (S1, S2, S9), §5 notes/§5.1/§5.2 gate references, §6.2, §8, §10, §13, §14, §19, §21, §22 (11, 13), §23 references, §24 | **Primary estimand changed:** H-W now averages the four single-missing conditions C4 = {−T1, −T1c, −T2, −FLAIR}; Full stays in C5 as a supporting/control condition, reported separately and excluded from the estimand and from F1. **H4** is made descriptive (F5 descriptive, no α spent). **§19** confident failure = U1 ≥ τ_0.20 (τ_0.80 unchanged as the primary operating point). **Terminology:** case / case-condition unit for evaluation; patient group for split, stratification and bootstrap. **T_screen rule frozen** (the minimum WT-Dice of positive-control pairs A and B; value computed once at gate B7). **Manual-review procedure frozen** (reviewer names are placeholders). **Lifecycle** restructured into gates A–D. **Literature status:** LNCS 15354 volume verified (owner, official Springer page); chapter screen pending; PNDC full text still unverified. U1, AURC, the bootstrap method, C5, models, seeds, the missingness policy and the τ_0.80/0.70/0.90 transfer analysis are unchanged. | Owner decisions following [17_V0.3_FINAL_CONSISTENCY_AUDIT.md](17_V0.3_FINAL_CONSISTENCY_AUDIT.md) | **No.** No data accessed; no split; no experiment; no test, HOI or BraTS-Africa evaluation. |
| 2026-09-28 | **v0.5 (substantive)** | Header, §4 S7, §4 S13, §19 (τ_0.20 population note), §22 (9) | **S7 validation population changed from C5 to C4** (equal condition weighting). **Full is excluded from τ_q estimation** and does not influence the missing-sequence threshold. Target Δrisk/Δcoverage are computed on each target set's C4 units. **S13 now applies to the descriptive pooled S12 (C5) only**; S7 is excluded from the mixture sensitivity, and no new C4 weights are introduced. τ_0.20 (§19) inherits the S7 validation population. The τ_q rule, q values, no interpolation or random tie-breaking, validation-only estimation, independent bootstraps, Δ definitions and the F3/F3b Holm rules are unchanged. H-W, C5, S12, BraTS-Africa, H4 and T_screen are unchanged. | Owner decision 2026-09-28 (consistency of S7 with the C4 primary estimand) | **No.** No imaging or label-volume dataset data were accessed for experiments. No training, split, test, HOI or BraTS-Africa evaluation occurred. |
| 2026-09-28 | v0.5 (documentation/statistical-consistency cleanup; no version change) | Header, provenance statement, §2.2 H-T, §10, §13 (note on I), §17.1, §22 (numbering), §23 summary label | **v0.5 content (recorded again for completeness):** the S7 validation population changed from C5 to C4; Full is excluded from τ estimation; S13 is restricted to S12; τ_0.20 inherits the C4 validation population. **Cleanup:** the header now separates the v0.5 reason from the retained v0.4 history. The provenance statement now reads "no study imaging or label-volume data downloaded; only public identifier/metadata files retrieved during verification". H-T is reworded as an assessment of evidence of adverse transfer, and non-significance establishes neither safety nor equivalence. §10: C5 is called "evaluation conditions", C4 is named as the primary estimand subset and the S7 population. §13: I is explained as a constant-score random-ranking baseline within condition. §17: "Primary inference" is renamed "Planned C5 inference/computation" (estimate unchanged). §22 is renumbered sequentially without content change: the former item 13 is now 12 and the former 12 is now 13, so earlier log references to "§22 (13)" refer to the current item 12. The operative-summary label is updated to v0.5. **No change** to H-W, C4/C5, S7 mathematics, T_screen or the estimands. | Owner instruction 2026-09-28 | **No.** No imaging or label-volume dataset data were accessed for experiments. No training, split, test, HOI or BraTS-Africa evaluation occurred. |
| 2026-09-28 | v0.5 (cleanup; no version change) | §2.3, §4 (supporting line), §13 (supporting analysis) | The formal full-input **TOST is removed**, because it conflicted with the descriptive-only status of the A-versus-B comparison. It is replaced by a descriptive sanity analysis: the 95% CI of the B-versus-A ET Dice difference (Full condition) against the pre-specified ±1.5 Dice-point margin, with no equivalence test and no α. The v0.2 log row's mention of a "full-input TOST" is historical and superseded by this entry. No endpoint, estimand, C4/C5, S7 or T_screen change. | Owner instruction 2026-09-28 (internal consistency) | **No.** No imaging or label-volume data accessed; no training, split or evaluation. |
| 2026-09-28 | v0.5 (final pre-freeze administrative/statistical-consistency changes; no version change) | Lifecycle gates A6–A8, §13 (supporting analysis), §23 (reference sentence) | **A6:** reviewer identities were **not** added, because the owner decision form contained unfilled template text ("[ENTER NAME HERE]"); A6 remains OPEN and none is invented. **A7: OWNER-WAIVED** (LNCS 15354 chapter list inaccessible; surrogate screen found no material overlap; mandatory pre-submission re-check of BraTS 2024 / BrainLes chapters). **A8: OWNER-WAIVED** (PNDC full text inaccessible; abstract and official code show no case-level reliability analysis; mandatory full-text re-check before submission if access becomes available). **§13:** the descriptive B-vs-A Dice sanity analysis now reports the patient-group bootstrap 95% CI only; the Wilcoxon signed-rank statistic/p-value is removed. No endpoint, estimand, conclusion, H-W, C4/C5, S7 or T_screen change. | Owner decisions 2026-09-28 following [19_GATE_A_CLOSURE_AUDIT.md](19_GATE_A_CLOSURE_AUDIT.md) | **No.** No study imaging or label-volume data accessed; no split, training or evaluation. |
| 2026-09-28 | v0.5 (pre-freeze administrative entry; no version change) | Lifecycle gate A6, §6.2 (reviewer line) | **A6 closed.** Primary reviewer = **Ayush Kushwaha**; second reviewer = **Dr. Sreenivasa Chakravarthi**, confirmed by the owner. The §6.2 reviewer placeholders are replaced with these names. The review procedure (categories, disagreement handling, conservative linking of UNRESOLVED, transitive grouping, IDs-only record, freeze before split, never-inspect list) is unchanged. No scientific design changed. | Owner confirmation 2026-09-28 | **No.** No study imaging or label-volume data accessed; no split, training, inference, evaluation or EXP-001 occurred. |
| 2026-09-28 | v0.5 (pre-freeze documentation/statistical-consistency entry; no version change) | §4 S3, lifecycle gate D heading, §23 (search date), §4 S8, §11 (I scope) | **S3:** the "before freeze" deadline is replaced; HD95 now uses the BraTS evaluation convention implemented by the evaluation code pinned at gate C6, with empty-mask behaviour verified before `eval-v1` is tagged (no numerical convention stated). **Gate D heading:** "independent of freeze" → "after B1 approval; before main training" (D1–D6 unchanged). **§23:** search date now "2026-09-27 and 2026-09-28" (claim substance unchanged). **S8:** external per-condition components are stated to be descriptive; only the pre-specified external means are tested in F2 (F2 membership unchanged). **§11:** I's cross-condition use is stated as S12 and S14 (definition unchanged). No endpoint, estimand or scientific design changed. **A9 remains open.** | Owner instruction 2026-09-28 following the A9 pre-freeze consistency audit | **No.** No data were accessed; no split was created; no training, inference or evaluation occurred. |
| 2026-09-28 | **v1.0 — FROZEN** | Header (version, freeze date, freeze basis, previous versions), freeze rule, gate A9, provenance note (status at freeze) | **A9 closed: owner approved the v0.5 text as the final frozen protocol.** Frozen as v1.0 and tagged `protocol-v1.0`. The freeze rule now states that subsequent changes require a logged §25 amendment, and that gate B–D execution records are appended as administrative entries. **No change** to the research question, H-W, C4/C5, S7, the τ rules, T_screen, patient grouping, datasets, models, preprocessing, missingness policy, U1/I, endpoints, statistical procedures, multiplicity, compute budget, stopping rules, interpretation rules, novelty statement, A7/A8 waiver wording or reviewer identities. | Owner A9 approval 2026-09-28 | **No.** No study imaging or label-volume data accessed; no split, duplicate screen, training, inference, evaluation or EXP-001 occurred. |

## Key references for revisions

- MMA-LTS: https://papers.miccai.org/miccai-2026/0659-Paper1236.html
- SimMLM / MoFe: https://arxiv.org/abs/2507.19264
- Joham et al., UNSURE 2026: https://papers.miccai.org/miccai-2026-sat/UNSURE2026_036.html
- Zenk et al. 2025: https://arxiv.org/abs/2406.03323
- BraTS-GoAT reliability study: https://arxiv.org/abs/2608.13223
- TCIA BraTS 2021 crosswalk page: https://www.cancerimagingarchive.net/analysis-result/rsna-asnr-miccai-brats-2021/
- TCIA BraTS-Africa: https://www.cancerimagingarchive.net/collection/brats-africa/
- RANO 2.0 operational summary (AJNR 2024): https://www.ajnr.org/content/45/12/1846
