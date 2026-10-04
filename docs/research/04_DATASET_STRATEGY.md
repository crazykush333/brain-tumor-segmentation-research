# 04 — Dataset Strategy

**No data has been downloaded.** No medical data will ever be committed to this repository.

Legend:

- ✔ = verified on 2026-09-27 against the source page cited in [09](09_LITERATURE_MATRIX.md)
- ? = to verify before use

Licences and access terms change. **The dataset's own terms page at download time is authoritative, not this table.**

## 1. Candidate datasets

| Dataset | Cases (labelled, public) | Sequences | Labels | Sites / shift | Access | Licence / terms | Role candidates |
|---|---|---|---|---|---|---|---|
| **BraTS 2018** | 285 train ? | T1, T1c, T2, FLAIR | NCR/NET, ED, ET | Multi-site (subset of later releases) | Via CBICA / historical; availability ? | BraTS terms ? | **Legacy comparison only.** Most missing-modality papers use it [C-common]. It is a subset of BraTS 2021, so combining the two leaks data. |
| **BraTS 2020** | 369 train ? | same | same | same | same ? | ? | Legacy comparison only; subset of 2021. |
| **BraTS 2021 (RSNA-ASNR-MICCAI)** | 1,251 train (labels public); validation/test labels hidden ✔ ([A1], [C6]) | same | same | Multi-institutional; **site IDs not generally released** ? | Synapse registration; TCIA with **Restricted License Agreement** ✔ | CC BY contributions per TCIA ✔; must cite [A1, A2, A3] | **Source domain** (train / val / internal test). |
| **BraTS 2023 GLI** | Believed to equal the 2021 training set ? | same | same | same | Synapse | ? | **Not an external set**: assumed overlap with 2021 (flagged in [C10]). |
| **BraTS-Africa (SSA)** | 146 patients total ✔; labelled/public split ? | same | same | Nigeria; lower-field, heterogeneous protocols [A5] | TCIA / Synapse ✔ | **CC BY 4.0** ✔ | **External test (acquisition + population shift).** |
| **UPenn-GBM** | 630 patients ✔; manual vs automated label split ? | structural + DSC/DTI ✔ | BraTS-style sub-regions | Single institution | TCIA ✔ | **CC BY 4.0** ✔ | **External test after de-duplication** against BraTS 2021 and restriction to manually revised labels. Precedent: [C7]. |
| **UCSF-PDGM** | 501 ✔ | structural + advanced ✔ | BraTS-style | Single institution, 3T | TCIA ✔ | ? (TCIA page) | **External test after de-duplication**; TCIA provides a BraTS ID mapping ✔. Overlap may be large (one report: 298) ?. |
| **EGD (Erasmus)** | 774; 374 manual WT ✔ | T1, T1c, T2, FLAIR ✔ | **Whole tumour only** ✔ | Single center, multi-scanner | DUA via Health-RI ✔ | DUA (no redistribution) | Optional WT-only external test. |
| **RHUH-GBM** | 40 ✔ | structural (+DWI ?) | Sub-regions, expert-corrected ✔ | Single center, pre + post-op | ? | ? | Small external test, including post-op. |
| **LUMIERE** | 91 patients, 638 timepoints ✔ | structural ✔ | **Automated only** ✔ | Single center | ? | ? | Not suitable as ground truth. |
| **BraTS 2024 post-treatment GLI** | ? | structural | ET, SNFH, NETC, **RC** ✔ | Multi-site | Synapse ? | ? | Direction 4 only. |
| **MU-Glioma-Post** | ? (secondary source: ~2,200 cases, unverified) | structural | ? automated vs expert | Multi-site | TCIA ? | ? | Direction 4 only. |
| **BraTS-PEDs / MEN / METS** | see [A13, A14] | structural | differ | differ | Synapse | ? | Far-OOD inputs only; not glioma external validation. |

## 2. Recommended dataset roles *if* Direction 1, 2, 3 or 5 is chosen

This is a *design*, not a recommendation of a direction.

