# Result verification protocol

This document defines how every scientific result of the pre-registered study is independently
verified before publication. It adds checks only. It changes nothing in the frozen protocol v1.0
(`docs/research/FINAL_RESEARCH_PROTOCOL_v1.0.md`, SHA-256
`704c0b495917344f44b93e7548ade0e32a71220265419516a2c83d626fcd9811`): the hypotheses, datasets,
split rules, seeds, model, conditions, metrics, thresholds, tests, bootstrap design, Holm
families, stopping rules and interpretation rules all stay as written there.

Implementation: `src/brats_uncertainty/verification/`. CLI: `brats-uncertainty verify-results`.
Orchestration: master-run steps `STATISTICS` → `VERIFY` → `WEBSITE` → `FINAL_AUDIT`
(`python scripts/remote/master_run.py --resume --commit --push`).

## 1. Principle

A result is verified only when an **independent recomputation** reproduces it from lower-level
evidence. A program finishing, a file existing, the tests passing or a figure being generated is
not verification. The independent code (`verification/independent.py`) does not import the
production metric, AURC, bootstrap-summary, Holm or threshold functions. It works from:

- integer voxel counts that the evaluation stores per unit, with exact rational arithmetic
  (`fractions.Fraction`):
  - `member_voxels`, `member_pair_intersections`, `member_gt_intersections`,
    `ensemble_gt_intersection`;
  - 15 calibration bins (`count:sum_p:sum_y`);
  - `brier_sse`;
- the AURC rank-weight identity AURC = (1/n) Σ r₍ᵢ₎ (Hₙ − H₍ᵢ₋₁₎), with tie blocks averaged;
- a brute-force search for τ_q;
- type-7 percentiles and a two-sided bootstrap p-value written out from their definitions.

The only shared input is the **canonical bootstrap resample matrix** (§3.3). Both sides must use
identical resamples.

## 2. Statuses

| Status | Meaning |
|---|---|
| PASS | exact equality |
| PASS_WITH_FLOAT_TOLERANCE | \|Δ\| ≤ 1e-12 or relative \|Δ\| ≤ 1e-9; reported with the maximum differences |
| FAIL | any larger difference, any missing input, any violated rule |
| NOT_PERFORMED | the check could not run; it **blocks** every scientific stage that needs it |
| NOT_APPLICABLE | only for EXTERNAL, when no external set has been evaluated (nothing external is published) |

Counts, Dice from counts, U1 from counts, τ_q, case lists and seeds must match exactly.

**Overall = VERIFIED** only if all of the following hold:

- every scientific stage is PASS or PASS_WITH_FLOAT_TOLERANCE: DATA, SPLIT, RUNS, CHECKPOINTS,
  METRICS, PRIMARY_AURC, BOOTSTRAP, THRESHOLDS, STATISTICS, CALIBRATION, FAILURES, EXTERNAL,
  TABLES, FIGURES, LINEAGE and REPRODUCIBILITY;
- the two publication stages, WEBSITE and PUBLIC_EXPORT, also pass;
- EXTERNAL may be NOT_APPLICABLE;
- CLEAN_ENV may be NOT_PERFORMED, which is recorded honestly as such.

Otherwise the overall status is **BLOCKED**.

## 3. Stages

### 3.1 Provenance (DATA, SPLIT, RUNS, CHECKPOINTS, EXTERNAL)

**DATA:**
- re-enumerates the private training tree with its own hashing;
- compares it with the B5 manifest (paths, sizes, SHA-256) and the B2 inventory;
- checks the B3/B4 metadata hashes;
- checks case IDs, the four modalities plus label, and the 1,251-case count.

**SPLIT:**
- checks 1,251 = 740 + 511 site-1 HOI cases, and split seed 20260927;
- checks full coverage, and that no site-1 case is in the split;
- checks that no patient group crosses partitions, including the verified groups;
- checks the split file hashes against the B12 record;
- rebuilds the assignment with the protocol's stratified group split from label features it
  computes itself (1 mm voxels; WT volume = voxel count / 1000).

