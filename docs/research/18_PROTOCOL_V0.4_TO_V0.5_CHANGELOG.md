# 18 — Protocol v0.4 → v0.5 Changelog

| Field | Value |
|---|---|
| Protocol | [FINAL_RESEARCH_PROTOCOL.md](archive/FINAL_RESEARCH_PROTOCOL_v0.5_SUPERSEDED.md) |
| Change | v0.4 → **v0.5 — AMENDED PRE-FREEZE DRAFT, awaiting owner approval** (**NOT FROZEN**) |
| Type | **Substantive** (the pre-specified threshold-transfer estimand changed) |
| Date | 2026-09-28 |
| Authorization | Owner decision, 2026-09-28 |

## Changes

1. **S7 validation population changed from C5 to C4.**
   - τ_q = the largest observed U1 value with coverage(validation, U1 ≥ τ_q) ≥ q.
   - Coverage is now computed only on the validation C4 units {−T1, −T1c, −T2, −FLAIR}, with equal condition weighting.
   - Target Δrisk and Δcoverage are computed on each target set's C4 units (internal test, UPenn, BraTS-Africa).
   - S7 is interpreted as a single operating threshold learned from the four missing-sequence validation conditions and transferred unchanged.
2. **Full is excluded from τ estimation.** Full remains a supporting/control condition, may be reported separately, and does not influence the missing-sequence threshold.
3. **S13 mixture sensitivity remains C5-only, for S12.** S13 now applies only to the descriptive pooled S12 analysis, keeping (a) equal weights over C5 and (b) 80% Full + 5% for each single-missing condition. S7 is excluded from S13. No new C4 weights were introduced.
4. **Consequential clarifications** (no independent design change):
   - §19: τ_0.20 inherits the S7 validation population (C4; Full not used). It remains the descriptive confident-failure threshold.
   - §22 item 9: "full validation set" is reworded to "complete set of validation C4 units", to avoid confusion with the Full condition.

## Unchanged

- The primary H-W (mean over C4 of the within-condition ET ΔAURC) is **unchanged from v0.4**.
- The τ_q rule; q = 0.80 (primary) and 0.70/0.90 (sensitivity); no interpolation; no random tie-breaking.
- τ_q is estimated once on validation and never re-estimated on test, UPenn or BraTS-Africa.
- Independent validation/target bootstraps; the Δrisk and Δcoverage definitions; the F3/F3b Holm rules.
- τ_0.80 remains the primary deployment threshold.
- The C5 definition; S12; BraTS-Africa; H4; T_screen and the manual-review procedure; the lifecycle gates.

## Integrity

- **No test data seen.**
- **No experiment run** (no training, inference, metric calculation or EXP-001).
- **No split created.**
- No UPenn or BraTS-Africa evaluation.
- No v1.0 and no tag.
