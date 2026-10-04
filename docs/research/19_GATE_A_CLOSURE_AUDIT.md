# 19 — Gate-A Closure Audit (A6, A7, A8)

| Field | Value |
|---|---|
| Audit date | 2026-09-28 |
| Protocol audited | [FINAL_RESEARCH_PROTOCOL.md](archive/FINAL_RESEARCH_PROTOCOL_v0.5_SUPERSEDED.md) **v0.5 — AMENDED PRE-FREEZE DRAFT, awaiting owner approval (NOT FROZEN)** |
| Protocol modified by this audit | **No** |
| Scope | Gate-A items A6 (reviewer identities), A7 (BrainLes/BraTS 2024 chapter-level screen), A8 (PNDC full text); static consistency scan |

Evidence labels:

- **FULL TEXT**: the paper's own text was read or keyword-searched.
- **ABSTRACT ONLY**: the official abstract/metadata only.
- **CODE**: the authors' public repository.
- **METADATA ONLY**: bibliographic record or title only.
- **UNVERIFIED**: could not be checked.

The exact novelty question tested is whether prior work evaluates **case-level reliability under missing MRI sequences** where:

1. sequence(s) are missing at inference;
2. the missing-sequence identity is fixed/known within the evaluation condition;
3. a case-level uncertainty / ensemble-disagreement signal is used;
4. that signal discriminates segmentation failures **within** the fixed condition;
5. preferably, the operating threshold or failure-detection behaviour is evaluated on a held-out institution or external population.

---

## 1. A6 — Manual-review reviewer identities

**Repository search:** all files were searched for "reviewer" (2026-09-28). **No reviewer name is documented anywhere.** The protocol contains only its role placeholders (§6.2): `[PRIMARY REVIEWER — to be named before v1.0]` and `[SECOND REVIEWER — to be named before v1.0, or recorded as unavailable]`. No names were invented.

**Procedure consistency check (§6.2): consistent.**

| Element | Present? | Consistent? |
|---|---|---|
| Categories SAME PATIENT / DIFFERENT PATIENT / UNRESOLVED | yes | yes |
| Decision rule for each category | yes | yes |
| Material inspected / never-inspected list (no predictions, Dice, calibration, test or post-split outcomes) | yes | yes |
| Two-reviewer disagreement procedure (independent second review; unresolved → UNRESOLVED) | yes | yes |
| UNRESOLVED treated as linked for splitting (conservative) | yes (§6.2 step 4 and step 5) | yes |
| Transitive grouping (with groups A and B and shared TCIA IDs) | yes | yes |
| IDs-only record: pair IDs, decision, reviewer, timestamp, reason | yes | yes |
| Frozen before the split (gates B7–B9) | yes | yes |

Minor wording note (not a contradiction): §6.2 and gate A5 say the rule/procedure is "frozen in v0.4" while the protocol as a whole is NOT FROZEN. The intended meaning is "fixed in the pre-registration text; binding at v1.0". It could be clarified at the v1.0 edit.

**A6 status: OPEN.** The owner must provide:

- (a) the **primary reviewer** identity: name, or a role identifier plus name, to be recorded in the experiment metadata;
- (b) the **second reviewer** identity, **or** an explicit statement that no second reviewer is available. In that case disagreements cannot arise and the primary reviewer's UNRESOLVED category governs, as already specified.

## 2. A7 — BrainLes / BraTS 2024 chapter-level screen

### 2.1 Locating the LNCS 15354 chapter listing

| Route | Result (2026-09-28) |
|---|---|
| Crossref: book query (title + "MICCAI 2024 Challenges") | Not found. Returned MICCAI 2024 LISA, HNTS-MRG, ToothFairy, DIAMOND/MARIO and 2025 BraTS volumes. |
| Crossref: chapter queries via companion-challenge topics (MIDI-B de-identification; TBI 2024) | Not found |
| OpenAlex (earlier round, 193 BraTS-2024-related works) | No LNCS 15354 chapters |
| Springer series / search pages | Redirect to login (303), not accessible |
| Springer "LNCS Forthcoming Proceedings 2024–2027" PDF (30 June 2026) | 15354 is not listed (consistent with an already-published volume, which is not a chapter listing) |
| Web search on the exact title / "15354" | Not found |

**Result:** the **existence** of the volume rests on the owner's verification of the official Springer page (recorded in protocol gate A7). **Its chapter listing could not be obtained**, so no chapter of LNCS 15354 could be screened. Evidence level for LNCS 15354 chapters: **UNVERIFIED**.

### 2.2 Surrogate screen of 2024 brain-tumour literature (not a substitute for the chapter screen)

