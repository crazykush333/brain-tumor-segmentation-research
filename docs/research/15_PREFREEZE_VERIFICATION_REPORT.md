# 15 — Pre-Freeze Verification Report

Verification date: 2026-09-27/28 (search and metadata access on those dates).
Object: [FINAL_RESEARCH_PROTOCOL.md](archive/FINAL_RESEARCH_PROTOCOL_v0.5_SUPERSEDED.md) **v0.2 — not modified by this report.**

Evidence labels used throughout:

- **VERIFIED** — checked against a primary or official source or file.
- **INFERENCE** — reasoned from verified facts.
- **ESTIMATE** — a projection.
- **UNVERIFIED** — could not be checked.
- **UNKNOWN** — cannot currently be determined.

## 1. Owner authorization

"FINAL_RESEARCH_PROTOCOL.md v0.2 is approved by the project owner for pre-freeze verification and closure work. It is not yet frozen."

(Owner message received during this task. Authorized: literature and PNDC verification, crosswalk and BraTS-Africa verification, licensing verification, scientific/statistical audit, the EXP-001 specification, and this report. Not authorized: training, preprocessing, final splits, test or external evaluation, freeze, tagging.)

## 2. Executive verdict

**MINOR AMENDMENT REQUIRED**

The research question and H-W survive the literature falsification: no located paper performs within-condition, case-level failure discrimination under missing MRI sequences.

Five text corrections are needed before freeze (§13):

1. **A1 (substantive, leakage):** the protocol assumes "one BraTS subject = one patient". Official TCIA UCSF-PDGM metadata shows **two same-patient pairs inside the development pool**.
2. **A2:** a statistical inconsistency between the threshold-transfer rule and Holm correction.
3. **A3:** τ tie-handling is undefined, and one U1 limitation is misstated.
4. **A4:** the BraTS 2021 access/licence wording is outdated.
5. **A5:** the BraTS-Africa "v2 release" wording is inaccurate.

None changes the research question, H-W, or the endpoint structure.

## 3. Pre-freeze checklist

| # | Item | Status | Evidence | Remaining action |
|---|---|---|---|---|
| 1 | BrainLes / BraTS 2024 | **PARTIALLY CLOSED** | No LNCS BrainLes/BraTS 2024 volume is indexed in Crossref (queried 2026-09-27); brainlesion-workshop.org is unreachable (Cloudflare error 1000). Surrogate screen of arXiv (11 queries, 76 unique records) plus the earlier complete screens of MICCAI 2025/2026, UNSURE 2025/2026 and BraTS 2025: no paper performs within-condition case-level failure detection under missing sequences (§4). | Owner decision: **waive** with a documented surrogate screen, or re-screen when the LNCS volume is indexed. Re-check before submission regardless. |
| 2 | PNDC full text | **PARTIALLY CLOSED — FULL TEXT UNVERIFIED** | Metadata and abstract VERIFIED (Crossref, Europe PMC). Not open access; no PMC copy; IEEE PDF request returned HTTP 418. | Obtain via institutional access, or owner waiver based on the abstract (§5). |
| 3 | BraTS 2021 crosswalk | **COUNTS VERIFIED; HASH PENDING (data milestone); NEW LEAKAGE ISSUE** | 1,251 training; site 1 = 511 (403 + 108); development = 740; no duplicated TCIA patient IDs; SHA-256 of the copies fetched 2026-09-27 and 2026-09-28 are identical (§6). **Two same-patient pairs in development** (UCSF-PDGM metadata v5). | Record the SHA-256 of the exact file used at split time. Adopt amendment A1. |
| 4 | BraTS-Africa | **PARTIALLY CLOSED** (metadata verified; file-level pending) | TCIA metadata: 95 Glioma / 51 OtherNeoplasms; 4 sequences; 146 subjects / 730 processed series (§7). The collection page states **Version 1**. | File-level check of label values, sequence completeness and the eligible count, at the data milestone (download not authorized now). |
| 5 | Licensing | **PARTIALLY CLOSED** | TCIA lists the BraTS 2021 challenge package as **CC BY 4.0**, public download. TCIA Data Usage Policy and BraTS/Synapse citation terms VERIFIED. Private Kaggle re-hosting is **not explicitly addressed** by either (§8). | Confirm with the TCIA helpdesk; adopt amendment A4 wording; owner chooses the storage route. |
| 6 | EXP-001 | **Not yet authorized (spec prepared)** | [EXP-001_COMPUTE_PILOT_SPEC.md](../experiments/EXP-001_COMPUTE_PILOT_SPEC.md) | Owner authorization, which also requires a data-acquisition decision (item 5). |
| 7 | Owner approval | **Pending for v1.0** | v0.2 approved for pre-freeze verification only. | Owner decision on the amendments, then the freeze. |

