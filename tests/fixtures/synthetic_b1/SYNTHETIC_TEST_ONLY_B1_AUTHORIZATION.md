# SYNTHETIC_TEST_ONLY — synthetic B1 authorization fixture

**SYNTHETIC_TEST_ONLY. This is NOT an actual TCIA response and NOT B1 evidence.**

This fixture exists only to exercise the B1 parser, content checks and the test-only state machine (`SYNTHETIC_TEST_B1: PENDING -> TEST_AUTHORIZED`, see `src/brats_uncertainty/data/synthetic_b1.py`). The real gate B1 refuses it, and so does any real acquisition that relies on it: synthetic authorization cannot authorize real-data acquisition. Never copy it to `docs/data/B1_EVIDENCE_<date>.md`; the repository scan flags synthetic content there.

The project owner supplied the synthetic response on 2026-10-01, labelled as a synthetic software-test fixture. `Inquiry date` is a fixture value because the synthetic response states none. Every other field is taken from the synthetic response.

Source class: SYNTHETIC_TEST_AUTHORIZATION
Synthetic: true
Test-only marker: SYNTHETIC_TEST_ONLY
Protocol version: v1.0
Dataset: RSNA-ASNR-MICCAI-BraTS-2021
DOI: 10.7937/jc8x-9874
Inquiry date: 2026-10-01
Recipient: help@example.invalid (synthetic)
Sender: Researcher (synthetic; addressed as "Dear Researcher")
Proposed route: Private, access-restricted computational environment used solely for the stated academic research project (synthetic)
Route category: A
Evidence type: TCIA Help Desk written response
Provider/source: Synthetic Test Provider, Synthetic Test Environment (From: TCIA Help Desk <help@example.invalid>)
Response date: 2026-10-01
Evidence reference: Email "RE: Request for confirmation of permitted computational access route for BraTS 2021", 2026-10-01 (synthetic)
Interpretation: Synthetic software test only: the official data may be accessed and retained in a private, access-restricted computational environment used solely for the stated academic research project, for the duration of the approved analysis
Conditions: Used solely for the stated academic research project; retained only for the duration of the approved analysis; compliance with applicable TCIA data-use requirements
Restrictions: No public redistribution; not made available to unauthorized third parties; public derived research artifacts must not redistribute the underlying imaging dataset or expose unnecessary patient-level information
Attribution requirements: Retain the required TCIA dataset attribution and citation
Approved route: SYNTHETIC_TEST_ONLY private access-restricted computational environment, retention for the duration of the approved analysis
Authorization status: TEST_AUTHORIZED
Conclusion: TEST_APPROVED

## Exact provider wording

Synthetic response, verbatim as supplied:

> From: TCIA Help Desk <help@example.invalid>
> Date: 2026-10-01
> Subject: RE: Request for confirmation of permitted computational access route for BraTS 2021
>
> Dear Researcher,
>
> Thank you for contacting The Cancer Imaging Archive regarding your
> proposed academic use of the RSNA-ASNR-MICCAI-BraTS-2021 dataset.
>
> For purposes of this synthetic software test only, assume that the
> following computational workflow has been approved:
>
> 1. The official BraTS 2021 data may be accessed within a private,
>    access-restricted computational environment used solely for the
>    stated academic research project.
>
> 2. The data may be retained within that private computational
>    environment for the duration of the approved analysis.
>
> 3. The dataset must not be publicly redistributed or made available
>    to unauthorized third parties.
>
> 4. The researcher must retain the required TCIA dataset attribution
>    and citation and must comply with the applicable TCIA data-use
>    requirements.
>
> 5. Any derived research artifacts made public must not redistribute
>    the underlying imaging dataset or expose unnecessary patient-level
>    information.
>
> This synthetic message is not an actual TCIA authorization and must
> not be used as evidence of permission for real-world data acquisition.
>
> Regards,
>
> Synthetic Test Provider
> Synthetic Test Environment

## Notes

SYNTHETIC_TEST_ONLY. The response says nothing explicit about runtime-only access, and this fixture infers nothing about it.