- MICCAI 2024 main conference: all **856** open-access titles were keyword-screened; hits were checked by abstract.
- arXiv BraTS 2024 / BrainLes 2024 queries (report [15](15_PREFREEZE_VERIFICATION_REPORT.md) §4) and an OpenAlex scan (audit [17](17_V0.3_FINAL_CONSISTENCY_AUDIT.md) §5).
- A new arXiv recency screen (5 queries on missing modality/sequence × failure detection / QC / uncertainty / risk-coverage / selective; sorted to Sept 2026).

| Paper | Venue / ID | What it evaluates | Criteria 1–5 met | Evidence |
|---|---|---|---|---|
| Missing as Masking (M³FeCon) | MICCAI 2024, https://papers.miccai.org/miccai-2024/520-Paper0067.html | Incomplete-modality brain-tumour segmentation **accuracy** (BraTS18); feature reconstruction | 1 only | ABSTRACT ONLY |
| Task-conditional MoE for missing-modality segmentation | MICCAI 2024, https://papers.miccai.org/miccai-2024/033-Paper2509.html | MS-lesion segmentation **accuracy** under missing contrasts vs modality dropout | 1 only (and not tumour) | ABSTRACT ONLY |
| XLSTM-HVED | arXiv 2412.07804 (BraTS 2024 data) | Missing-modality reconstruction + segmentation **accuracy** | 1 only | ABSTRACT ONLY |
| 3D WDM (Ferreira et al.) | arXiv 2411.04630 (BraTS 2024 tasks 7/8) | Synthesis / inpainting | none (synthesis) | ABSTRACT ONLY |
| Subtyping + ensemble (Jiang et al.) | arXiv 2412.04094 (MICCAI-BraTS 2024) | Segmentation accuracy, complete inputs | none | ABSTRACT ONLY |
| Shapley agreement/uncertainty (Ren et al.) | arXiv 2512.07224 (BraTS 2024) | Contrast attribution; Shapley-rank variance vs Dice | partial 3 (a different uncertainty notion); no fixed-missing-condition failure ranking | ABSTRACT ONLY |
| "Feeling of Error" (FOE) | ECCV 2026, arXiv 2609.08879 | **Case-level failure detection** (concept activations; incl. brain cancer segmentation); **no missing sequences mentioned** | 3–4 on complete input; not 1–2 | ABSTRACT ONLY |
| CRS-Triage | arXiv 2608.03862 | Selective triage under incomplete **EHR** data (classification) | not segmentation | ABSTRACT ONLY |

No located paper meets criteria 1 + 2 + 3 + 4 together.

**A7 status: OPEN — INSUFFICIENT EVIDENCE for the LNCS 15354 chapters specifically.** The accessible 2024 literature shows **no material overlap**. The owner can either:

- (a) supply the LNCS 15354 table of contents or chapter DOIs (or use institutional access) so the chapter screen can be run; or
- (b) **owner-waive** A7 with the documented rationale: the chapter list is inaccessible; BraTS 2024 challenge papers are largely mirrored on arXiv; surrogate screens of MICCAI 2024 (full title list), arXiv and OpenAlex found no overlap; and a pre-submission re-check is required.

Option (b) is defensible but carries a residual risk: a BraTS 2024 challenge chapter could contain a reliability analysis not posted elsewhere.

## 3. A8 — PNDC full text

| Item | Finding | Evidence |
|---|---|---|
| Citation | Qiu Y., Jiang K., Yao H., Wang Z., Satoh S. *Does Adding a Modality Really Make Positive Impacts in Incomplete Multi-Modal Brain Tumor Segmentation?* IEEE TMI 44(5):2194–2205, 2025. DOI 10.1109/TMI.2025.3526818; PMID 40031068 | METADATA (Crossref, Semantic Scholar, PubMed) |
| Open access? | **No.** Semantic Scholar `isOpenAccess: false`; Unpaywall `is_oa: False`, 0 OA locations; IEEE PDF not retrievable (HTTP 418 earlier); no PMC copy; no copy in the repository | METADATA |
| Full text read? | **FULL TEXT UNVERIFIED** | — |
| Method (abstract) | Training-time "Reverse Audit" + "Forward Checksum" to identify negative/positive-impact regions per modality and "calibrate whether the fusion prediction is reliable in these regions", used to enhance learning. No new parameters. | ABSTRACT ONLY |
| Official code | https://github.com/yansheng-qiu/PNDC: an RFNet-compatible implementation (a BraTS 2023 checkpoint is referenced). `predict.py` computes **per-region Dice** under modality masks only. A keyword search of `train_PNDC.py` found no AURC, risk, coverage, calibration, ECE, uncertainty, failure, external or threshold terms. | CODE |

Answers to the specific questions. Only the abstract and code are available, so every answer is **not confirmed from the paper**:

