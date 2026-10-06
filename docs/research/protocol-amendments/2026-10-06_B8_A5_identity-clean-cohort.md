# Protocol v1.0 amendment A5: identity-clean primary development cohort at gate B8

Amendment ID: v1.0-A5
Amendment type: METHOD / POPULATION
Date: 2026-10-06
Owner: Ayush Kushwaha
Protocol: v1.0 (frozen 2026-09-28, tag `protocol-v1.0`, SHA-256 `704c0b495917344f44b93e7548ade0e32a71220265419516a2c83d626fcd9811`). The frozen file and its tag are unchanged.
Sections: §6.2 (same-patient screen, review and grouping), §6.3 (split population), checklist gates B8–B12
Test-set data seen before amendment: No (no split exists; no model has been trained)

Specification: `configs/grouping/b8_identity_clean_v1.0-A5.yaml`. Production code: `brats_uncertainty.grouping.identity_clean`. Independent verifier: `brats_uncertainty.verification.identity_audit`, which does not import the production grouping code.

## Statements

1. **v1.0-A3 failed** because image similarity could not reliably identify patient identity. Verified same-patient pair B scored below the 0.999 quantile of metadata-certified different-patient pairs, and 717 of 740 cases fell into one group. See `docs/research/execution/B8_A3_ACCEPTANCE_FAILURE_2026-10-06.md`.
2. **v1.0-A4 failed** because authoritative metadata do not cover all development cases (243 of 740 have none), and conservative handling of the unresolved relationships created invalid giant groups. The largest had 374 cases and joined patients that metadata prove are different. A4 was never adopted. See `2026-10-06_B8_A3-withdrawn-A4-dry-run.md`.
3. **The original 740-case split therefore cannot be constructed without unacceptable leakage risk:**
   - assigning the 243 cases to singleton groups would treat the absence of identity as proof of uniqueness;
   - linking them conservatively makes the §6.3 split impossible.
4. **Exhaustive manual adjudication of the 49,468 flagged candidate pairs is operationally infeasible** (about 140–275 expert hours; owner decision).
5. **The study therefore adopts an identity-clean primary development cohort.** It is the set of B6 development cases (site ≠ 1) with an authoritative provider identity, from three sources:
   - the TCIA patient ID in its namespace, with TCGA-GBM and TCGA-LGG sharing the TCGA barcode namespace;
   - the UCSF-PDGM v5 base patient number;
   - the official UCSF-PDGM follow-up rename list.

   Patient groups are the connected components of identical identity keys and the verified groups A and B. The size of the cohort is derived from the evidence, not set as a parameter.
6. **Unresolved cases are quarantined rather than falsely assigned to patient groups.** They form the IDENTITY-UNCERTAIN QUARANTINE COHORT. They are never forced into singleton groups, never linked by image similarity or proximity, and never placed in the train/validation/internal-test split.
7. This amendment was made **before** any final split, training, test evaluation or scientific result.
8. **No model result** influenced this amendment; none exists. Identity uses only authoritative provider metadata. Image similarity, WT Dice values or thresholds, model predictions, AURC, validation or test outcomes and post-split information are not used.
9. **The primary estimand is the same conceptual quantity:** the within-missingness-condition ET ΔAURC of the Arm-B ensemble, U1 versus the indicator I, averaged over the C4 conditions. The following are unchanged:
   - the research question, primary hypothesis, primary endpoint and secondary metrics;
   - the model architecture, modality-dropout design and training configuration (Arm A/B × seeds 0–2, 250 epochs);
   - the validation logic;
   - the external evaluation (UPenn site 1; BraTS-Africa);
   - the bootstrap (10,000 replicates, seed 12345) and the statistical framework, including the Holm family;
   - the split rule (70/10/20 at patient-group level, frozen stratification, seed 20260927, created once).
10. **The population to which the primary inference applies is now explicitly the identity-clean development cohort**, not all 740 site ≠ 1 cases.
11. **The reduced-development-cohort limitation and possible selection bias must be reported** in the final manuscript and on every results page. The cohort is selected by the availability of identity metadata, not at random. Its site and collection composition differs from the 740-case pool (below). Internal-test precision is lower than planned.
12. **The quarantine cohort remains outside all training, validation and primary-test decision-making.** That covers training, checkpoint selection, validation, threshold, τ_q or I derivation, calibration and primary analysis. After every primary quantity is frozen, it may be evaluated as a secondary descriptive robustness analysis under three conditions:
    - it is labelled "IDENTITY-UNCERTAIN QUARANTINE COHORT";
    - it reports case-level descriptive metrics only, with no patient-group bootstrap inference;
    - it makes no claim of patient-level independence.

**Audit trail.** v1.0-A3 and the proposed v1.0-A4 are recorded as failed and withdrawn / not adopted methodological attempts. Their evidence is retained unchanged:
- `docs/data/records/B8_automated_*`;
- `docs/data/records/B8_A4_dryrun/`.

