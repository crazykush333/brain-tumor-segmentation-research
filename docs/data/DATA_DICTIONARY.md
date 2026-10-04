# Data dictionary

Definitions of the identifiers, fields and files the code produces or consumes. The values shown are **formats**, not data.

## Identifiers

| Field | Format | Source |
|---|---|---|
| `case_id` (BraTS 2021) | `BraTS2021_NNNNN` | BraTS 2021 release / crosswalk |
| `case_id` (BraTS-Africa) | expected `BraTS-SSA-NNNNN-NNN` (to be verified at C1–C2) | TCIA release |
| `group_id` | `DEV-NNNN` (development), `HOI-NNNN` (held-out institution); numbered by smallest member case ID | `grouping/groups.py` |
| `condition` | `Full`, `-T1`, `-T1c`, `-T2`, `-FLAIR`; C15 subsets as `T1+T2` etc. | `preprocessing/modalities.py` |
| `region` | `WT`, `TC`, `ET` | protocol §8 |
| `partition` | `train`, `validation`, `internal_test` | `splitting/split.py` |

## Channels and labels

| Item | Definition |
|---|---|
| Channel order | `[T1, T1c, T2, FLAIR]` (§8) |
| Missing sequence | the **normalized** channel is set to 0 (§10) |
| BraTS 2021 labels | 1 = NCR, 2 = ED, 4 = ET. Regions: ET = {4}, TC = {1, 4}, WT = {1, 2, 4} |
| BraTS-Africa labels (expected; verify at C1) | 1 = NETC, 2 = SNFH, 3 = ET. Regions: ET = {3}, TC = {1, 3}, WT = {1, 2, 3} |
| nnU-Net internal labels | BraTS 2021 {0, 2, 1, 4} → {0, 1, 2, 3}; regions WT = (1, 2, 3), TC = (2, 3), ET = (3) |

## Per-unit metric CSV (protocol §24)

One row per case × condition × region:

| Column | Type | Meaning |
|---|---|---|
| `case_id` | str | case identifier |
| `group_id` | str | patient group (bootstrap unit) |
| `condition` | str | missing-sequence condition |
| `region` | str | WT / TC / ET |
| `dice` | float | ensemble Dice (both empty → 1; one empty → 0) |
| `risk` | float | 1 − Dice |
| `U1` | float | mean pairwise member Dice (primary confidence) |
| `U2` | float | negative mean binary entropy (bits) in the ROI |
| `U3` | float | seed-0 mean max-probability in the ROI (exploratory) |
| `I` | float | −(validation mean risk of the condition) |
| `vol_gt_ml`, `vol_pred_ml` | float | ET volumes (mL) |
| `ece`, `brier` | float | voxel calibration in the ROI (NaN if the ROI is empty) |

## Committed ID files (future; created only at their gates)

| File | Gate | Columns |
|---|---|---|
| `splits/split_all.csv` | B10 | `case_id, group_id, partition` |
| `patient_groups_dev.csv` | B9 | `case_id, group_id` |
| `flagged_pairs.csv` | B7 | `case_a, case_b` |
| `reviews.csv` | B8 | `case_a, case_b, decision, reviewer, round, timestamp, reason` |
