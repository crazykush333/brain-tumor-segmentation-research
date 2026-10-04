# Research status

Snapshot of the real study (the authoritative, machine-checked record is
[`docs/project_status.yaml`](../project_status.yaml); the website and `results/status.json`
are generated from it).

| Item | Status | Detail |
|---|---|---|
| Research protocol | ✅ Frozen | v1.0, 2026-09-28, SHA-256 `704c0b49…6fcd9811`; one logged amendment (v1.0-A1, data route, no scientific change) |
| Repository | ✅ Public reproducible release | clean release snapshot; development history archived ([ARCHIVAL_PROVENANCE.md](ARCHIVAL_PROVENANCE.md)) |
| Tests | ✅ Passing | synthetic fixtures only; verified locally before release (pytest, ruff, mypy, package and website builds); CI runs on `main` |
| Execution engine | ✅ Implemented | `brats-uncertainty master-run`: gated steps B2 → final audit, resume, provenance, safe export |
| Data route (B1) | ✅ Approved | owner-approved alternative; no external TCIA authorization is claimed |
| EXP-001 authorization (D1, D2) | ✅ Closed | owner authorization of the compute pilot; approved route |
| Official BraTS data (B2) | ⏳ Pending | authorized, not executed; no data acquired |
| Data gates B3–B12 | ⏳ Pending | locked until B2 passes, in protocol order |
| GPU execution / EXP-001 pilot (D3–D6) | ⏳ Pending | no suitable GPU environment has been used yet |
| Main training (6 runs) | ⏳ Pending | not started |
| Internal evaluation | ⏳ Pending | not started (needs C5, C6 / `eval-v1`) |
| External evaluation | ⏳ Pending | not started (UPenn HOI; BraTS-Africa needs an approved route) |
| Scientific results | ⏳ Not available | `results/status.json`: `scientific_results_available: false` |
| Synthetic pipeline demonstration | ✅ Available | [`results/demo/`](../../results/demo/) — synthetic, labelled, never a scientific result |

**Real experiment status: pending official data acquisition and suitable GPU execution.**
Nothing in this repository claims a trained model, an evaluation, external validation or
a statistically significant finding.

Known owner actions before the real study can complete: the B2 delivery and execution
environment; implementation-choice confirmations due before specific gates
([REPRODUCIBILITY.md §4](../reproducibility/REPRODUCIBILITY.md)); the human B8 and C4
reviews; the D6 decision if a pilot quantity cannot be measured on the platform; the HD95
evaluator pin (C6); a BraTS-Africa data route (C1, SR7).