## 4. BrainLes / BraTS 2024 literature audit

**Locating the proceedings.** VERIFIED negative result:

- Crossref book searches (2025–2026) returned BrainLes **2023** (LNCS, 978-3-031-76160-7), BraTS 2023 proceedings (978-3-031-76163-8) and the BraTS/BrainLes **2025** volumes (978-3-032-16365-3, 978-3-032-16370-7), but **no 2024 volume**.
- The researchr.org page for BrainLes 2024 lists no papers.
- The official workshop site was unreachable.
- Status of the 2024 proceedings: **UNKNOWN** (possibly unpublished or not indexed).

**Surrogate screen.** arXiv API queries, run 2026-09-28:

- `all:"BraTS 2024"`
- `all:BrainLes AND all:2024`
- `abs:"BraTS-2024"`
- missing-modality × {uncertainty, calibration, reliability}
- `"missing sequences" AND segmentation`
- `"incomplete modalities" AND uncertainty`
- `"failure detection" AND modality AND segmentation`

This gave 76 unique records, all titles screened. Abstracts were read for the potentially relevant ones:

| Paper | Venue / ID | Missing-modality setting | Uncertainty / level | Calibration | AURC | Within-condition | Indicator baseline | External | Threshold transfer | Relevance to H-W |
|---|---|---|---|---|---|---|---|---|---|---|
| XLSTM-HVED (Zhu et al.) | arXiv 2412.07804; BraTS 2024 data | Yes (reconstruction + segmentation) | No | No | No | No | No | No | No | Accuracy only |
| Brain Tumour Removing and Missing Modality Generation using 3D WDM (Ferreira et al.) | arXiv 2411.04630; BraTS 2024 tasks 7/8 | Synthesis | No | No | No | No | No | No | No | Synthesis only |
| MRI Feature-Based Subtyping and Model Ensemble (Jiang et al.) | arXiv 2412.04094; MICCAI-BraTS 2024 | No | No | No | No | No | No | No | No | None |
| Optimizing … MedNeXt: BraTS 2024 SSA and Pediatrics | arXiv 2411.15872 | No | No | No | No | No | No | No | No | None |
| UniME (Song et al.) | CVPR 2026; arXiv 2604.22177; BraTS 2023/2024 | Yes | No | No | No | No | No | No | No | Accuracy only |
| CLoE (Tong et al.) | arXiv 2603.09316 | Yes | Expert-consistency gating (training) | No | No | No | No | "cross-dataset generalization" (abstract) | No | Method; consistency is used for fusion, not evaluated as case-level QC |
| MultiMAE for Brain MRIs (Erdur et al.) | arXiv 2509.11442 | Yes (missing inputs) | No | No | No | No | No | No | No | Accuracy only |
| Shapley-derived agreement and uncertainty (Ren et al.) | arXiv 2512.07224; BraTS 2024 | Contrast attribution by perturbation | Shapley-rank variance across CV folds | No | No | No | No | No | No | Interpretability. Relates uncertainty to Dice > 0.6 but has no missingness-conditioned failure ranking. |
| **Lost in the Folds** (Kirscher et al.) | MICCAI 2026; arXiv 2605.18329 | No | Deep ensemble vs CV ensemble: calibration, failure detection | Yes | Failure detection (metric not verified) | No | No | Distribution shift | No | **Supports** our design: seed-based deep ensembles on a fixed training set are recommended for failure detection (as in §9 of the protocol) |
| SimMLM, BMDS-Net, SIUM, No Modality Left Behind, Bridging the Gap | previously audited | Yes | See [13](13_PRE_FREEZE_AUDIT.md) | — | — | No | No | — | — | No change |

**Verdict for item 1.** No located paper invalidates or narrows H-W beyond the narrowing already recorded in [13](13_PRE_FREEZE_AUDIT.md) (MMA-LTS). The formal BrainLes/BraTS 2024 volume remains unscreened. Arguably most BraTS 2024 participant papers appear on arXiv [INFERENCE], but this is not guaranteed.

## 5. PNDC verification

