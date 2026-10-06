# Gate B8: amendment v1.0-A3 acceptance failure (2026-10-06)

**Status: B8 STOPPED (REVIEW_REQUIRED). Gate B8 is not passed. No patient groups, split, training or results exist.**

As amendment v1.0-A3 prescribes, nothing has been adjusted, re-run or tuned.

## Run

| Field | Value |
|---|---|
| Session | Kaggle `brats-99-master-pipeline`, Version 5 (script version 355728828) |
| Hardware | CPU only (no accelerator) |
| Data | official TCIA data, re-acquired and verified against the committed B2 inventory |
| Code commit | `0f3672c04bc3c1ea152721c4929ef6c7c84a0241`; the A3 files are unchanged since `6d55ee4` |
| Configuration | `configs/grouping/b8_automated_v1.0-A3.yaml`, SHA-256 `33c2410809b21ddde8a4a074dd886a61378624836a0d5c28356f33c1fea28428` (matches the amendment) |
| Evidence | `docs/data/records/B8_automated_audit.json` and `docs/data/records/B8_automated_decisions.csv`, committed by the runner in `98bc9da` |

The inputs were the protocol's permitted pre-split inputs only:
- the four MRI sequences;
- the WT labels, used for lesion exclusion;
- the crosswalk;
- UCSF-PDGM Sex and IDH;
- the B7 flagged pairs.

No model prediction, segmentation performance, split, validation, test or calibration result was used. None exists yet.

## Result, from the audit record

| Quantity | Value |
|---|---|
| Development cases | 740 |
| Flagged pairs | 49,468 |
| Negative reference | 19,997 metadata-certified different-patient pairs scored (rules R3/R4, sampling seed 20261006) |
| tau_neg (0.999 quantile, method "higher") | 0.5424 |
| Control A (BraTS2021_00626 + 00758) | S = 0.7743, coverage 0.946 |
| Control B (BraTS2021_00639 + 00557) | S = **0.2419**, coverage 0.734 |
| tau_ctrl = min(S_A, S_B) | 0.2419 |
| SAME_PATIENT | 15,930 |
| DIFFERENT_PATIENT | 33,482 |
| UNRESOLVED | 56 |
| Rule counts | R1 2 · R3 7,217 · R5 56 · R6 15,928 · R8 26,265 (R2 and R4 decided no flagged pair) |
| Patient groups | 24: one group of **717** cases and 23 single-case groups |

**Acceptance criteria:**

| Criterion | Result |
|---|---|
| controls_above_tau_neg | **FAIL**: S_B = 0.2419 ≤ tau_neg = 0.5424 |
| controls_min_coverage | pass |
| max_group_size ≤ 8 | **FAIL**: largest group 717 |
| no_site1_in_development | pass |
| verified_groups_intact | pass |
| every_flagged_pair_decided | pass |

## Interpretation (factual)

The verified same-patient pair B is less similar in non-tumour anatomy (S = 0.2419) than 99.9% of the metadata-certified different-patient pairs. The pre-specified anatomy feature therefore **cannot recognise a known same-patient pair** in this cohort.

Because tau_ctrl < tau_neg, rule R6 (S ≥ tau_ctrl → SAME PATIENT) applied to 15,928 pairs, and transitive linking produced one 717-case group. The pre-specified acceptance criteria exist to catch exactly this. They did, and the procedure stopped.

The automated procedure of v1.0-A3 does not produce a defensible patient grouping for this cohort. By the amendment, B8 cannot pass under v1.0-A3 as written, and any further change requires a new logged amendment and an owner decision.

## Consequence

The frozen §6.3 split cannot be created, so no training, evaluation or scientific result can be produced. B9–B12, EXP-001 and everything downstream are blocked.

Owner options, none taken here:
- the frozen manual review (§6.2);
- a new logged amendment, specified without reference to these results beyond this disclosure;
- stopping the study at B8.
