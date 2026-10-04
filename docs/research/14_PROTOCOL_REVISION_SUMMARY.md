# 14 — Protocol Revision Summary (v0.1 → v0.2)

| Field | Value |
|---|---|
| Date | 2026-09-27 |
| Protocol | [FINAL_RESEARCH_PROTOCOL.md](archive/FINAL_RESEARCH_PROTOCOL_v0.5_SUPERSEDED.md) **v0.2 — REVISED DRAFT, awaiting owner approval** |
| Authoritative audit | [13_PRE_FREEZE_AUDIT.md](13_PRE_FREEZE_AUDIT.md) (verdict B) |
| Status | **READY FOR OWNER REVIEW — NOT YET FROZEN** |

No code was written, no data downloaded, no splits created and no experiments run.

## 1. What changed and why

| # | Change | Why | Literature or evidence that caused it |
|---|---|---|---|
| 1 | Research question now asks about **within-condition, case-level** discrimination and its transfer | The missing sequence is known at deployment. Only within-condition information is actionable, and a pooled comparison cannot isolate it. | Joham et al., UNSURE 2026 (pooled vs within-site E-AURC) |
| 2 | Single primary **H-W**: mean over C5 of the within-condition ET ΔAURC (U1 − I) < 0; α = 0.05; 95% patient-bootstrap CI (10,000 replicates); −T1c reported separately | The former S11 is the only direct test of "beyond missingness identity". Removing the co-primaries frees α. | 13 §8 items 1, 5, 7, 8 |
| 3 | H-SEG demoted to supporting/sanity; full-input TOST kept | It replicates established accuracy findings. | Ruffle 2023; Öchsner 2026; Pemberton 2023 |
| 4 | Pooled U1 vs I made descriptive (S12); added the **I-then-U1** lexicographic ranker and **mixture-weight sensitivity** (equal; 80% Full + 5% × 4) | Pooled AURC mixes between-condition difficulty with within-condition discrimination and depends on arbitrary weights. | Joham 2026; 13 §8 item 3 |
| 5 | ECE/Brier (S4) and H2 reframed as a **replication** | Voxel-level calibration under missing-modality combinations and regions is already published. | **MMA-LTS**, Lee et al., MICCAI 2026; SimMLM/MoFe 2025 |
| 6 | HOI = **511** site-1 UPenn-origin cases (403 + 108); development = **740** | Avoids same-institution leakage. 403 was an undercount. | TCIA `BraTS2021_MappingToTCIA.xlsx` (inspected; not committed) |
| 7 | BraTS-Africa = **95** glioma (v2 release); 51 OtherNeoplasms excluded; expected labels 1 = NETC, 2 = SNFH, 3 = ET, **pending file-level check** | Resolves the 60/75/95 conflict. | TCIA `BraTS-Africa_TCIA_datainfo_v2.xlsx`; BraTS 2023 label documentation |
| 8 | Threshold transfer: **Δrisk** and **Δcoverage** with independent validation/target bootstraps; 80% coverage primary, 70% and 90% sensitivity; "unsafe" / "inefficient" transfer only by CI rules | The v0.1 rule treated the validation risk as a fixed point and ignored coverage drift. | 13 §8 item 11 |
| 9 | Volume failure renamed "RANO 2.0-motivated relative ET volume error ≥ 40%", with 65% sensitivity; 1 mL labelled a study choice | RANO 2.0 thresholds describe longitudinal change, not segmentation error. | RANO 2.0 (Wen et al., JCO 2023, via AJNR/KJR summaries) |
| 10 | Removed mirroring-TTA, QU-BraTS score and lesion-wise Dice. C15 limited to internal test and arm B. | Not needed for the question; saves compute. | 13 §8 item 12 |
| 11 | Multiplicity: families F1–F5, Holm within family only; no cross-family FWER claim | Honest scope of error control. | 13 §8 item 6 |
| 12 | Stopping rules SR6 (projected > 220 GPU-h: ordered reductions), SR7 (licensing), SR8 (platform change) | Feasibility risks. | 13 §10 |
| 13 | Novelty statement rewritten conservatively | It must acknowledge the closest prior work. | MMA-LTS, SimMLM/MoFe, Joham 2026, Zenk 2025, BraTS-GoAT, accuracy/volumetry literature |

## 2. What remains unresolved

These are the pre-freeze checklist items in the protocol.

1. BrainLes / BraTS 2024 proceedings are unscreened.
2. PNDC (IEEE TMI 2025) full text is unverified.
3. The SHA-256 of the BraTS 2021 / TCIA crosswalk must be recorded at the data milestone.
4. BraTS-Africa label values, eligible count and sequence completeness must be verified on the files.
5. Whether BraTS 2021 data may be re-hosted privately on Kaggle (licensing).
6. The EXP-001 compute pilot (all compute figures are estimates).
7. Owner approval.

**Scientific risks carried forward:**

- H-W may be a predictable positive (uncertainty usually correlates with error). The informative results are then the per-condition components (especially −T1c), the external replication and the transfer analyses.
- The UPenn held-out institution is likely a mild shift.
- BraTS-Africa yields wide CIs.

## 3. Next approval gate

**Gate: owner review of protocol v0.2.**

The owner can:

- **(a) approve v0.2 as the analysis plan.** This authorizes closing checklist items 1–5, and then EXP-001 (the compute pilot) only.
- **(b) request amendments**, which produce v0.3.
- **(c) reject the direction.**

Freezing to v1.0 requires owner approval **and** a closed (or explicitly waived) checklist. Implementation beyond EXP-001 does not begin before v1.0.