| Question | Answer |
|---|---|
| Case-level segmentation failure detection? | Not described in the abstract; absent from the evaluation code. UNVERIFIED in the paper. |
| Ensemble disagreement / case-level uncertainty score? | Not described; the region-level "reliability" is a training signal. UNVERIFIED in the paper. |
| Under missing modalities? | **Yes**: incomplete multi-modal segmentation (abstract; code uses modality masks). |
| Missing identity fixed during evaluation? | The code evaluates under supplied modality masks (INFERENCE from code). Not verified in the paper. |
| Within-condition discrimination? | Not described or implemented. UNVERIFIED. |
| AURC / risk-coverage / failure ranking? | Not described or implemented. UNVERIFIED. |
| Threshold transfer? | Not described. UNVERIFIED. |
| Held-out institution / external population? | Not described. UNVERIFIED. |
| Material overlap with H-W? | **No evidence of material overlap.** From the abstract and code, PNDC is a training-time fusion method evaluated by segmentation accuracy. It is not a full-text conclusion. |

**A8 status: OPEN — FULL TEXT UNVERIFIED.** The abstract and the authors' own evaluation code consistently indicate no case-level reliability analysis, so an **owner waiver is reasonable**. Alternatively, obtain the full text via institutional access.

## 4. Targeted falsification matrix

Columns:

- **A** missing MRI sequence at inference
- **B** case-level reliability / failure detection
- **C** fixed missing-sequence condition
- **D** ensemble/uncertainty signal
- **E** within-condition discrimination
- **F** AURC / risk-coverage
- **G** threshold transfer
- **H** held-out institution / external population
- **I** material overlap with our novelty claim
- **J** evidence level

| Work | A | B | C | D | E | F | G | H | I | J |
|---|---|---|---|---|---|---|---|---|---|---|
| LNCS 15354 (BraTS 2024) chapters | ? | ? | ? | ? | ? | ? | ? | ? | **Unknown** | UNVERIFIED (chapter list inaccessible) |
| BraTS 2024-era surrogates (M³FeCon, XLSTM-HVED, task-MoE, subtyping, Shapley) | yes (some) | no | per-config accuracy only | no (Shapley: different notion) | no | no | no | no | No | ABSTRACT ONLY |
| PNDC (TMI 2025) | yes | not described | per-mask evaluation (code) | no (training-time region reliability) | not described | not described | not described | not described | No evidence | ABSTRACT + CODE; full text UNVERIFIED |
| MMA-LTS (MICCAI 2026) | yes | **no** (voxel ECE only) | yes (per combination) | calibration conditioned on availability | no | no | no | no (internal BraTS 2020 / FeTS 2024) | Partial (voxel calibration under missingness) | FULL TEXT |
| Zenk et al. 2025 (MedIA) | no | **yes** | n/a | yes (ensemble, pairwise DSC) | n/a | **yes** (AURC) | no | shifts, but no missing sequences | Partial (method, complete input) | FULL TEXT |
| BraTS-GoAT reliability (2026) | no | **yes** | n/a | yes (3-seed ensemble) | n/a | **yes** | no | no (synthetic corruptions) | Partial (complete input) | FULL TEXT |
| Joham et al. (UNSURE 2026) | no | **yes** | n/a (sites, not conditions) | yes (distance scores; pairwise-Dice baseline) | **yes (within-site)** | **yes** (E-AURC) | no | multi-site | Partial (within-group evaluation concept) | FULL TEXT (keyword-searched) |
| SIUM (MICCAI 2026) | yes | no (config-level variance) | yes | variance embedding | no | no | no | no | No | FULL TEXT |
| SimMLM / MoFe (2025) | yes | no (ECE averaged over configs) | aggregated | no | no | no | no | no | No | FULL TEXT |
| QCResUNet (MedIA) | inputs to QC complete; segmentations from partial-input models | yes (QC regression) | no | learned QC | no | no | no | yes (BraTS-SSA, WUSM) | Partial | FULL TEXT (partial) |
| FOE (ECCV 2026) | no (not mentioned) | **yes** | n/a | concept-activation classifier | n/a | not stated | no | not stated | Partial (complete input) | ABSTRACT ONLY |

## 5. Novelty verdict

**Classification: 2. PARTIAL OVERLAP for the accessible literature, combined with 4. INSUFFICIENT EVIDENCE for the LNCS 15354 chapters and the PNDC full text.**

- **Established by prior work:**
  - case-level failure detection with ensembles/AURC on **complete inputs** (Zenk, BraTS-GoAT, FOE);
  - **within-group** (within-site) failure-detection evaluation as a concept (Joham);
  - **voxel-level** calibration conditioned on missing-modality identity (MMA-LTS);
  - accuracy under missing modalities (many papers).
- **Still distinct, on the accessible evidence:** the conjunction of criteria 1–4 (case-level ensemble-disagreement failure discrimination **within fixed missing-sequence conditions**) together with criterion 5 (transfer of a validation-derived operating threshold to a held-out institution and an external population). No accessible paper performs this combination.
- **Not established:** that no LNCS 15354 chapter, or the PNDC full text, performs it. A7 and A8 therefore remain open unless waived.

