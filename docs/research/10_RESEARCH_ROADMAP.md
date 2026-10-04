# 10 — Research Roadmap

| Phase | Output | Gate | Status |
|---|---|---|---|
| 0. Research design | Documents 01–11, README | **Approval gate 1** (direction choice) | ✅ drafted 2026-09-27; awaiting review |
| 0b. Pre-protocol verification | Structured literature search for the chosen direction; full-text read of the closest papers; dataset terms verified; access applications submitted | — | not started |
| 0c. Protocol | `FINAL_RESEARCH_PROTOCOL.md` (pre-registration: hypotheses, splits, metrics, families, thresholds, compute budget) | **Approval gate 2** | not started |
| M1 | Repository skeleton, environment, CI, licence | tests pass | — |
| M2 | Dataset interface (modality order, label mapping), synthetic tests | tests pass | — |
| M3 | Preprocessing + de-duplication scripts; split files | split audit | — |
| M4 | Evaluation framework (metrics, reliability metrics, statistics) validated on synthetic cases with known answers | tests pass | — |
| M5 | Baseline configs (nnU-Net full, nnU-Net dropout) and Kaggle notebooks with resume | EXP-001 pilot runs; **cost measured** | — |
| M6 | Baseline experiments (EXP-010/011) | results logged | — |
| M7 | Studied condition / proposed method (direction-dependent) | — | — |
| M8 | Main experiments | — | — |
| M9 | Ablations (only those justified by the hypothesis) | — | — |
| M10 | Robustness / external validation (single pass, pre-registered) | — | — |
| M11 | Statistical analysis | — | — |
| M12 | Failure analysis | — | — |
| M13 | Figures from real results | provenance check | — |
| M14 | Reproducibility audit; `FINAL_RESEARCH_AUDIT.md` | — | — |
| M15 | GitHub release | **explicit owner confirmation before push** | — |
| M16 | Manuscript | — | — |

After every milestone: run tests, update docs and `CHANGELOG.md`, make a Git commit, and report what was actually completed.

## Rough timeline [ESTIMATE, highly uncertain]

- Phase 0b/0c: 1–2 weeks. Data-access approval time is outside our control.
- M1–M4: 2–3 weeks of part-time development (local).
- M5–M10: dominated by GPU quota. At ≈30 free GPU-h/week, training alone could take **4–10 weeks** depending on the direction and the schedule chosen. This will be re-estimated after EXP-001.
- M11–M16: 4–8 weeks.
