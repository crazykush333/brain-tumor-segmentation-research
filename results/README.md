# results/

## Scientific results

**No real scientific results are available yet.**

The pre-registered experiment has not yet been executed because official BraTS data and
the required compute environment are pending. No model has been trained or evaluated,
and no synthetic or demonstration number is presented here as a scientific finding.

The repository already contains:

- the frozen research protocol ([`docs/research/FINAL_RESEARCH_PROTOCOL_v1.0.md`](../docs/research/FINAL_RESEARCH_PROTOCOL_v1.0.md));
- the reproducible execution pipeline (`brats-uncertainty master-run`);
- gate and state management with committed evidence;
- provenance tracking (commit, protocol hash, config and input hashes on every record);
- the evaluation infrastructure (per-unit metrics, statistics, figures, tables);
- a public-safe export and the website integration.

Real result artifacts are written here automatically by the gated pipeline after the
pre-registered experiment has been executed: `results/MAIN/` (per-unit metric CSVs,
validation SR2 record, frozen C5 thresholds), `results/public-safe/` (analysis artifacts,
figures, tables) and `results/index.json` (the list the website reads). Each artifact
records its experiment ID, git commit, config hash, protocol hash and input hashes.

## Machine-readable status

[`status.json`](status.json) is generated from `docs/project_status.yaml`
(`brats-uncertainty export-site-data`; CI checks it is in sync). Current values:
`scientific_results_available: false`, `real_experiment_executed: false`,
`real_brats_data_processed: false`, `status: pending_official_data_and_compute`.

## Synthetic demonstration (not results)

[`demo/`](demo/) holds a **synthetic demonstration — not real BraTS results**: the
study's own metric, statistics and figure code run on deterministic synthetic toy
volumes (seed 20261004) to show what this directory and the website will contain once the
real study has run. Every demo file is flagged `demo=true`, `synthetic=true`,
`scientific_result=false`; the export, the results index and the gate system refuse
demo files.
