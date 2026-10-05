# results/demo — SYNTHETIC DEMONSTRATION — NOT REAL BRATS RESULTS

> **SYNTHETIC DEMO — NOT REAL RESULTS.** Synthetic demonstration only — not a BraTS scientific result.
>
> demo=true · synthetic=true · scientific_result=false · seed 20261004 · generated 2026-10-05T17:53:02+00:00 · code commit `eff42d622dfd` · code sha256 `2e8be058f70d636f…`

This directory shows what the finished repository and website will look like once the pre-registered experiment has run. Everything here comes from deterministic synthetic toy volumes (`SYNTH_*` cases, seed 20261004) processed by the study's real metric, statistics and figure code. It is **not** a scientific-results directory.

- `synthetic_summary.json` — example statistics with full provenance flags
- `synthetic_metrics.csv` — example per-unit metric rows (protocol §24 layout)
- `synthetic_failure_analysis.csv` — example failure-category counts
- `synthetic_*.svg` — example figures (each visibly labelled)
- `synthetic_results_report.md` — the demonstration report

Regenerate (deterministic): `brats-uncertainty demo --out results/demo`.

Safeguards: demo files carry demo=true / synthetic=true / scientific_result=false; the generator refuses every real result namespace; the public export and the website results index refuse demo files; demo files can never serve as gate evidence.