**RUNS:**
- checks the identity of the six MAIN runs (arm, seed, trainer, epochs) and that each is
  COMPLETED;
- checks the dataset-manifest and split hashes;
- checks that each checkpoint lies inside its own run directory and matches its recorded
  SHA-256;
- checks that the attempts are recorded and that no checkpoint is shared.

**CHECKPOINTS:** loads each checkpoint and checks the trainer name, the final epoch and the 4
input channels. It is NOT_PERFORMED, and therefore blocking, if the checkpoints cannot be loaded.

**EXTERNAL:**
- UPenn HOI population = the 511 site-1 cases, with HOI groups and gate C4 closed;
- no HOI case in training or validation;
- each external set evaluated once per arm (ledger, SR4);
- BraTS-Africa gates C1–C3 closed, the frozen C3 eligible list, and no image identical to a
  BraTS 2021 image.

### 3.2 METRICS, PRIMARY_AURC

**METRICS:** every unit row is recomputed from its counts:
- member Dice;
- ensemble Dice;
- U1 = 1 − mean pairwise member Dice, with the protocol's empty-mask conventions.

**PRIMARY_AURC:** recomputes AURC(U1), AURC(I) and ΔAURC per condition for the ET region on the
internal test set, arm B. It also checks that:
- the C4 mean is the equal-weight mean of exactly the four single-missing conditions;
- Full is reported but **excluded** from the C4 estimand;
- the primary region is ET;
- each production `metrics.selective.aurc` value matches the independent value.

### 3.3 BOOTSTRAP (canonical resample artifact)

**Canonical draws:**
- patient-group bootstrap, seed **12345**, **10,000** replicates;
- draws are `numpy.random.default_rng(12345).integers(0, G, size=(R, G))` over the sorted group
  order;
- the transfer analysis draws validation then target groups per replicate from one generator.

**Shared artifact:** production writes `bootstrap/bootstrap_resamples_seed12345.json`. It holds
the seed, the method, the group order and the SHA-256 of the int64 little-endian draw matrix. The
matrix itself is not committed; it is regenerated from the seed and checked against the digest.
Production also writes every replicate statistic: `bootstrap_replicates_primary.csv` and
`bootstrap_replicates_transfer_q080.csv`.

**The verifier:**
- regenerates the draws and checks the digest;
- recomputes **every** replicate of the C4 mean and of each C4 condition on those draws;
- compares the replicates element-wise with production;
- recomputes the percentile CI, the p-value and the H-W decision (CI upper bound < 0);
- recomputes the TC/WT secondary analyses (S2) on the same draws.

A replicate count other than 10,000 fails.

### 3.4 THRESHOLDS

- τ_q for q ∈ {0.70, 0.80, 0.85, 0.90} is found by exact search on the **validation** C4 units
  only, with the realized coverage checked.
- I is checked per arm, region and condition.
- The threshold-transfer point quantities are checked for the three transfer q values (coverage
  and selective risk on validation and target, Δrisk, Δcoverage), using **exact rational
  coverage**.
- The declared transfer draws digest, every Δrisk/Δcoverage replicate, the CIs and the p-values
  are checked.

### 3.5 STATISTICS, CALIBRATION, FAILURES

**STATISTICS:**
- Holm is recomputed within each declared family only: F1, F2, F3, F3b, and F4 where declared;
- the claim rules of the frozen protocol are re-applied;
- descriptive blocks must carry no p-values.

**CALIBRATION:** ECE (15 equal-width bins) and the Brier score are recomputed from the stored bin
sums.

**FAILURES:** failure categories (volume-based rules) are recomputed and the per-condition lists
compared.

### 3.6 TABLES, FIGURES, LINEAGE, REPRODUCIBILITY, CLEAN_ENV

**TABLES:** every numeric cell of every scientific table is compared with the independent value
(`results/verification/table_verification.csv`).

