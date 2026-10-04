# 16 — Protocol v0.3 Changelog

> **Superseded:** the protocol is now v0.4. See [17_V0.3_TO_V0.4_CHANGELOG.md](17_V0.3_TO_V0.4_CHANGELOG.md). This file records the v0.3 amendment only.


| Field | Value |
|---|---|
| Protocol | [FINAL_RESEARCH_PROTOCOL.md](archive/FINAL_RESEARCH_PROTOCOL_v0.5_SUPERSEDED.md) |
| Change | v0.2 → **v0.3 — AMENDED PRE-FREEZE DRAFT, awaiting owner approval** (NOT FROZEN) |
| Date | 2026-09-28 |
| Authorization | Owner, 2026-09-28 (controlled amendment A1–A5) |
| Source | [15_PREFREEZE_VERIFICATION_REPORT.md](15_PREFREEZE_VERIFICATION_REPORT.md) §13 |

**Unchanged:** the research question (§1), H-W (§2.1), the primary endpoint (§3), models, experiments and the endpoint structure. §1–§3 were verified byte-identical to v0.2.

**Test data seen: No, for every item.** No test, held-out-institution or BraTS-Africa evaluation data were used. Only public identifier/metadata files were consulted.

| ID | Issue | Correction | Reason | Source | Sections | Test data seen? |
|---|---|---|---|---|---|---|
| **A1** | "One BraTS subject = one patient" is false. Two same-patient follow-up pairs exist in development, and 243 development rows have placeholder TCIA IDs. | The patient group becomes the unit for split, stratification and bootstrap. The verified groups A (00626 + 00758) and B (00639 + 00557) are hard-coded. A pre-split label-only WT-Dice same-patient screen is added: **threshold and review procedure TO BE PRE-SPECIFIED BEFORE SPLIT CREATION** (checklist item 7). The split script must assert site ≠ 1, development = 740 before grouping, and no group spanning partitions. The HOI bootstrap is also grouped. | Prevents correlated follow-up scans from crossing train/validation/test and keeps resampling valid | TCIA `UCSF-PDGM-metadata_v5.csv`; BraTS 2021 crosswalk | §5 table, §6.1–6.3, §7, §13, §15, §16, §18, §20 SR3, §22 (11), §24 | No |
| **A2** | The unsafe-transfer rule used an unadjusted 95% CI, while F3 was Holm-corrected. No p-value procedure existed for secondary families. | Two-sided bootstrap p = 2 × min[P*(Δ ≥ 0), P*(Δ ≤ 0)] for all tested secondaries. Holm within F1–F5 only. Claims use the Holm-adjusted p < 0.05 plus the sign in the hypothesised direction. "Unsafe transfer" = Holm-adjusted p < 0.05 **and** Δrisk > 0 (Δrisk > 0 means the target is worse than validation). "Inefficient transfer" moved to a new family **F3b** (Δcoverage < 0). Unadjusted CIs are descriptive. No global FWER claim. H-W is unchanged. | Internal statistical inconsistency | 15 §10 | §4 S7, §13, §14, §21 | No |
| **A3** | τ was undefined under U1 ties (mass points at 0 and 1). The limitation "coarse values" was misstated. | τ_q = the largest observed U1 with validation coverage(U1 ≥ τ_q) ≥ q. No interpolation and no random tie-breaking. Validation only, never re-estimated. τ_q, realized validation coverage and realized target coverage are reported for q = 0.80 (primary), 0.70 and 0.90 (sensitivity). The U1 properties and limitation are rewritten (3 pairs; continuous; mass at 1 and 0; tiny-ET false alarms; 0.5 threshold). | Deterministic, reproducible operating point | 15 §9–10 | §4 S7, §11, §16, §18, §22 (4, 9) | No |
| **A4** | "Synapse / TCIA Restricted License Agreement" is outdated. Private re-hosting was unresolved. | TCIA challenge package listed as CC BY 4.0. Synapse access authenticated under Synapse terms. TCIA Data Usage Policy and citations apply. "Private third-party re-hosting (including private Kaggle dataset storage) requires confirmation from TCIA before use." No public Kaggle mirror. Data route pending owner confirmation. No legal conclusion. | Accuracy of access and licence terms | TCIA BraTS 2021 page; TCIA Data Usage Policy; Synapse "Rules & Resources" | §5.1, checklist item 5, §20 SR7, §22 (12) | No |
| **A5** | "BraTS-Africa, TCIA v2 release" is inaccurate. | Changed to "TCIA BraTS-Africa collection (Version 1, updated 2024-09-04; metadata file `BraTS-Africa_TCIA_datainfo_v2.xlsx`)". Kept: 95 Glioma / 51 OtherNeoplasms, ≤ 95 eligible, 4 sequences, expected labels 1 = NETC / 2 = SNFH / 3 = ET, and cases with fewer than 3 sub-regions (possible ET absence). A metadata-vs-file-level verification table was added. | Factual correction | TCIA BraTS-Africa collection page and metadata | §5 table, §5.2, §5 notes, checklist item 4 | No |

## Minor v0.3 clarification (2026-09-28; no version change)

This is separate from A1–A5 and is not a new amendment.

- **U1 wording (§11, §22 item 4).** The phrase "U1 is continuous in general" is technically imprecise. It now reads "U1 can take many distinct values, but is discrete because it is computed from finite binary masks". The U1 definition, both-empty = 1, empty/non-empty → 0, the fixed 0.5 member threshold and the τ_q ≥ rule (no interpolation, no random tie-breaking, validation-only estimation) are unchanged. *(The A3 row above still paraphrases the earlier wording "continuous"; this clarification supersedes it.)*
- **A1 wording (§6.2).** The screen is rewritten as an explicit ordered procedure, stated to be a leakage-prevention safeguard that is not a substitute for patient-identity metadata and cannot guarantee complete duplicate detection. The split may occur only after the grouping is frozen.
- **Not resolved:** **T_screen** and the **manual-review procedure** remain **TO BE PRE-SPECIFIED BEFORE SPLIT CREATION**. A search of the project documents (2026-09-28) found no defensible, directly applicable threshold, so none was invented.
- Test data seen: **No.**

## Remaining unresolved (unchanged by v0.3)

- The BrainLes/BraTS 2024 LNCS volume (partially closed; waiver or re-screen).
- The PNDC full text (unverified).
- Crosswalk SHA-256 at split time.
- BraTS-Africa file-level verification.
- TCIA confirmation on private re-hosting, then the owner's data-route decision.
- T_screen and the manual-review procedure for the §6.2 screen.
- EXP-001 (not authorized; depends on the data route).
- Owner approval for freeze.

**Next gate:** OWNER REVIEW OF FINAL_RESEARCH_PROTOCOL.md v0.3.
