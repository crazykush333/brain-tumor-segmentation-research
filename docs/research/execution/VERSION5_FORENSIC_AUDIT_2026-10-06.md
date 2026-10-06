# Post-run forensic audit: Kaggle Version 5 (2026-10-06)

## Run identity

| Field | Value | Source |
|---|---|---|
| Notebook / version | `brats-99-master-pipeline` Version 5, scriptVersionId 355728828 | Kaggle log page |
| Execution status | "Successfully ran in 2559.6s". The notebook exited cleanly after the runner stopped at B8; this does not mean any gate passed | Kaggle log page |
| Accelerator | **None** (CPU only) | Kaggle log page |
| Repository commit run | `0f3672c04bc3c1ea152721c4929ef6c7c84a0241` | Kaggle log; `B8_automated_audit.json` `code_commit` |
| Amendment | v1.0-A3, `6d55ee4`. The A3 config, code and amendment are unchanged between `6d55ee4` and `0f3672c` | git |
| A3 configuration | SHA-256 `33c2410809b21ddde8a4a074dd886a61378624836a0d5c28356f33c1fea28428` (equals the amendment) | `B8_automated_audit.json` |
| Runner step table (end of session) | ENV, D1, D2, B2, DATA, B3–B7 PASSED; **B8 REVIEW_REQUIRED**; B9–B12 LOCKED; PILOT BLOCKED (no GPU); C1 BLOCKED | Kaggle log |
| Evidence pushed by the runner | `98bc9da` (B8 audit and decisions, run summary, final audit) | git |

## Gate audit (from `docs/project_status.yaml` and the committed records)

| Gate | Status | Evidence path | Commit | SHA-256 (first 16 hex) | Notes |
|---|---|---|---|---|---|
| B6 | PASSED | `docs/data/records/B6.json` | `eb3166b` | `39a6e20133b6e89e` | 1,251 / 511 / 740 from the hashed crosswalk |
| B7 | PASSED | `docs/data/records/B7/t_screen.json` | `e30e0cd` | `d811ffd6c75d867b` | T_screen 0.2174; 49,468 flagged pairs |
| B8 | **RUNNING (not passed)** | none recorded as gate evidence; run output: `docs/data/records/B8_automated_audit.json`, `B8_automated_decisions.csv` | `98bc9da` | — | A3 acceptance failed (below) |
| B9 | LOCKED | — | — | — | not reached |
| B10 | LOCKED | — | — | — | no split exists |
| B11 | LOCKED | — | — | — | — |
| B12 | LOCKED | — | — | — | — |

The independent split audit (`brats-uncertainty audit-split`) is **not applicable**: there are no B9 patient groups and no B10–B12 split files to audit.

## B8 forensic review

This section is an independent recomputation from the committed ID-level files. It uses its own union-find and does not use the production grouping code.

| Quantity | Recomputed | Production audit |
|---|---|---|
| Flagged pairs; decisions cover exactly the flagged set | 49,468; yes | 49,468 |
| SAME / DIFFERENT / UNRESOLVED | 15,930 / 33,482 / 56 | identical |
| Rules R1 / R3 / R5 / R6 / R8 (R2 and R4 none) | 2 / 7,217 / 56 / 15,928 / 26,265 | identical |
| Groups, including 3 unflagged singletons | 24 | 24 |
| Largest group / size counts | **717** / {717: 1, 1: 23} | identical |
| Group A, group B | each intact; **both inside the 717-case group** | intact |

**Thresholds** (production audit):
- tau_neg = 0.5424, the 0.999 quantile over 19,997 metadata-certified different-patient pairs;
- control A S = 0.7743;
- control B S = **0.2419**;
- tau_ctrl = 0.2419.

**Mechanism.** Control B is less anatomically similar than 99.9% of certified different-patient pairs. So tau_ctrl < tau_neg, and rule R6 (S ≥ tau_ctrl → SAME) linked 15,928 pairs. **15,904 of these have S ≤ tau_neg**: they are not distinguishable from certified different-patient pairs, and were linked only because of control B's low similarity. Transitive linking then produced one 717-case group.

**Acceptance criteria:**
- controls_above_tau_neg **FAIL**;
- max_group_size ≤ 8 **FAIL** (717);
- controls_min_coverage, no_site1_in_development, verified_groups_intact and every_flagged_pair_decided: pass.

**Inputs** (audit record):
- the four MRI sequences;
- the WT labels (lesion exclusion);
- the crosswalk (collection, site, real TCIA ID);
- UCSF-PDGM Sex and IDH;
- the B7 flagged pairs.

**Not used:** model predictions, segmentation performance, split, validation, test or calibration results, and any post-split information. None of these exists: no model has been trained and no split exists.

## Conclusion

The amendment v1.0-A3 procedure ran exactly as frozen. It produced a **pathological grouping** (one group holding 717 of 740 development cases), and its pre-specified acceptance criteria stopped B8. **The study is stopped at B8.**

No replacement rule was invented. B9–B12, the split audit, EXP-001, training and all evaluation remain blocked. Continuing requires an owner decision:
- the frozen §6.2 manual review;
- a new logged amendment;
- or stopping the study.

The failure details are in `docs/research/execution/B8_A3_ACCEPTANCE_FAILURE_2026-10-06.md`.