## 6. Static scan of the protocol (Step 8)

| Check | Result |
|---|---|
| Active TOST references | **None.** Only historical §25 rows (v0.2 row; v0.5 cleanup row), which are retained as history. |
| Active equivalence-test language | **None.** Every "equivalence" mention is a negation ("no equivalence is claimed / not evidence of equivalence") or the descriptive margin analysis. |
| Descriptive A-vs-B vs inferential testing | **Minor tension (not an A-vs-B reliability contradiction).** §13 "Supporting (descriptive)" reports a **Wilcoxon signed-rank test** over patient groups "descriptively". It concerns the B-vs-A **Dice** sanity comparison, not the H4 reliability comparison, and spends no α. Reporting a test statistic/p-value inside a declared descriptive analysis may still be read as inferential. **Owner decision:** keep it (as descriptive) or reduce it to a CI-only summary. Not changed here. |
| Reviewer placeholders | Present, as intended (§6.2 line 291; gate A6). |
| A7/A8 status statements | Consistent with this audit (A7: volume verified, chapter screen pending; A8: full text unverified). |
| Accidental "frozen" claim | **None for the protocol** (header: NOT FROZEN; freeze rule intact). Component-level "frozen in v0.4" wording is noted in §1 above. |
| Wording implying experiments or study-data evaluation | **None.** The provenance statement (line 13) correctly states that only public identifier/metadata files were retrieved and that no training, split or evaluation occurred. |

## 7. Recommended owner actions before v1.0

| Gate | Action | Protocol amendment needed? |
|---|---|---|
| **A6** | Provide the primary reviewer identity and the second reviewer identity (or "unavailable"), to be recorded in the experiment metadata, with a pointer in the v1.0 text. | Only to replace the placeholders at v1.0 (administrative; no design change) |
| **A7** | Either (a) supply the LNCS 15354 TOC/chapter DOIs or institutional access for a chapter-level screen, or (b) record an owner waiver with the §2.2 rationale and a mandatory pre-submission re-check. | No, unless the chapter screen finds overlap |
| **A8** | Either obtain the PNDC full text (institutional access) or record an owner waiver citing the abstract plus official-code evidence (§3). | No, unless the full text shows overlap |
| Optional | Decide on the §13 Wilcoxon (keep as descriptive, or CI-only). Optionally reword "frozen in v0.4" as "fixed in the pre-registration text; binding at v1.0". | Wording only, if chosen |
| **A9** | Owner approval of the v1.0 text after A6–A8 are closed or waived. | v1.0 creation |

**A design amendment does not appear necessary** on current evidence.

## 8. Sources checked

- Protocol and project documents: FINAL_RESEARCH_PROTOCOL.md v0.5; reports 12, 13, 15, 17; changelogs 16, 17, 18.
- Crossref REST API (book and chapter queries); OpenAlex (earlier round); arXiv API (recency queries, 2026-09-28).
- MICCAI 2024 open access: https://papers.miccai.org/miccai-2024/ (856 titles).
- Springer LNCS forthcoming list: https://media.springernature.com/original/springer-cms-alt/rest/v1/content/27852192/data/LNCS%20Forthcoming%20Proceedings%20PDF
- PNDC:
  - https://doi.org/10.1109/TMI.2025.3526818
  - https://pubmed.ncbi.nlm.nih.gov/40031068/
  - Semantic Scholar API
  - Unpaywall API
  - https://github.com/yansheng-qiu/PNDC
- FOE: https://arxiv.org/abs/2609.08879 ; CRS-Triage: https://arxiv.org/abs/2608.03862
- Previously full-text-read comparators: MMA-LTS (https://papers.miccai.org/miccai-2026/0659-Paper1236.html), Zenk 2025 (https://arxiv.org/abs/2406.03323), BraTS-GoAT reliability (https://arxiv.org/abs/2608.13223), Joham 2026 (https://papers.miccai.org/miccai-2026-sat/UNSURE2026_036.html).

## 9. Unresolved limitations of this audit

- The LNCS 15354 chapter list was not accessible.
- The PNDC full text was not accessible.
- The surrogate screens are keyword/title-based with abstract checks and can miss papers with atypical titles.
- The FOE, BUFNet and DFuse-Net full texts were not read; BUFNet and DFuse-Net remain on the pre-submission re-check list.

---

- No study imaging or label-volume data were downloaded.
- No split was created.
- No training was run.
- No inference or evaluation was performed.
- EXP-001 was not run.
- FINAL_RESEARCH_PROTOCOL.md was not modified. It remains **v0.5, NOT FROZEN**. No v1.0 and no git tag.