After A5 and the split are verified, **patient grouping is frozen**. It is not reopened because of model results. No post-hoc identity rule, threshold change, image-similarity rescue or manual inspection is allowed, unless an external data-provider correction appears.

## Final metadata identity-recovery sweep (pre-split)

The record is `docs/data/records/B8_A5_identity_sweep.json`. It is reproducible with `brats-uncertainty a5-identity-sweep`; the inputs are verified against the B3/B4 hashes and the development set against the B6 hash.

The 243 development cases without identity were checked against every official TCIA identity resource for these data. These are the only metadata files; no imaging was downloaded for this sweep.

| Source | SHA-256 | Finding |
|---|---|---|
| `BraTS2021_MappingToTCIA.xlsx` (B3) | `223243c5…a2dc0b` | all 243: TCIA patient ID `new-not-previously-in-TCIA`, no study date |
| `UCSF-PDGM-metadata_v5.csv` (B4; current version, 2025/05/30) | `afc1c23a…16fd78` | no row references any of the 243 (any column) |
| TCIA UCSF-PDGM follow-up rename notice | page of 2025/05/30 | six renamed follow-ups, all of TCIA UCSF-PDGM patients; none of the 243 |
| `NotPreviouslyInTCIA.csv` (TCIA BraTS 2021 page) | `363d410c…4f9010` | lists all 243 as "new (NIfTI) series with no TCIA DICOM equivalent"; gives no patient, study or series identifier |
| `GC_manifest_RSNA-ASNR-MICCAI-BRATS-2021_sources.csv` (TCIA BraTS 2021 page) | `50e54e3a…c50aa2` | maps file IDs to TCIA series UIDs only; references no BraTS case, so it cannot link cases without TCIA series |

The affected contributions ("Collection 1, 3, 4, 5, 7, 9" and UCSF-PDGM_Additional) have no TCIA source collection, so no further official source-collection metadata exist.

**Result: 0 of 243 gain an authoritative identity.** All 243 remain unresolved; the SHA-256 of their ID list is in the sweep record. The mapping is independently reproducible from the hashed public files.

## Disclosure: pre-split composition (local dry run with the B3/B4-verified files)

The authoritative counts are those written at execution by the pipeline (`docs/data/records/B8_A5/summary.json`); the dry run is shown here so the selection effect is visible before the split.

| Quantity | Value |
|---|---|
| Development pool (B6) | 740 |
| Primary (identity-clean) | 497: UCSF-PDGM 263, TCGA-GBM 102, TCGA-LGG 65, CPTAC-GBM 33, IvyGAP 30, ACRIN-FMISO-Brain 4 |
| Quarantine | 243: UCSF-PDGM_Additional 119, Collection 5 47, Collection1 35, Collection 4 30, Collection3 7, Collection 7 4, Collection 9 1 |
| Patient groups (primary) | 495: 493 singletons and 2 groups of size 2 (verified groups A and B, also the only follow-up links within development) |
| Identity coverage by site | sites 5–16, 19 and 20: 100%; site 18 (UCSF): 263/382 (68.9%) |
| Sites absent from the primary cohort | 2, 3, 4, 17, 21, 22, 23, 24 (all cases of the non-TCIA "Collection" contributions) |
| Acceptance (identity provenance) | all pass; independent reconstruction identical |

**Disproportionately excluded:**
- every case of the non-TCIA "Collection" contributions (124 cases, 8 sites);
- 31% of UCSF.

No sample-size threshold is applied. A reduced cohort is accepted, and disclosed, rather than an unverifiable grouping.

## Residual identity risks (disclosed)

- **Quarantine versus primary.** The 119 UCSF-PDGM_Additional cases may include follow-ups of UCSF-PDGM primary patients. This cannot be checked from permitted inputs. The quarantine is excluded from all training, validation and primary inference, so this does not leak into the primary analysis. It does mean that a descriptive quarantine evaluation may include patients whose other scans were in training; this is why that evaluation is labelled identity-uncertain.
- **Across collections.** A patient contributed to two different TCIA collections under different identifiers cannot be detected from metadata. TCGA-GBM and TCGA-LGG share one barcode namespace and are compared within it.

## Acceptance (objective, identity provenance only)

- Verified groups A and B intact.
- Official follow-up links intact.
- Different identities never grouped (except through a verified group).
- No site-1 case in development.
- Primary + quarantine = the B6 development set exactly.
- An independent re-implementation gives identical cohorts and groups. Its result is written to `results/verification/A5_IDENTITY_VERIFICATION.{json,md}`, which must read `A5_IDENTITY_VERIFICATION = VERIFIED`.

Any failure stops at B8, and nothing is adjusted. After B10–B12, `brats-uncertainty audit-split` independently re-derives the groups from the committed cohort file and checks the split.