```
SOURCE DOMAIN      BraTS 2021 training set (1,251), after de-duplication checks
  ├─ TRAIN         ~70% of patients
  ├─ VALIDATION    ~10% (early stopping, calibration fitting, threshold selection)
  └─ INTERNAL TEST ~20% (touched once, at the end)
TARGET DOMAINS (EXTERNAL TEST; never used for training, tuning, calibration or thresholds)
  ├─ BraTS-Africa  (all publicly labelled cases)
  ├─ UPenn-GBM     (manually revised, not in BraTS 2021)
  └─ optional: UCSF-PDGM (not in BraTS 2021), EGD (WT only)
```

Split ratios are provisional. Final ratios and exact patient ID lists go into `FINAL_RESEARCH_PROTOCOL.md`, and the ID lists (IDs only, no images) are committed under `splits/`.

## 3. Leakage controls (mandatory)

1. **Patient-level splitting only.** One patient = one split. Each BraTS 2021 case is one patient per the organizers (to verify for any multi-timepoint cases).
2. **Cross-dataset de-duplication:**
   - UCSF-PDGM: use the TCIA BraTS-ID mapping.
   - UPenn-GBM: use the BraTS mapping (source to be identified; [C7] authors contacted dataset authors).
   - Any case appearing in BraTS 2021 is removed from external sets.
   - The de-duplication script and its output (IDs only) are versioned.
3. **Never combine BraTS 2018/2020 with 2021** as if they were separate sources.
4. **Preprocessing leakage:**
   - Intensity normalization is per-case (z-score within the brain mask). Dataset-level statistics come from TRAIN only.
   - nnU-Net's dataset fingerprint is computed on TRAIN only. This needs a custom split file and an audit of what nnU-Net's planning step reads.
5. **Augmentation leakage:** augmentation applies to TRAIN only. TTA at inference is a declared method, not augmentation leakage.
6. **Hyperparameter leakage:** all tuning, calibration fitting and threshold selection happen on VALIDATION. INTERNAL TEST and EXTERNAL sets are evaluated **once per pre-registered configuration**. Any re-run after seeing test results is logged as such.
7. **Preprocessing mismatch as shift:** BraTS data is already co-registered, skull-stripped and resampled to 1 mm (SRI-24 atlas). External datasets must be put through a documented equivalent pipeline, ideally the BraTS preprocessing toolkit (identify the current official tool, e.g. `BraTS-Toolkit` or `brainles-preprocessing`, and verify its licence). Differences in preprocessing are reported as part of the shift, not hidden.

## 4. Label harmonization

- BraTS 2021 labels are 1 = NCR, 2 = ED, 4 = ET (the label value 3 is unused in 2021; to verify on the actual files). They are evaluated as the regions ET = {4}, TC = {1, 4}, WT = {1, 2, 4}.
- Newer BraTS releases may use 1/2/3 with ET = 3. This must be verified per release and handled by an explicit, unit-tested mapping.
- EGD provides WT only, so only WT metrics are reported there.
- Post-treatment schema (ET, SNFH, NETC, RC) is Direction 4 only, with a documented mapping to pre-op regions.

## 5. Legal and ethical notes

- Data stays on Kaggle/Colab or local storage **outside** the Git working tree. `.gitignore` excludes common medical formats.
- Kaggle datasets: **do not rely on unofficial Kaggle mirrors** of BraTS unless their redistribution status is verified. Preferred approach: obtain from Synapse/TCIA under our own agreement, then upload to a **private** Kaggle dataset, if the terms allow private re-hosting (to verify). Otherwise download inside the notebook session.
- Figures showing patient images (overlays): allowed only if the dataset licence permits redistribution of derived images. CC BY 4.0 sets (UPenn, BraTS-Africa) permit it with attribution. For BraTS 2021 via the TCIA restricted licence, check whether axial slices may be published; faces are not visible in axial tumour slices, but this is to verify.
- Citation requirements: each dataset's "citation required" list is copied into `docs/reproducibility/dataset.md` at download time.

## 6. Open questions to resolve before the protocol

1. Verify the BraTS 2021 Synapse terms and the TCIA restricted licence wording.
2. Obtain the UPenn-GBM ↔ BraTS mapping and the count of manually revised labels.
3. Obtain the BraTS-Africa labelled case count.
4. Confirm the BraTS 2023 GLI vs 2021 overlap.
5. Confirm label conventions in each release by reading the files, at the dataset milestone.
