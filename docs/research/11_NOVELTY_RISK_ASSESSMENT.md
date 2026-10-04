# 11 — Novelty Risk Assessment

**No novelty is claimed at this stage.** This document lists what could invalidate each direction's contribution, and what must be done before any novelty statement appears in a manuscript.

## 1. Per-direction threats

| Direction | Closest known work | What would invalidate the contribution | Residual contribution if that happens |
|---|---|---|---|
| D1 Missing-sequence reliability | [C9] Set-inclusive uncertainty (2026); [C10] UAF-AIMM (2026); [D2] | A paper that already evaluates calibration/AURC across modality subsets with external data | Replication on external cohorts; clinical failure definitions |
| D2 Missing-modality benchmark | [B2] (general), [C6–C8] | An existing controlled benchmark of missing-modality architectures vs nnU-Net | Extension to external data / newer methods; still weaker |
| D3 Failure detection under real shift | [D2], [D3], [D4] | [D4] already covers BraTS-SSA with learned QC; [D2] covers aggregation broadly | Threshold transfer / clinical risk definitions — thin |
| D4 Pre→post-treatment | [A4], BraTS 2024/2025 proceedings | A BraTS 2024/25 paper analysing reliability across timepoints | Training-regime study with reliability metrics |
| D5 TTA reliability | [E1], [E2], general-ML TTA calibration work (not yet searched) | Existing TTA-calibration analyses in medical segmentation | Brain-tumour-specific evidence on real external cohorts |

## 2. Field-level risks (all directions)

- **"Only an evaluation paper."** Some reviewers undervalue empirical studies. Mitigation: pre-registered hypotheses, external data, rigorous statistics, and precedent venues that publish such work ([B2], [D2]).
- **Pseudo-external validation.** Mitigation: the de-duplication in [04](04_DATASET_STRATEGY.md) §3, and reporting overlap counts.
- **Compute-limited schedules.** A reduced training schedule may be criticized as not representative. Mitigation: report it explicitly, apply it identically across arms, and include one full-schedule anchor run if feasible.
- **Fast-moving literature.** Papers from 2026 (e.g. [C9], LASSNet 2609.06733) appeared within months of this review. The search must be repeated before submission.

## 3. Required before any novelty claim

1. A **structured search** (Google Scholar, PubMed, arXiv, MICCAI/MIDL/MELBA proceedings, 2022–present). Pre-defined query strings for the chosen direction, logged with date and hit counts in `docs/research/search_log.md`.
2. A **full-text read** of every paper in the "closest known work" column.
3. A written comparison table: what they did / what we do / what is different.
4. Wording discipline: "to our knowledge, no prior study has evaluated X under Y" only after steps 1–3, and scoped precisely. "First" and "state-of-the-art" are avoided unless strictly supported.
5. A re-check immediately before submission.
