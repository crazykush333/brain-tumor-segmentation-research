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

1. **v1.0-A3 failed.** Image similarity could not identify patients: verified same-patient pair B scored below the 0.999 quantile of metadata-certified different-patient pairs, and 717 of 740 cases fell into one group. A3 is withdrawn. See the administrative entry `2026-10-06_B8_A3-withdrawn-A4-dry-run.md`.
2. **v1.0-A4 failed** and was never adopted. Metadata identity coverage is incomplete (243 of 740 development cases have none), and conservative linking of their unresolved relationships created giant groups. The largest had 374 cases, and the linking joined patients that metadata prove are different.
3. This amendment is made **before** any split, training, validation or test evaluation.
4. **No model result** of any kind exists or informed it.
5. Identity uses **only** authoritative provider metadata:
   - the crosswalk (B3);
   - the UCSF-PDGM v5 metadata (B4);
   - the official TCIA UCSF-PDGM follow-up rename notice.

   It does not use image similarity, WT Dice values or thresholds, model predictions, validation or test outcomes, AURC, or any post-split information.
6. The **primary development cohort** is the set of B6 development cases (site ≠ 1) with an authoritative identity. Its size is derived from the data and is not a parameter.
7. Cases without authoritative identity form the **IDENTITY-UNCERTAIN QUARANTINE COHORT**. They are never grouped. They are never used in training, validation, threshold or τ_q/I derivation, calibration, model selection, the internal test, or any primary or secondary inference.
8. **Patient groups** are the connected components of identical authoritative identity keys and the protocol's verified groups A and B. Two cases with different identity keys are never grouped, except through a verified group. Groups are frozen once at B9 and never reopened.
9. **The estimand is unchanged** apart from its population. Unchanged:
   - the endpoint (mean C4 within-condition ET ΔAURC, Arm B), hypotheses, metrics and conditions;
   - the uncertainty scores, the missingness indicator, the models (Arm A/B × seeds 0–2, 250 epochs) and the statistical tests;
   - the bootstrap (10,000, seed 12345) and the Holm family;
   - the external cohorts (UPenn site 1; BraTS-Africa).

   **The population changes:** the development and internal-test population is the identity-clean cohort, not all 740 site ≠ 1 cases. The split ratio (70/10/20, grouped) and its seed (20260927) are unchanged. The split is created once, on the primary cohort only.
10. **Limitation (mandatory in every presentation of results):** the primary cohort is reduced and selected by the availability of identity metadata. It is not a random subsample. Its site and collection composition differs from the 740-case pool (below), so internal-test results may not generalise to the excluded contributors. Internal-test precision is lower than planned.
11. An optional evaluation of the quarantine cohort may be reported. It must be **descriptive only**, at case level, and labelled "IDENTITY-UNCERTAIN QUARANTINE COHORT". It enters no hypothesis test, threshold or primary result.
12. v1.0-A3 and the proposed v1.0-A4 are recorded as **failed and withdrawn / not adopted**. Their evidence is retained unchanged as an audit trail:
    - `docs/data/records/B8_automated_*`;
    - `docs/data/records/B8_A4_dryrun/`;
    - `docs/research/execution/B8_A3_ACCEPTANCE_FAILURE_2026-10-06.md`.

## Final metadata identity-recovery sweep (pre-split)

The 243 development cases without identity were checked against every permitted authoritative source:
- the crosswalk (all columns);
- the UCSF-PDGM v5 metadata (every column, including `BraTS21 ID`);
- the TCIA UCSF-PDGM rename notice.

All 243 have TCIA patient ID `new-not-previously-in-TCIA` and no study date. No UCSF v5 row references any of them. **0 of 243 were resolved.**

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