- **VERIFIED (Crossref, Europe PMC):**
  - Qiu Y., Jiang K., Yao H., Wang Z., Satoh S.
  - "Does Adding a Modality Really Make Positive Impacts in Incomplete Multi-Modal Brain Tumor Segmentation?"
  - IEEE TMI 44(5):2194–2205, May 2025; DOI 10.1109/TMI.2025.3526818; PMID 40031068; licence: IEEE standard (not open access).
- **Abstract content (VERIFIED as abstract text only):**
  - PNDC is a training pipeline ("Reverse Audit" + "Forward Checksum").
  - It identifies negative-impact regions of each modality, then checks whether the fusion prediction is reliable in those regions using positive-impact regions of the other modalities.
  - These regions are used to "enhance the learning of individual modalities and fusion process".
  - It adds no learnable parameters and is plugged into existing incomplete-modality training.
- **FULL TEXT UNVERIFIED.** Therefore UNKNOWN from the full text:
  - the exact meaning and level (voxel/region) of "calibration";
  - whether any case-level uncertainty, failure detection, AURC/e-AURC, within-condition analysis, indicator comparison, external data or threshold transfer appears.
- **INFERENCE (abstract only; not a full-text finding):** the abstract describes a training-time fusion correction evaluated by segmentation performance. It mentions no case-level reliability evaluation, so direct overlap with H-W appears unlikely. This is not confirmed.

## 6. BraTS 2021 crosswalk audit

- **Source (VERIFIED):** TCIA analysis-result page "RSNA-ASNR-MICCAI-BraTS-2021" (DOI 10.7937/jc8x-9874). File "ID Crosswalk map between BraTS ID and TCIA ID", `BraTS2021_MappingToTCIA.xlsx`, 78.12 KB, listed as **CC BY 4.0**. HTTP Last-Modified: Thu, 14 Sep 2023 06:07:11 GMT; Content-Length: 80000.
- **SHA-256 of the copies downloaded 2026-09-27 and re-downloaded 2026-09-28** (VERIFIED identical): `223243c5821c282e90da980ba38d860ab2d2a597d1f4f1800ebe227329a2dc0b`.
  - This is recorded for provenance only. The checklist requires the hash of **the exact file used at split time**. That remains pending and must be re-computed then.
  - The file is held in session scratch space, **not committed**.
- **Columns:** Data Collection, Site ID, TCIA PatientID, Study date, BraTS2021 ID, Segmentation cohort, MGMT cohort, MGMT value.
- **Counts (VERIFIED from the file):**

| Quantity | Value |
|---|---|
| Segmentation "Training" rows | 1,251, all BraTS IDs unique |
| Site 1 training cases | 511 (`UPENN-GBM` 403 + `UPENN-GBM_Additional` 108) |
| `UPENN*` rows outside site 1 | none |
| Non-`UPENN*` rows in site 1 | none |
| Development = 1,251 − 511 | **740** |
| Site 18 (UCSF) training cases | 382 (`UCSF-PDGM` 263 + `UCSF-PDGM_Additional` 119), all in development |

- **Duplicates (VERIFIED):**
  - Among the 900 training rows with real TCIA patient IDs, **no ID repeats**.
  - **351 training rows carry the placeholder "new-not-previously-in-TCIA"**: 243 in development, 108 in site 1. Patient identity **cannot** be checked from the crosswalk for these rows (UNKNOWN).
- **Same-patient pairs (VERIFIED from TCIA `UCSF-PDGM-metadata_v5.csv`, SHA-256 `afc1c23a…6fd78`, fetched 2026-09-28).** TCIA states six UCSF-PDGM IDs are follow-up scans of other subjects. Two such pairs are **both** in BraTS 2021 training, and both are at site 18 (development):
  - UCSF-PDGM-433 = **BraTS2021_00626** and UCSF-PDGM-0433_FU007d = **BraTS2021_00758** (7 days apart)
  - UCSF-PDGM-429 = **BraTS2021_00639** and UCSF-PDGM-0429_FU003d = **BraTS2021_00557** (3 days apart)
  - In the other four pairs only one member is in BraTS 2021.

  Consequence: development = 740 **cases**, but at most **738 patients** (VERIFIED for these pairs; further duplicates among placeholder rows are UNKNOWN). The protocol text "One BraTS subject is treated as one patient" is therefore **incorrect**, and a random case-level split could place one scan in train and its near-identical follow-up in test. → Amendment A1.

