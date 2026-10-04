# Synthetic Results Demonstration

> **SYNTHETIC DEMO — NOT REAL RESULTS.** Synthetic demonstration only — not a BraTS scientific result.
>
> demo=true · synthetic=true · scientific_result=false · seed 20261004 · generated 2026-10-04T19:31:27+00:00 · code commit `6a7e0af6ef0e` · code sha256 `1d0b377d213c417b…`

## Purpose

This report demonstrates the repository's result-generation pipeline: the same code that will produce the real per-unit metrics, statistics and figures, run on deterministic synthetic toy volumes.

## IMPORTANT

These are synthetic examples. They are **not** generated from BraTS 2021, UPenn or BraTS-Africa, and they must not be interpreted as scientific findings. No value below supports or rejects the study's hypotheses.

## Demonstrated pipeline

- metric calculation (Dice with the protocol's empty-mask convention, risk = 1 − Dice)
- uncertainty calculation (U1 ensemble agreement; I from the validation freeze)
- risk–coverage and AURC with expected tie handling
- calibration (ECE / Brier within the protocol ROI)
- threshold transfer (τ_q frozen on validation C4 units, applied unchanged)
- failure analysis (confident failure, hallucinated / missed ET)
- figure generation, provenance and export

## Example outputs (synthetic)

| Example quantity | Synthetic value | Note |
|---|---|---|
| Mean over C4 of ET ΔAURC (U1 − I) | -0.1958 [-0.2533, -0.1334] | Synthetic demonstration only — not a BraTS scientific result. |
| ΔAURC -T1 | -0.1986 | Synthetic demonstration only — not a BraTS scientific result. |
| ΔAURC -T1c | -0.1799 | Synthetic demonstration only — not a BraTS scientific result. |
| ΔAURC -T2 | -0.2036 | Synthetic demonstration only — not a BraTS scientific result. |
| ΔAURC -FLAIR | -0.2012 | Synthetic demonstration only — not a BraTS scientific result. |
| τ_0.80 (validation C4) | 0.3484 | Synthetic demonstration only — not a BraTS scientific result. |
| Δrisk / Δcoverage at τ_0.80 | 0.0542 / -0.1615 | Synthetic demonstration only — not a BraTS scientific result. |

Figures: `synthetic_risk_coverage.svg`, `synthetic_calibration.svg`, `synthetic_uncertainty_vs_error.svg`, `synthetic_failure_analysis.svg`. Tables: `synthetic_metrics.csv`, `synthetic_failure_analysis.csv`.

## Real study status

Official data acquisition is pending. No real model results are available. Real result artifacts are written only by the gated pipeline after the pre-registered experiment has been executed, and never to this directory.
