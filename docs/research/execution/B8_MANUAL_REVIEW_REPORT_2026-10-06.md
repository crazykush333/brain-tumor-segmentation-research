# Gate B8: manual-review report (protocol §6.2), 2026-10-06

**Status: B8 RUNNING. No pair has been reviewed and nothing has been decided.**

Decisions are made only by the named reviewers:
- **Ayush Kushwaha** (primary reviewer);
- **Dr. Sreenivasa Chakravarthi** (second reviewer, for disagreements).

The runner never fills in decisions, and B8 is not passed automatically.

This report uses only committed, ID-level records:
- `docs/data/records/B7/t_screen.json`
- `docs/data/records/B7/screen_summary.json`
- `docs/data/records/B7/flagged_pairs.csv`
- `docs/data/records/B5_manifest.csv` (collections)

## 1. Why pairs were flagged (B7, frozen rule)

**Rule (frozen in v0.4).** T_screen is the minimum WT-label Dice over the two verified same-patient positive-control pairs. It was computed once at B7, before the pairwise distribution was examined.

| Control | Cases | WT-label Dice |
|---|---|---|
| A | BraTS2021_00626 + BraTS2021_00758 | 0.8650 |
| B | BraTS2021_00639 + BraTS2021_00557 | **0.2174** |

**T_screen = 0.2174**, set by control B.

**Flag reason:** WT-label Dice of the two cases' ground-truth WT masks ≥ T_screen. The masks are compared in the common SRI24 space, without registration.

**Evidence used to flag:** only the ground-truth WT labels of the 740 development cases (§6.2 steps 1–3). No prediction or outcome was used. The per-pair Dice values are deliberately not shown here, because §6.2 forbids reviewers from seeing Dice.

## 2. Flagged pairs

| Quantity | Value |
|---|---|
| Development cases | 740 |
| Unordered pairs compared | 273,430 |
| **Flagged pairs** | **49,468 (18.1%)** |
| Cases involved in at least one flagged pair | 737 of 740 |
| Flags per case (min / median / max) | 1 / 140 / 258 |
| Same-collection pairs | 12,750 |
| Cross-collection pairs | 36,718 |
| Both positive controls flagged | yes (by construction) |

**The complete list of every flagged pair** (case IDs) is `docs/data/records/B7/flagged_pairs.csv`. It has 49,468 rows, one per pair, and each pair's reason and evidence are as in §1. The collections come from `B5_manifest.csv`.

Largest collection combinations among the flagged pairs:

| Collection pair | Flagged pairs |
|---|---|
| UCSF-PDGM × new-not-previously-in-TCIA | 11,067 |
| new-not-previously-in-TCIA × new-not-previously-in-TCIA | 5,531 |
| UCSF-PDGM × UCSF-PDGM | 5,446 |
| TCGA-GBM × new-not-previously-in-TCIA | 5,134 |
| TCGA-GBM × UCSF-PDGM | 4,978 |
| TCGA-LGG × UCSF-PDGM | 2,900 |
| TCGA-LGG × new-not-previously-in-TCIA | 2,684 |
| other combinations | 11,728 |

## 3. Proposed patient grouping

**Before review**, applying §6.1 and §6.2 step 5 with no review decisions yet:
- **Verified group A:** {BraTS2021_00626, BraTS2021_00758}.
- **Verified group B:** {BraTS2021_00639, BraTS2021_00557}.
- **Shared real TCIA patient IDs:** none. The crosswalk's only shared value is the placeholder `new-not-previously-in-TCIA`, which is not an identity.
- **Every other development case** is its own patient group, pending review.

**After review**, SAME PATIENT and UNRESOLVED pairs are merged transitively (§6.2 step 5).

If the flagged pairs were left unreviewed and treated as linked, which is the conservative UNRESOLVED treatment, the transitive closure would be **one group of 737 cases**. The 70/10/20 patient-group split (§6.3) would then be impossible.

## 4. Feasibility and the owner's decision

The frozen procedure requires, for each of the 49,468 pairs, inspection of T1, T1c, T2, FLAIR and WT labels of both cases by the primary reviewer, plus second review of disagreements. At an assumed 10–20 s per pair, that is about **140–275 hours** of expert review.

The protocol has no stopping rule for this situation: SR1–SR8 cover compute, sanity, data, integrity, bugs, licensing and platform. Any change to the screen would therefore be a **logged amendment**, which must state that it was made **after** the flagged count was known (§6.2: "No threshold-shopping is permitted").

The options are the owner's. None is taken without an explicit decision:

1. **Review as frozen.** All 49,468 pairs are reviewed and recorded in the review CSV; B8 then passes on the recorded decisions.
2. **Logged amendment before any split.** Restrict or extend the screen with a rule fixed now and disclosed as post hoc, then review the resulting pairs. Examples:
   - use additional permitted metadata such as site or study date;
   - add a second similarity criterion on non-tumour anatomy.

   This is a design change under the freeze rule (§25). It must record the date, sections, change, reason and "test data seen: No". No test set exists yet.
3. **Stop and consult.** Pause the study at B8 while the reviewers assess the procedure.

## 5. Compute note

The B7 session (Kaggle version 4) ran with a **GPU T4 x2** accelerator. The per-run "without an accelerator" option was not honoured, because the notebook-level accelerator setting is GPU. B6 and B7 needed no GPU.

At B8, the runner began rendering one review panel per flagged pair into ephemeral session storage. For 49,468 pairs this is impractical and the output is lost at session end, so the session should be stopped.

Before any further B-gate session, the notebook-level accelerator must be set to **None**.
