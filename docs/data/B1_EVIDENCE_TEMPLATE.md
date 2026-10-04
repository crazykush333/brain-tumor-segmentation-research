# B1 evidence — template

**TEMPLATE - NOT EVIDENCE.** This file records no authorization and cannot close gate B1. **STATUS = PENDING.**

This template is for `EXTERNAL_PROVIDER_AUTHORIZATION` evidence. The owner-approved alternative (`OWNER_APPROVED_ALTERNATIVE`), which is the basis of the current B1 authorization, uses its own format; see [B1_DATA_ROUTE_AUTHORIZATION.md](B1_DATA_ROUTE_AUTHORIZATION.md) §4 and [B1_EVIDENCE_2026-10-01.md](B1_EVIDENCE_2026-10-01.md). External evidence is recorded only after actual external written evidence has been supplied. The status validator (`src/brats_uncertainty/data/evidence.py`) rejects this template, any copy that still contains the line above, and any copy with a `<FILL …>` placeholder. It also rejects any value that is empty, `PENDING`, `TBD` or `TODO`.

## What counts as evidence

Only one of these, in writing:

- a TCIA Help Desk written response (help@cancerimagingarchive.net) to the inquiry in [TCIA_DATA_ROUTE_INQUIRY.md](TCIA_DATA_ROUTE_INQUIRY.md);
- an explicit, official TCIA written instruction that names the proposed route or route category;
- another clearly authoritative written authorization from the data provider.

None of the following is authorization, and none may be used to fill this template:

- the dataset being publicly downloadable;
- a TCIA web page;
- the CC BY 4.0 licence on its own;
- the dataset's availability on Kaggle;
- a successful test download;
- the availability of an API.

## How to record real evidence

Do this only after the provider has replied.

1. Copy this file to `docs/data/B1_EVIDENCE_<Response date>.md`, for example `B1_EVIDENCE_2026-10-14.md`. The date in the file name must equal the `Response date:` field.
2. Delete the "TEMPLATE - NOT EVIDENCE" line. Replace every `<FILL …>` with the real value.
3. Paste the provider's exact wording under "Exact provider wording", as `> ` quoted lines. Redact personal contact details other than the official support address.
4. Set `Authorization status:` and `Conclusion:` from what the reply actually says:
   - **The reply authorizes the route:** use `AUTHORIZED` and `APPROVED`.
   - **The reply refuses it, or is inconclusive:** use `NOT AUTHORIZED` and `NOT APPROVED`. B1 then cannot pass. Record the outcome in [B1_DATA_ROUTE_AUTHORIZATION.md](B1_DATA_ROUTE_AUTHORIZATION.md) and, where appropriate, set B1 to FAILED or BLOCKED with this file as the evidence.
5. Stage the file with `git add`. Evidence must be in the git index and must not be git-ignored.
6. Dry run:

   ```
   brats-uncertainty gate-transition B1 PASSED --evidence docs/data/B1_EVIDENCE_<date>.md --on <date> --approved-route "<Approved route>"
   ```

   Add `--apply` only once the dry run succeeds. The website shows B1 PASSED as "Authorized". The command unlocks only B2; every other gate stays LOCKED.

## Machine-checked fields

Each field below must appear exactly once, at the start of a line, in the form `Name: value`.

| Field | Rule |
|---|---|
| Source class | exactly `EXTERNAL_PROVIDER_AUTHORIZATION`. A record carrying the synthetic test source class, the synthetic test-only label or a synthetic flag anywhere (see `src/brats_uncertainty/data/evidence.py`) is refused: synthetic authorization cannot authorize real-data acquisition. |
| Protocol version | must equal `protocol.version` in `docs/project_status.yaml` (`v1.0`) |
| Dataset | must equal `evidence_identity.dataset` in `configs/dataset/brats2021.yaml` |
| DOI | must equal `evidence_identity.doi` in the same file |
| Inquiry date | YYYY-MM-DD |
| Response date | YYYY-MM-DD, not before the inquiry date, and equal to the date in the file name |
| Route category | exactly `A`, `B` or `C` (see below) |
| Evidence type | exactly one of `TCIA Help Desk written response`, `Official TCIA written instruction`, `Other authoritative written authorization` |
| Approved route | identical to the `--approved-route` value, which becomes `data.approved_route` |
| Authorization status | `AUTHORIZED` is required to pass B1 |
| Conclusion | `APPROVED` is required to pass B1 |
| Recipient, Sender, Proposed route, Provider/source, Evidence reference, Interpretation, Conditions, Restrictions, Attribution requirements | non-empty and not a placeholder. Write `None stated` if the provider stated none. |

The `## Exact provider wording` section must contain at least one non-empty `> ` quoted line.

Route categories:

- **A:** private, access-restricted third-party computational storage, such as a private Kaggle dataset.
- **B:** runtime-only acquisition into an approved compute environment, with no persistent third-party copy.
- **C:** another route that the provider has approved in writing.

---

Source class: EXTERNAL_PROVIDER_AUTHORIZATION
Protocol version: v1.0
Dataset: RSNA-ASNR-MICCAI-BraTS-2021
DOI: 10.7937/jc8x-9874
Inquiry date: <FILL: date the inquiry was sent, YYYY-MM-DD>
Recipient: <FILL: help@cancerimagingarchive.net or the official TCIA contact who replied>
Sender: <FILL: full name and affiliation of the person who sent the inquiry>
Proposed route: <FILL: the exact route described in the inquiry>
Route category: <FILL: A | B | C>
Evidence type: <FILL: TCIA Help Desk written response | Official TCIA written instruction | Other authoritative written authorization>
Provider/source: <FILL: e.g. TCIA Help Desk, name and role of responder>
Response date: <FILL: date the written response was received, YYYY-MM-DD>
Evidence reference: <FILL: ticket number, message subject and date, or official document URL and version>
Interpretation: <FILL: one sentence stating what the response permits, without going beyond its wording>
Conditions: <FILL: conditions the approval depends on, quoted or closely tied to the wording; or None stated>
Restrictions: <FILL: access, storage, retention, deletion or sharing restrictions stated; or None stated>
Attribution requirements: <FILL: citations and acknowledgements required; or None stated>
Approved route: <FILL: exact route text; identical to --approved-route>
Authorization status: PENDING
Conclusion: PENDING

## Exact provider wording

> <FILL: paste the relevant sentences of the written response verbatim>

## Notes

<FILL: optional context, for example follow-up questions asked, or how the response maps to route A, B or C.>