## 7. BraTS-Africa audit

**VERIFIED from official metadata** (TCIA collection page and `BraTS-Africa_TCIA_datainfo_v2.xlsx`, SHA-256 `74ac283b…645eb`):

- 146 subjects; sheets "95 Glioma" and "51 OtherNeoplasms". The 51 are separate: meningioma, ventricular masses, metastases and others.
- Glioma sheet: 4 centres (NKDC 48, CRV 28, MEDHUB 14, LASUTH 5); scanners Siemens Magnetom Essenza, GE SIGNA Creator, Philips Achieva.
  - Recorded number of tumour sub-region labels per case: 3 = 89, 2 = 5, 1 = 1; one row blank.
  - Some cases therefore lack one or more sub-regions (e.g. no ET).
- Sequences: "T1, T1 CE, T2, and T2 FLAIR, acquired on 1.5T".
  - The processed release "Radiology Images and Segmentations – BraTS 2023 Challenge" lists 146 subjects and 730 series. 730 = 146 × 5 is **consistent with** 4 sequences + 1 segmentation per subject [INFERENCE, not a file check].
  - The page states that all scans passed sanity checks for "the presence of all required sequences".
  - Native slice thickness is 3–5 mm before resampling to 1 mm, a relevant acquisition shift.
- **Version:** the collection page states **"Version 1: Updated 2024/09/04"**. "v2" refers to the **metadata spreadsheet filename** only. → Amendment A5.
- Licence: processed release CC BY 4.0. Unprocessed NIfTI is under limited access (NIH Controlled Data Access Policy), and is not needed.

**VERIFIED from documentation, pending file check:** BraTS 2023-era convention 1 = NETC, 2 = SNFH, 3 = ET (BraTS 2023 challenge descriptions, including BraTS-Africa, arXiv:2305.19369). The TCIA page does not state label values.

**REQUIRES FILE-LEVEL VERIFICATION** (not done; download not authorized):

- the actual label values;
- presence of all four sequences for each of the 95 cases;
- the final eligible count, which is only knowable after inspection. The blank metadata row also needs resolving.

## 8. Licensing audit

This is a report of the terms, not legal advice.

**BraTS 2021 challenge data (TCIA): VERIFIED.**

- "Challenge data both tasks" (1,480 subjects, DICOM + NIfTI, 142 GB, Aspera download) and the crosswalk are listed as **CC BY 4.0**.
- Only the linked *original source DICOMs* of some collections fall under the NIH Controlled Data Access Policy. We do not need those.
- The v0.2 phrase "TCIA Restricted License Agreement" reflects an older TCIA wiki arrangement and appears **outdated** for the challenge package [INFERENCE from the current page]. → Amendment A4.

**TCIA Data Usage Policy: VERIFIED.** Users must:

- not identify or contact participants;
- not generate or use facial images or comparable representations that could reveal identity;
- cite the dataset DOI;
- review TCIA's **Data Analysis Centers** page before "mirroring a copy of our publicly available datasets or providing direct access to any of our data via another tool or website".

**BraTS 2021 Synapse rules (syn25829067, "Rules & Resources" wiki): VERIFIED.**

- Participants abide by the Synapse Governance documents and Terms and Conditions of Use.
- Data use is free "in your own research" provided the listed manuscripts are cited.
- Required acknowledgement text refers to Synapse ID syn25829070.
- The data entity requires an authenticated account; anonymous READ was denied (VERIFIED).
- The restriction on extra training data applies to challenge ranking, not to later publications.

**Assessment by workflow element:**

| Element | Assessment |
|---|---|
| Kaggle notebooks, temporary/local processing, cloud processing | No term found prohibiting processing under CC BY 4.0 + TCIA policy [INFERENCE] |
| **Private Kaggle dataset** | CC BY 4.0 permits copying and redistribution with attribution. A private (owner-only) dataset is arguably not "providing access" to others. **However, neither TCIA nor Synapse terms explicitly address private re-hosting on a third-party platform: AMBIGUOUS.** A **public** Kaggle mirror would fall under the TCIA mirroring/DAC clause and is **not recommended**. |
| **Per-session download** | The TCIA challenge package is 142 GB (both tasks, Aspera). That exceeds typical Kaggle notebook disk [ESTIMATE; verify in EXP-001], so per-session download from TCIA is **operationally infeasible** [INFERENCE]. Synapse per-session download needs account credentials inside notebooks; treat credentials as secrets and never commit them. |
| Derived predictions and metrics | Aggregate metrics and ID-level CSVs: no restriction found beyond citation. Prediction masks are derived data; keep them out of the public repository. |
| Model checkpoints | Terms do not address trained weights: **UNKNOWN**. Conservative choice: do not publish weights before confirming with the providers. |
| Public GitHub code; sharing BraTS/TCIA identifiers | The crosswalk itself is CC BY 4.0. Committing ID lists (splits) appears compatible with attribution [INFERENCE]. Do not commit images, masks, the crosswalk file (not needed) or credentials. |