**FIGURES:** every figure has a source-data CSV and a sidecar with `source_data_sha256`. The
verifier checks:
- the risk–coverage series point by point;
- the forest-plot estimates and CIs;
- every sidecar hash.

**LINEAGE:** every published value carries:
- its result ID and analysis ID;
- the dataset manifest, crosswalk, metadata, split and grouping hashes;
- the run IDs, model arm and seeds;
- the condition, region and metric;
- the analysis version, git commit, configuration and environment hashes;
- the protocol SHA-256 and the creation time.

An incomplete record fails.

**REPRODUCIBILITY:** a second complete analysis from the same inputs must produce byte-identical
outputs (`first_run_hash` = `second_run_hash`).

**CLEAN_ENV:** a rerun in a fresh environment. It is recorded as NOT_PERFORMED when impossible.

### 3.7 Publication (WEBSITE, PUBLIC_EXPORT)

**WEBSITE:**
- The built Results page (`website/out/results/index.html`) is parsed. Every scientific number
  must appear as
  `<span data-result-id=… data-field=… data-value=…>` with a value from the verified index,
  displayed rounded to 3 decimals.
- All primary and F1 results must be shown.
- The page must contain no synthetic or demo text.
- Before verification it must show no number at all, only *"Scientific results are being
  independently verified."* or *"Results pending real experimental execution."*
- The synthetic pipeline demonstration lives on the separate `/demo/` page.

**PUBLIC_EXPORT:**
- every published file must be a permitted public-safe type;
- no demo artifact may be published;
- the SHA-256 hashes are recorded in `results/verification/public_artifact_hashes.json`.

## 4. Publication gating and stop format

The real analysis is written privately to `work/eval/analysis`. The `VERIFY` step publishes to
`results/public-safe/` and sets `results.available` only if the scientific stages are VERIFIED.

If the publication checks then fail:
- the publication is **retracted** (files removed, status reset to *being independently
  verified*);
- the evidence is committed;
- the run stops.

The website exporter refuses `results.available = true` unless the verification manifest says
VERIFIED. Every failing check is reported as:

```
BLOCKED RESULT: <stage> | RESULT ID: <ids> | EXACT DISCREPANCY: <check>: production <x> vs recomputed <y> (<status>; <detail>) | AFFECTED ARTIFACTS: <...> | REQUIRED RERUN: <...>
```

## 5. Outputs

| File | Content |
|---|---|
| `results/verification/verification_manifest.json` | overall and scientific status, every stage and check, verified result index (empty unless VERIFIED), rerun hashes, audit |
| `results/verification/result_records.json` | lineage record per published value |
| `results/verification/table_verification.csv` | cell-by-cell table reconciliation |
| `results/verification/public_artifact_hashes.json` | SHA-256 of every public result file |
| `results/verification/consistency_audit.json` | the 23-question scientific consistency audit |
| `results/verification/RESULT_VERIFICATION_CERTIFICATE.md` | certificate |
| `results/verification/index.html` | quality-control dashboard (not a results page) |
| `docs/research/execution/RESULT_VERIFICATION_REPORT.md` | full report, including all discrepancies |

## 6. Discrepancies found during development

The verifier is tested against a synthetic study (software tests only, never published) and
against tampered artifacts: a table cell, a bootstrap replicate, a figure point, Full pooled into
the primary estimand, a failure list, a unit Dice, missing lineage, a wrong replicate count, and
missing data. Each tamper must be caught by the right stage.

**Real production discrepancy found and corrected (2026-10-05):**
- **What:** the bootstrap p-value of the threshold-transfer Δcoverage was 0.30 in production and
  0.32 when recomputed independently.
- **Cause:** production summed the condition weights in floating point, so an exactly zero
  Δcoverage became ±1e-17 and was counted on the wrong side of zero.
- **Fix:** production `weighted_coverage_risk` now uses exact rational coverage.
- **Effect:** no real analysis had run, so no real result was affected. This is also recorded
  permanently in every verification report.
