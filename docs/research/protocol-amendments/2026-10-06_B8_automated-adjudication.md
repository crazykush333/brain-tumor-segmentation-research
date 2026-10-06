# Protocol v1.0 amendment A3: automated, deterministic adjudication at gate B8

Amendment ID: v1.0-A3
Amendment type: METHOD / FEASIBILITY
Date: 2026-10-06
Owner: Ayush Kushwaha
Protocol: v1.0 (frozen 2026-09-28, tag `protocol-v1.0`, SHA-256 `704c0b495917344f44b93e7548ade0e32a71220265419516a2c83d626fcd9811`). The frozen file and its tag are unchanged.
Sections: §6.2 step 4 (manual review) and step 5 (grouping input); checklist gate B8
Test-set data seen before amendment: No (no split exists; no model has been trained)

## Disclosure

**This amendment was made after the frozen screen was run.** At gate B7 (2026-10-06), the frozen T_screen rule gave T_screen = 0.2174. That value is the WT-label Dice of verified control B (BraTS2021_00639 + BraTS2021_00557); control A gave 0.8650. With this threshold the screen flagged **49,468 of 273,430** development pairs.

The flagged graph connects 737 of the 740 development cases into one component (`docs/research/execution/B8_MANUAL_REVIEW_REPORT_2026-10-06.md`).

The frozen procedure requires a manual review of every flagged pair, about 140–275 expert hours. Conservative linking of unreviewed pairs would put 99.6% of the cohort into one patient group, and the §6.3 split would then be impossible.

The owner does not accept manual adjudication of 49,468 pairs or a pause for it. This is a **feasibility-driven methodological amendment of the pre-split leakage safeguard**. It changes no endpoint, hypothesis, metric, model, condition, threshold rule of the analysis, test, bootstrap or Holm family.

## What is unchanged

- The T_screen rule, its value (0.2174) and the flagged pair list (`docs/data/records/B7/`).
- The decision categories SAME PATIENT / DIFFERENT PATIENT / UNRESOLVED.
- Conservative handling: **SAME PATIENT and UNRESOLVED are linked** for grouping, transitively, together with verified groups A and B and any shared real TCIA patient ID (§6.1, §6.2 step 5).
- Grouping is frozen before the split. The 70/10/20 split, seed `20260927`, stratification and assertions (§6.3) are unchanged.
- §6.2 permitted inputs. **Not used:**
  - model predictions;
  - segmentation performance;
  - split, validation, test or calibration results;
  - AURC;
  - any post-split information.

## Change

§6.2 step 4 (manual review of each flagged pair by the two named reviewers) is replaced by the deterministic procedure below. Every constant is in `configs/grouping/b8_automated_v1.0-A3.yaml`, SHA-256 `33c2410809b21ddde8a4a074dd886a61378624836a0d5c28356f33c1fea28428`.

The implementation is `src/brats_uncertainty/grouping/auto_b8.py` and `produce_b8_automated` in `src/brats_uncertainty/orchestration/steps.py`. All constants were fixed **before** the procedure was run on any study data. None was chosen from the flagged-pair distribution.

### Inputs

1. The four MRI sequences (T1, T1c, T2, FLAIR) of the 740 development cases. These are BraTS-preprocessed: SRI24 space, 1 mm, skull-stripped.
2. The ground-truth WT labels. They are used only to exclude the lesion from the anatomy comparison; they are already the basis of the frozen screen.
3. The TCIA crosswalk: TCIA collection, site ID and real TCIA patient ID. The placeholder `new-not-previously-in-TCIA` is not an identity.
4. UCSF-PDGM metadata v5: Sex and IDH class (wildtype / mutant; unknown never decides).

### Anatomy feature

**Per case:**
- The brain is the set of voxels that are > 0 in all four sequences.
- Each sequence is z-scored within the brain.
- Voxels within the WT label dilated by 3 voxels are excluded. The dilation uses a Euclidean ball, as in REPRODUCIBILITY.md item 1.
- Values are averaged over 4×4×4-voxel blocks. A block is valid if at least 50% of its voxels are valid brain outside the dilated lesion.

**Per pair:**
- **S** is the mean, over the four sequences, of the Pearson correlation of block values over the blocks valid in both cases. It measures non-tumour brain anatomy.
- **Coverage** is the number of shared valid blocks divided by the smaller of the two cases' brain-block counts.

### References (computed before any flagged pair is scored)

- **tau_neg** is the 0.999 quantile (numpy method "higher") of S over the negative reference: development pairs certified DIFFERENT PATIENT by metadata rules R3/R4.
  - The reference includes all development pairs, flagged or not.
  - It is a deterministic sample of at most 20,000 pairs, drawn with numpy `default_rng(20261006)` from the sorted list.
  - Only pairs with coverage ≥ 0.5 and ≥ 100 shared blocks are used.
- **tau_ctrl** is min(S_A, S_B) over the two verified same-patient pairs.

### Decision rules, in order (first match wins)

| Rule | Condition | Decision |
|---|---|---|
| R1 | the pair lies within verified group A or B | SAME PATIENT |
| R2 | both cases carry the same real TCIA patient ID | SAME PATIENT |
| R3 | both cases carry real TCIA patient IDs in the same TCIA collection, and the IDs differ (TCIA assigns one ID per patient within a collection) | DIFFERENT PATIENT |
| R4 | both cases are in the UCSF-PDGM metadata, and Sex differs or the known IDH class differs (IDH status does not change within a patient) | DIFFERENT PATIENT |
| R5 | coverage < 0.5 or fewer than 100 shared blocks (too little non-tumour anatomy to decide) | UNRESOLVED |
| R6 | S ≥ tau_ctrl (anatomy at least as concordant as the least concordant verified same-patient pair) | SAME PATIENT |
| R7 | tau_neg < S < tau_ctrl | UNRESOLVED |
| R8 | S ≤ tau_neg (no more concordant than 99.9% of certified different-patient pairs) | DIFFERENT PATIENT |

Every flagged pair already satisfies the protocol's lesion-overlap condition, because it was flagged by WT-label Dice ≥ T_screen.

### Acceptance criteria (pre-specified; no adjustment if any fails)

1. Both verified pairs have S > tau_neg and coverage ≥ 0.5. The feature must recognise the known same-patient pairs.
2. No development case has site ID 1.
3. Groups A and B each lie within one patient group.
4. Every flagged pair has exactly one decision.
5. **The largest resulting patient group has at most 8 cases.** Larger groups would indicate chaining of non-identical patients rather than a patient's timepoints, and would compromise the group split.

**If any criterion fails, gate B8 stops.** The audit record is committed, nothing is passed, and no rule or constant is changed in response. Any further change would require a new logged amendment and an owner decision.

## Records

The B8 evidence written by the runner is IDs and derived numbers only, never images:
- `docs/data/records/B8_automated_decisions.csv`: per pair, the decision, the rule, S and coverage.
- `docs/data/records/B8_automated_audit.json`: configuration hash, code commit, inputs used and not used, tau_neg, tau_ctrl, the control similarities, decision and rule counts, the group-size distribution and the acceptance results.
- `docs/data/records/B8_review_record.json`.

Gate B9 freezes the patient groups from these decisions (`stage_freeze_groups(..., automated_decisions=...)`).

## Scientific impact

None on endpoints. The safeguard's role is unchanged: to prevent same-patient leakage across partitions. The paper reports this amendment, the T_screen value, the flagged count, the decision and rule counts and the group-size distribution.