**Most conservative supported workflow:**

1. Obtain the official Task-1 NIfTI data once, from TCIA (Aspera, local or controlled storage) or Synapse (authenticated).
2. Verify against official file lists and hashes.
3. **Before** any re-hosting, email the TCIA helpdesk to ask whether a private, non-shared Kaggle dataset copy is acceptable.
4. If confirmation is not obtained, run compute where the data can be staged without re-hosting (e.g. Colab with a personal Google Drive copy), with the same question considered for that route.
5. Never use unofficial Kaggle mirrors as the source of record.

Checklist 5 remains **PARTIALLY CLOSED** until that confirmation or an owner risk decision (SR7).

## 9. H-W scientific audit

| # | Question | Finding |
|---|---|---|
| 1 | Beyond missingness identity? | **Yes, by construction.** Within condition c, I is constant, so AURC_c(I) is the expected random-ranking AURC (the mean risk). ΔAURC_c < 0 can only come from within-condition ranking by U1. **Caveat:** H-W is therefore equivalent to "U1 ranks better than chance within each condition". Given the complete-input literature (Zenk 2025; BraTS-GoAT 2026; Lost in the Folds 2026), a positive primary result is **expected** [INFERENCE]. The informative results are the per-condition components (especially −T1c), the external replications (F2) and transfer (F3). The protocol's §21 already treats per-condition differences as supporting results. |
| 2 | I correctly defined? | Yes (§11): −(validation mean risk of the condition), same arm's ensemble. Its value is irrelevant within condition and matters only for S12/S14. |
| 3 | I from validation only? | Yes (§11, §18). |
| 4 | Internal test untouched? | Yes. No splits exist, and the protocol forbids evaluation before v1.0. |
| 5 | Bootstrap coherent? | Yes. Patients are resampled with all conditions (§13). Resampled duplicate patients create ties, handled by the §3 expected-tie rule. After amendment A1, the resampling unit should be the **patient group**. |
| 6 | Averaging five ΔAURC_c? | Coherent as a pre-defined estimand (unweighted mean over C5). Raw ΔAURC scales with each condition's risk spread, so conditions with more heterogeneous risk dominate. This is an interpretive limitation, not an error. Optional (not required): report the normalized per-condition ratio ΔAURC_c / (AURC_c(I) − AURC_c,optimal) descriptively. |
| 7 | U1 defensible? | Yes. Pairwise-DSC between ensemble members was the best-performing case-level failure-detection score in Zenk et al. 2025. |
| 8 | Are 3 members sufficient? | Adequate but noisy: 3 pairs. It is declared as a limitation, but the declared wording is inaccurate. U1 is **not** coarse-valued: pairwise Dice is continuous. It has **mass points at 1** (all members empty) **and 0** (one member empty, another not). → Amendment A3. |
| 9 | Empty ET handling | Consistent. Risk: both empty → Dice 1; one empty → 0. U1: both empty → 1. Cases where all members predict no ET but GT ET exists get maximal confidence and maximal risk; they are correctly counted as confident failures (§19). Cases where one member predicts a tiny ET and another predicts none get U1 = 0 even if the ensemble mask is correct. This is a mild source of false alarms, acceptable, and should be mentioned in the limitations (A3). U1 depends on the 0.5 threshold per member; declared implicitly (§9). |
| 10 | Trivial correlation? | See item 1. This does not invalidate H-W, but the manuscript must not present a positive H-W as surprising. |
| 11 | −T1c meaningful? | Yes. T1c is the defining sequence for ET, so it is the condition where within-condition ranking is most at risk of failure (hallucinated or missed ET with agreeing members). |
| 12 | External leakage? | None found. UPenn and BraTS-Africa are used only for final evaluation. τ and I come from validation. Datasets are analysed separately (§18, §4). |
| 13 | Threshold transfer | See §10: one inconsistency (A2) and one undefined rule (A3). |
| 14 | Multiplicity | See §10 (A2). |
| 15 | Novelty | See §12. |

