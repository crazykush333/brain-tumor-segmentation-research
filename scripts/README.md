# scripts/

Thin command-line entry points over the `brats_uncertainty` package. Every script
that touches study data, trains, predicts or evaluates first calls
`require_action(...)`. It therefore **fails with `ResearchGateError` until the
corresponding protocol gates are closed** (with evidence) in
`docs/project_status.yaml`.

| Script | Gated action | Gates required |
|---|---|---|
| `checks/check_repository.py` | — (safe) | — |
| `reporting/export_site_data.py` | — (safe) | — |
| `data/acquire.py` (B2) | `acquire_data` (only with `--execute`; dry run by default) | B1 PASSED, B2 AUTHORIZED/RUNNING, `data.authorization: APPROVED`, matching route |
| `data/hash_metadata.py --gate B3` / `--gate B4` | `record_crosswalk_hash` / `record_ucsf_metadata_hash` | B1–B2 PASSED, own gate AUTHORIZED |
| `data/validate_data.py` | `validate_data` | B1–B2 |
| `data/build_manifest.py` (B5) | `build_manifest` | B1–B4 |
| `data/derive_counts.py` (B6) | `derive_counts` | B1–B5 |
| `grouping/compute_t_screen.py` | `compute_t_screen` | B1–B6 |
| `grouping/run_pairwise_screen.py` | `pairwise_screen` | B1–B6 (+ T_screen record) |
| `grouping/freeze_patient_groups.py` | `freeze_patient_groups` | B1–B8 |
| `splitting/create_split.py` | `create_split` | B1–B9 |
| `experiments/train.py` | `train_main` | B1–B12, D1–D6 |
| `evaluation/analyze_primary.py` | `evaluate_internal_test` | B1–B12, D1–D6, C5, C6 + `eval-v1` checkout |
| `remote/master_run.py` (`run_all.sh`, `run_all.ps1`) | every step's own action, in order | each step's gates; stops at the first unmet one |

**Master entry point.** `python scripts/remote/master_run.py --resume --commit --push`
(= `brats-uncertainty master-run`) runs the whole frozen protocol: it re-derives every
gate from `docs/project_status.yaml`, executes each permitted step in order through the
gated stages above, resumes interrupted work, commits/pushes allow-listed public-safe
milestones, and stops only at a genuine blocker with the exact gate, blocker and action.
`--plan` shows the step statuses without executing anything. See
[docs/reproducibility/REMOTE_COMPUTE.md](../docs/reproducibility/REMOTE_COMPUTE.md) §9.

Run from the repository root, for example `python scripts/checks/check_repository.py`.
Data locations are passed as arguments or environment variables and never hard-coded.
