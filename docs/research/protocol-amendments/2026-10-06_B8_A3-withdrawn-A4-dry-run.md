# Administrative entry: B8 amendment v1.0-A3 withdrawn; proposed v1.0-A4 failed its pre-split dry run

Date: 2026-10-06
Owner: Ayush Kushwaha
Protocol: v1.0 (tag `protocol-v1.0`, SHA-256 `704c0b495917344f44b93e7548ade0e32a71220265419516a2c83d626fcd9811`), unchanged
Gate: B8 (§6.2). **No split exists, no model has been trained, and no scientific result exists.**
Test-set data seen: No

This entry records two events and changes no design:
- the withdrawal of a failed procedure;
- the failure of a proposed replacement before adoption.

## 1. v1.0-A3 failed and is withdrawn

v1.0-A3 (automated anatomy-similarity adjudication) was executed on the official data on 2026-10-06. This was before any split or training.

It failed its pre-specified acceptance checks (`docs/research/execution/B8_A3_ACCEPTANCE_FAILURE_2026-10-06.md`):
- Verified same-patient pair B had non-tumour anatomy similarity 0.2419. That is below the 0.999 quantile (0.5424) of metadata-certified different-patient pairs.
- 15,904 of the 15,928 rule-R6 links fell below that quantile.
- 717 of the 740 development cases fell into one group.

**This shows that A3's image-similarity rule is not a valid patient-linkage mechanism for this cohort.**

**Consequences:**
- A3 is withdrawn.
- Its grouping and its thresholds are not used for anything.
- A3's decision mechanism did not inform the replacement below.

The A3 evidence (`docs/data/records/B8_automated_*`) is kept as an audit trail.

## 2. Proposed replacement v1.0-A4: metadata linkage only

**Pre-specification.** The rule was committed **before** its dry run:
- config `configs/grouping/b8_metadata_linkage_v1.0-A4.yaml`, SHA-256 `8e3334f289ec0123aee45be46ff339e27b82e8b3ca218daea70d63c8611c450d`;
- commit `9968aa9`.

**Basis.** The rule uses only authoritative identity evidence, which is the mechanism by which the protocol verified groups A and B (TCIA UCSF-PDGM follow-up records). Image similarity and Dice values are not identity evidence.

**Rules:**

| Rule | Condition | Decision |
|---|---|---|
| M1 | verified groups | SAME |
| M2 | same UCSF-PDGM base patient number (follow-up records `_FU<k>d`) | SAME |
| M3 | same real TCIA ID within a collection | SAME |
| M4 | different UCSF patients | DIFFERENT |
| M5 | different real TCIA IDs in one collection | DIFFERENT |
| M6 | UCSF Sex or IDH discordance | DIFFERENT |
| M7 | different contributing site (stated assumption) | DIFFERENT |
| M8 | otherwise | UNRESOLVED |

- M1–M3 apply to all development pairs.
- M4–M8 apply to the remaining B7 flagged pairs.
- UNRESOLVED is linked (conservative, §6.2).
- The acceptance limits are those of A3 (largest group ≤ 8; A/B intact; no site 1; all pairs decided), plus "no metadata-certified different pair ends in one group".

**Disclosure.** The proposal was made after the A3 failure and after aggregate counts of the flagged pairs by site and collection had been seen. It was not tuned on its own dry run. It sets no threshold.

### Pre-split dry run (evidence: `docs/data/records/B8_A4_dryrun/`)

The dry run is reproducible with `brats-uncertainty b8-a4-dryrun --crosswalk … --ucsf-metadata …`. The inputs are verified against the B3/B4 hashes, and the development set against the B6 hash.

| Quantity | Value |
|---|---|
| Development cases with authoritative identity / without | 497 / **243** (UCSF-PDGM_Additional 119; Collection 1, 3, 4, 5, 7, 9: 124) |
| Metadata SAME links | 2 (groups A and B only; no further follow-up record links two development cases) |
| SAME / DIFFERENT / UNRESOLVED (flagged pairs plus metadata links) | 2 / 42,738 / 6,728 |
| Rules | M1 2 · M4 5,444 · M5 1,773 · M7 35,521 · M8 6,728 |
| Unresolved pairs | 6,728 among 482 cases; 6,314 at site 18 (UCSF) |
| Groups | 269: largest **374** (all UCSF: 257 UCSF-PDGM + 117 UCSF-PDGM_Additional); also 46, 35, 10, 4, 3 and 5 × 2; 258 singletons |
| Median / 95th-percentile group size | 1 / 1 |
| Independent re-implementation | decisions identical (0 differences); groups identical (269 = 269) |

**Acceptance:**
- max_group_size: **FAIL** (374);
- **metadata_different_never_linked: FAIL**;
- verified_groups_intact, no_site1_in_development and every_flagged_pair_decided: pass.

### Conclusion: A4 is not adopted

243 development cases carry no authoritative identity information, and image similarity cannot recognise known same-patient pairs. Conservative linking of their flagged relationships therefore chains together patients that TCIA/UCSF metadata **prove** are different, producing a 374-case group.

The **leakage-sensitivity finding** is this. Identity uncertainty is concentrated at site 18 (UCSF): 6,314 unresolved relationships involve the 119 UCSF-PDGM_Additional cases, which TCIA lists as "new-not-previously-in-TCIA", with no link to UCSF-PDGM patient records. Without identity data, it cannot be determined from permitted inputs whether some of these are follow-ups of UCSF-PDGM patients.

**Automated, leakage-safe patient grouping cannot be made scientifically defensible with the permitted data.** As the owner's instruction requires, no third rule is introduced. Gate B8 remains not passed; no split is created; nothing downstream runs.

The remaining paths require an owner decision:
- a human identity review limited to the cases without authoritative identity;
- an identity source from the data provider;
- or stopping the study at B8.