## 10. Statistical audit

- **AURC and ties:** defined (§3). Mean selective risk over k/n, with expected tie handling. Correct.
- **Primary test:** single hypothesis, α = 0.05, 95% percentile CI, 10,000 patient-level replicates, decision rule "CI entirely < 0". Coherent. The two-sided CI rule is conservative relative to the one-directional hypothesis; this is acceptable and should be stated.
- **Inconsistency (A2).**
  - §4 S7 declares "unsafe transfer" when the **unadjusted** 95% CI of Δrisk lies entirely above 0.
  - §14 places the same three tests in family F3 with **Holm correction**.
  - Holm operates on p-values, so the two rules can disagree.
  - The same ambiguity applies to F1, F2, F4 and F5: §13 gives a bootstrap p-value only for the primary.
  - Minimum fix: secondary tests use the §13 bootstrap p-value construction; Holm is applied to those p-values within each family; unadjusted 95% CIs are reported descriptively; labels ("unsafe transfer" and the per-condition "<0" claims) are declared only on Holm-adjusted p < 0.05.
- **Threshold transfer (A3).**
  - Independent validation/target bootstraps and fixed τ are appropriate.
  - The validation selective risk is treated as a random quantity (fixed from v0.1).
  - The 80/70/90% coverages are pre-specified.
  - **Undefined:** how τ is set when U1 has ties at the boundary. The mass points at 1 and 0 make exact 80% coverage impossible in general.
  - Minimum fix: τ = the largest U1 value such that validation coverage (units with U1 ≥ τ) is ≥ the target. Report the realized validation coverage. Target coverage is computed with the same ≥ τ rule.
- **External analyses:** separate per dataset, no pooling, no equivalence claims. Correct.
- **Families:** F1–F5 are disjoint and Holm is within family only, with no global FWER claim. Correct once A2 is adopted.

## 11. Leakage / reproducibility audit

**Held-out institution / development separation (VERIFIED):**

- Site 1 = 511 cases, and every `UPENN*` row is at site 1.
- Selecting the development pool by `Site ID ≠ 1` (not by collection name) guarantees no site-1 case enters development.
- Recommend the split script **assert** this, and assert 740 / 511 counts from the hashed crosswalk.

**Within-development duplicates (VERIFIED issue):**

- Two same-patient pairs (§6). The patient-grouping rule in v0.2 relies on TCIA IDs, which are absent for 243 development cases.
- Minimum fix (A1):
  - (i) Hard-code the two verified pairs as patient groups.
  - (ii) Before splitting, run a **label-only same-patient screen** within development. All cases are in SRI24 space, so compute pairwise WT-label Dice between cases, flag pairs above a pre-specified threshold for manual review, and group confirmed pairs.
  - (iii) Split, stratify and bootstrap by **patient group**.
  - (iv) Report the grouping.

  Using ground-truth labels only for grouping, before any model exists, does not leak test information into training decisions [INFERENCE], in the same way as the existing label-based stratification.

**Cross-dataset:**

- Development vs held-out institution: disjoint by site.
- BraTS-Africa vs BraTS 2021: different countries and institutions; overlap very unlikely [INFERENCE]. The image-hash safeguard stays.
- Same-patient follow-ups across *different* sites are implausible [INFERENCE].

**Provenance to record at the data milestone:**

- SHA-256 of the crosswalk and of the UCSF-PDGM metadata file used;
- download manifests and dataset DOIs;
- the nnU-Net version.

**Conflicts with other project documents.** FINAL_RESEARCH_PROTOCOL.md prevails. These documents are older and superseded in part; recommend marking them "superseded by protocol v0.2" at the next documentation update (not done now):

- **[04](04_DATASET_STRATEGY.md):** mentions a UPenn "manually revised subset", UCSF/EGD options and "TCIA Restricted License Agreement".
- **[05](05_EXPERIMENTAL_DESIGN.md):** an EXP matrix with MC-dropout, TTA, a remedy experiment (EXP-040), QU-BraTS and lesion-wise metrics.
- **[06](06_BASELINE_STRATEGY.md):** MC-dropout and TTA baselines.
- **[10](10_RESEARCH_ROADMAP.md):** the roadmap.
- **[11](11_NOVELTY_RISK_ASSESSMENT.md):** pre-MMA-LTS novelty risks.

