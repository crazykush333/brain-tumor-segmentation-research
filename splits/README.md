# splits/

**No split exists yet.** The real patient-group split has not been created and no
train / validation / test IDs are published.

- **Controlled by the frozen protocol (§6.3):** the 70 / 10 / 20 patient-group split of
  the 740 development cases (crosswalk Site ID ≠ 1), stratified at group level by ET
  presence and the tertile of mean WT volume, split seed `20260927`, created **exactly
  once** at gate B10 — after the same-patient screen (B7), the human review (B8) and the
  frozen patient groups (B9).
- **Assertions (B11):** no site-1 case in development; development count before grouping
  = 740; no patient group spans partitions (including the verified groups A and B).
- **IDs only:** the files written here will contain case IDs, patient-group IDs and
  partition names — never images or labels.
- **Hashes and provenance (B12)** are recorded only when the real split has been executed
  (`split_hashes.json`), together with the frozen patient groups (`patient_groups_dev.csv`)
  and, at gate C4, the HOI bootstrap groups (`patient_groups_hoi.csv`).

The gated pipeline refuses to create or overwrite a split before its gates are closed.
