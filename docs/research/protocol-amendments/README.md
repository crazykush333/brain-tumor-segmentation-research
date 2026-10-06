# Protocol amendments and administrative entries

**Protocol v1.0 has three logged amendments: v1.0-A1, v1.0-A2 and v1.0-A3.** The frozen v1.0 text and the `protocol-v1.0` tag are unchanged.

**v1.0-A1 — 2026-10-01 — DATA-ROUTE / OPERATIONAL.** Owner-approved direct official TCIA access into a private, access-restricted computational environment.

- External provider authorization: **NONE**.
- TCIA response: **NONE**.
- This is the owner-approved alternative already permitted by gate B1 ("TCIA confirmation on private third-party re-hosting (or an owner-approved alternative), per §5.1 and SR7").
- Scientific impact: none.
- Methodological impact: none.
- Not authorized: third-party re-hosting, Kaggle mirroring and public redistribution.

**v1.0-A2 — 2026-10-06 — DATA-ROUTE / OPERATIONAL.** Owner-approved official TCIA BraTS-Africa download (DOI 10.7937/v8h6-8x67, processed release CC BY 4.0) into a private, access-restricted computational environment (gate C1). External evaluation only; scientific and methodological impact: none.

**v1.0-A3 — 2026-10-06 — METHOD / FEASIBILITY (executed; failed its acceptance checks; withdrawn — see the administrative entry of the same date).** Gate B8: the 49,468 pairs flagged by the frozen T_screen rule are adjudicated by a pre-specified deterministic procedure (non-tumour anatomy of the four MRI sequences, crosswalk and UCSF-PDGM metadata) instead of exhaustive manual review. Made after the flagged count was known (disclosed); T_screen, categories and conservative linking unchanged; no endpoint change.

Rules (protocol v1.0, "Freeze rule" and §25):

1. The frozen file `docs/research/FINAL_RESEARCH_PROTOCOL_v1.0.md` is never edited in place.
2. Any **design change** requires a logged amendment recording the date, version, sections, change, reason and whether any test data had been seen. The owner must approve it. No change is allowed after any test-set evaluation.
3. **Execution records** from gates B–D are appended as logged **administrative entries**. They include hashes, counts, the computed T_screen value, patient groups, split hashes and EXP-001 measurements, and do not change the pre-registered design.
4. Each amendment or administrative entry is a separate file in this directory: `YYYY-MM-DD_<gate-or-topic>.md`. Its effect on the machine-readable mirror (`configs/protocol/`) and on `docs/project_status.yaml` is committed in the same change.

| Date | Type | Gate / sections | File | Test data seen? |
|---|---|---|---|---|
| 2026-10-01 | Amendment v1.0-A1 (DATA-ROUTE / OPERATIONAL) | B1; §5.1 operational data route; SR7 | [2026-10-01_B1_data-route.md](2026-10-01_B1_data-route.md) | No |
| 2026-10-01 | Administrative entry (OPERATIONAL; no design change) | Remote compute environment for the B1 route; §17, §24; SR8 | [2026-10-01_compute-environment.md](2026-10-01_compute-environment.md) | No |
| 2026-10-06 | Amendment v1.0-A2 (DATA-ROUTE / OPERATIONAL) | C1; §5 BraTS-Africa operational data route; SR7 | [2026-10-06_C1_brats-africa-route.md](2026-10-06_C1_brats-africa-route.md) | No |
| 2026-10-06 | Amendment v1.0-A3 (METHOD / FEASIBILITY) | B8; §6.2 steps 4–5 | [2026-10-06_B8_automated-adjudication.md](2026-10-06_B8_automated-adjudication.md) | No |
| 2026-10-06 | Administrative entry: v1.0-A3 failed and withdrawn; proposed v1.0-A4 failed its pre-split dry run (not adopted) | B8; §6.2 | [2026-10-06_B8_A3-withdrawn-A4-dry-run.md](2026-10-06_B8_A3-withdrawn-A4-dry-run.md) | No |