## 12. Novelty audit

After this verification, no located paper evaluates within-condition case-level failure discrimination under missing MRI sequences.

**Closest works:**

- MMA-LTS: voxel calibration conditioned on missingness.
- Zenk 2025 / BraTS-GoAT 2026 / Lost in the Folds 2026: case-level failure detection with complete inputs.
- Joham 2026: within-site vs pooled evaluation.
- SIUM: configuration-level variance.

**A hostile reviewer's strongest objection:** "Ensemble disagreement is known to rank failures. Applying it separately per missing-sequence condition is an expected extension." This objection is **reasonable**.

**Narrowest defensible claim (recommended wording for the manuscript):**

> "a pre-registered empirical evaluation of whether ensemble-disagreement confidence ranks case-level enhancing-tumour segmentation failures within fixed, simulated single-missing-sequence conditions for a modality-dropout nnU-Net, how this varies by which sequence is missing, and whether this ranking and a validation-derived operating threshold hold on a held-out institution and an external population."

The protocol's §23 wording is consistent with this. No change is required beyond keeping "simulated" explicit, which §22 item 1 already covers.

## 13. Required amendments

**Owner approval is needed to produce v0.3. Nothing has been applied.**

| ID | Section | Current wording (paraphrase) | Problem | Evidence | Minimum correction |
|---|---|---|---|---|---|
| **A1** | §6 (and §7, §13) | "One BraTS subject is treated as one patient. Any duplicate TCIA patient IDs are grouped." | False for ≥ 2 verified pairs; the ID-based rule cannot detect duplicates among 243 placeholder-ID development cases. | TCIA UCSF-PDGM metadata v5 + crosswalk (§6) | Group BraTS2021_00626 + 00758 and BraTS2021_00639 + 00557. Pre-specify a label-only pre-split same-patient screen (pairwise WT-label Dice, threshold, manual confirmation). Split, stratify and bootstrap by patient group. Assert site ≠ 1 and the counts. |
| **A2** | §4 S7, §13, §14 | Unsafe transfer = unadjusted 95% CI > 0, while F3 is Holm-corrected. No p-value procedure is given for secondary families. | Internal inconsistency between the CI rule and Holm. | §10 | Bootstrap p-values for all tested secondaries; Holm within family on those p-values; labels only on Holm-adjusted p < 0.05; unadjusted CIs reported descriptively. |
| **A3** | §4 S7 / §11 / §22 item 4 | τ "giving 80% coverage"; "pairwise Dice takes coarse values" | τ is undefined under ties (mass points at 0 and 1). The limitation is misstated. | §9–10 | τ = the largest U1 with validation coverage ≥ target (≥ rule, realized coverage reported). Replace limitation 4 with: "3 pairs → noisy disagreement; mass points at U1 = 1 (all-empty) and U1 = 0 (discordant empty); discordant tiny-ET predictions can produce false alarms; depends on the 0.5 member threshold." |
| **A4** | §5 table; checklist item 5 | "Synapse / TCIA Restricted License Agreement" | Outdated. TCIA lists the challenge package as CC BY 4.0, public. The 142 GB package makes per-session download infeasible. | TCIA page (§8) | State: CC BY 4.0 (TCIA) / Synapse (authenticated), citation requirements, the TCIA Data Usage Policy, and the pending confirmation on private re-hosting. |
| **A5** | §5 table, §5 notes | "BraTS-Africa, TCIA **v2** release" | The collection is Version 1 (2024/09/04); v2 is the metadata file. | TCIA page (§7) | "TCIA BraTS-Africa collection (Version 1, 2024/09/04; metadata `BraTS-Africa_TCIA_datainfo_v2.xlsx`)". Record that some glioma cases have fewer than 3 labelled sub-regions. |

**Not required, but recommended (owner's choice):**

- a descriptive normalized ΔAURC_c;
- an explicit sentence in §21 that a positive H-W is expected from prior literature and that the per-condition, external and transfer results carry the scientific weight.

## 14. EXP-001 readiness

- The specification is prepared: [../experiments/EXP-001_COMPUTE_PILOT_SPEC.md](../experiments/EXP-001_COMPUTE_PILOT_SPEC.md). It is **not executed**.
- **Blocking dependencies:**
  - (a) the owner authorizes EXP-001;
  - (b) the owner authorizes a data-acquisition route (checklist 5, SR7), since EXP-001 needs real BraTS volumes on the GPU platform;
  - (c) amendment A1 is resolved, because the pilot must draw only from the development pool and must not pre-empt the split.
- The spec restricts the pilot to compute/engineering measurements, with **no segmentation accuracy evaluation**.

## 15. Final recommendation

**Already resolved (VERIFIED):**

- BraTS 2021 counts: 1,251 / 511 (403 + 108) / 740; site-1 purity; no duplicated real TCIA patient IDs.
- BraTS-Africa metadata: 95 / 51, 4 sequences listed, 1.5T, 4 glioma centres.
- Licence of the BraTS 2021 challenge package (CC BY 4.0) and of BraTS-Africa processed data (CC BY 4.0).
- TCIA and Synapse usage and citation terms.
- H-W logic, I definition, bootstrap design and external-analysis separation are coherent.
- No literature found that performs H-W.

**Inferred:** PNDC is unlikely to overlap (abstract only); BraTS-Africa sequence completeness (730 = 146 × 5); per-session TCIA download is infeasible on Kaggle.

**Estimated:** all compute figures (unchanged from v0.2 until EXP-001).

**Unresolved:**

- the BrainLes/BraTS 2024 LNCS volume;
- the PNDC full text;
- the crosswalk hash at split time;
- BraTS-Africa file-level labels and eligibility;
- private Kaggle re-hosting;
- checkpoint-sharing terms;
- same-patient duplicates among placeholder-ID cases (pending the A1 screen).

**Requires owner decision:**

- approve A1–A5, which produces v0.3;
- waive or keep checklist items 1–2;
- choose the data-storage route (email TCIA first);
- authorize EXP-001 after that.

**Before v1.0:**

- adopt A1–A5;
- close or waive items 1, 2 and 5;
- run EXP-001 and confirm the budget;
- at the data milestone, record the hashes and complete the BraTS-Africa file check and the A1 screen, or explicitly schedule them as pre-split gates written into v1.0.

**Must NOT happen yet:** training; final preprocessing; split creation; any test, held-out-institution or external evaluation; v1.0; the `protocol-v1.0` tag; M1 implementation.

No training, split creation, test evaluation, full dataset download, or EXP-001 was performed during this verification pass. Only small public metadata/identifier files were retrieved into session scratch space: the TCIA crosswalk, BraTS-Africa datainfo and UCSF-PDGM metadata. None was committed.

**Next gate:** OWNER REVIEW OF v0.2 + 15_PREFREEZE_VERIFICATION_REPORT.md.

### Sources

- TCIA RSNA-ASNR-MICCAI-BraTS-2021: https://www.cancerimagingarchive.net/analysis-result/rsna-asnr-miccai-brats-2021/ ; crosswalk https://www.cancerimagingarchive.net/wp-content/uploads/BraTS2021_MappingToTCIA.xlsx
- TCIA UCSF-PDGM: https://www.cancerimagingarchive.net/collection/ucsf-pdgm/ ; https://www.cancerimagingarchive.net/wp-content/uploads/UCSF-PDGM-metadata_v5.csv
- TCIA BraTS-Africa: https://www.cancerimagingarchive.net/collection/brats-africa/ ; https://www.cancerimagingarchive.net/wp-content/uploads/BraTS-Africa_TCIA_datainfo_v2.xlsx
- TCIA Data Usage Policies: https://www.cancerimagingarchive.net/data-usage-policies-and-restrictions/
- Synapse BraTS 2021 (syn25829067), "Rules & Resources" wiki, via the Synapse REST API; Synapse Terms: https://s3.amazonaws.com/static.synapse.org/governance/SageBionetworksSynapseTermsandConditionsofUse.pdf
- PNDC: https://doi.org/10.1109/TMI.2025.3526818 ; https://pubmed.ncbi.nlm.nih.gov/40031068/
- BraTS 2023 label convention / BraTS-Africa: https://arxiv.org/abs/2305.19369
- Lost in the Folds: https://arxiv.org/abs/2605.18329 ; UniME: https://arxiv.org/abs/2604.22177 ; CLoE: https://arxiv.org/abs/2603.09316 ; XLSTM-HVED: https://arxiv.org/abs/2412.07804 ; 3D WDM: https://arxiv.org/abs/2411.04630 ; MultiMAE brain: https://arxiv.org/abs/2509.11442 ; Shapley agreement: https://arxiv.org/abs/2512.07224 ; BraTS 2024 subtyping ensemble: https://arxiv.org/abs/2412.04094
