# Gate B1: data-route authorization record

| Field | Value |
|---|---|
| **Status** | **AUTHORIZED: owner-approved alternative** (gate lifecycle `PASSED`, 2026-10-01) |
| Source class | `OWNER_APPROVED_ALTERNATIVE` |
| External provider authorization | **NONE.** No TCIA response exists, and no TCIA authorization is claimed. |
| Approved route | Direct official TCIA access into a private, access-restricted computational environment |
| Basis | The frozen B1 wording permits "an owner-approved alternative" (§5.1, SR7). The owner decision is logged as protocol amendment [v1.0-A1](../research/protocol-amendments/2026-10-01_B1_data-route.md) (DATA-ROUTE / OPERATIONAL). |
| Evidence | [B1_EVIDENCE_2026-10-01.md](B1_EVIDENCE_2026-10-01.md) |
| Protocol version | v1.0 (frozen 2026-09-28; tag `protocol-v1.0`; frozen text unchanged) |
| Dataset | RSNA-ASNR-MICCAI-BraTS-2021 (TCIA analysis result), DOI 10.7937/jc8x-9874 |
| Inquiry | [TCIA_DATA_ROUTE_INQUIRY.md](TCIA_DATA_ROUTE_INQUIRY.md): **not sent**, and not required for this route |
| Record created | 2026-09-29 |

**No study imaging data have been acquired.** B2 is AUTHORIZED, meaning ready but not executed. B3–B12 are LOCKED.

**Route restrictions:**
- no public mirror;
- no private Kaggle mirror;
- no third-party re-hosting;
- no redistribution;
- no raw data in GitHub;
- no raw data exposed through the website (Vercel/Netlify).

The official TCIA source remains the source of record, and the required attribution and citation are retained.

## 1. Intended research use

This is academic research in brain-tumour segmentation and case-level uncertainty under missing MRI sequences, as pre-registered in protocol v1.0. The data are used only to:

- train and evaluate nnU-Net models;
- compute IDs, hashes, counts and metrics.

Images, labels and licensed metadata files are never redistributed. Only IDs, hashes, counts and aggregate metrics are published.

## 2. Routes

The approved route is the owner-approved alternative: direct official TCIA access into a private, access-restricted computational environment. The data come only from the official download links on the TCIA BraTS 2021 page:
- the challenge package, through TCIA's public IBM Aspera Faspex package;
- the ID crosswalk, by direct HTTPS from www.cancerimagingarchive.net.

The data are held only in the private environment used for the study. No persistent copy is kept on a third-party dataset or storage service.

The routes considered on 2026-09-29/30 for the TCIA inquiry are **not** approved:

| Category | Route | Status |
|---|---|---|
| **A** | Private, access-restricted computational storage on a third-party platform, such as a private Kaggle dataset | **Not authorized.** This is private third-party re-hosting, which still needs TCIA confirmation under protocol §5.1. No such confirmation has been requested or received. |
| **B** | Runtime-only acquisition into third-party compute with no persistent copy | Covered only as part of the approved route: an owner-controlled private GPU environment (private VM, or a private Kaggle or Colab session) that receives the data directly from TCIA into its private, ephemeral storage, with no dataset, mirror or upload. See the administrative entry [2026-10-01_compute-environment.md](../research/protocol-amendments/2026-10-01_compute-environment.md) and [REMOTE_COMPUTE.md](../reproducibility/REMOTE_COMPUTE.md). |
| **C** | Another route approved by TCIA in writing | None exists |

## 3. Official sources (verified 2026-09-29; re-verified 2026-09-30 and 2026-10-01)

Only official TCIA pages were used, read in a browser on each date. Content was unchanged across the three dates. Blogs, forums, Reddit, Kaggle discussions and unofficial interpretations were not used. The statements below are short summaries, not legal conclusions. Details are in [DATA_ACCESS.md](DATA_ACCESS.md) §1 and [B1_EVIDENCE_2026-10-01.md](B1_EVIDENCE_2026-10-01.md) §3.

| Source | URL | Relevant content |
|---|---|---|
| TCIA Data Usage Policies and Restrictions | https://www.cancerimagingarchive.net/data-usage-policies-and-restrictions/ | Anyone considering **mirroring** TCIA's public datasets, or providing **direct access** to them via another tool or website, is directed to the Data Analysis Centers page. Dataset (DOI) citation is required. Participants must not be identified or contacted. |
| TCIA Data Analysis Center (DAC) | https://www.cancerimagingarchive.net/tcia-data-analysis-center/ | A DAC provides TCIA data by connecting to the TCIA REST API **or by mirroring collections**. The approved route is neither. |
| TCIA Support | https://www.cancerimagingarchive.net/support/ | Helpdesk **help@cancerimagingarchive.net** |
| TCIA BraTS 2021 analysis result | https://www.cancerimagingarchive.net/analysis-result/rsna-asnr-miccai-brats-2021/ | DOI 10.7937/jc8x-9874; Version 1, updated 2023/08/25; "Data Citation Required". The "Challenge data both tasks" package (142 GB) is **CC BY 4.0** and downloads through IBM Aspera Connect. The ID crosswalk (XLSX, 78.12 KB) is **CC BY 4.0**. |

The policies do **not** explicitly address a *private*, single-user copy in third-party compute storage. **This record makes no legal conclusion.**

## 4. B1 state rule

B1 changes from PENDING to AUTHORIZED only on a recorded basis that the status validator (`check_b1_evidence` in `src/brats_uncertainty/data/evidence.py`) accepts. The evidence file must be named `docs/data/B1_EVIDENCE_<date>.md` and be committed or staged in git. There are exactly two accepted source classes.

**1. `EXTERNAL_PROVIDER_AUTHORIZATION`:** a written provider authorization, such as:
- a TCIA Help Desk written response;
- an official TCIA written instruction;
- another authoritative written authorization from the provider.

The record follows [B1_EVIDENCE_TEMPLATE.md](B1_EVIDENCE_TEMPLATE.md):
- every field exactly once, filled in;
- an external evidence type;
- the provider's exact wording quoted;
- `Authorization status: AUTHORIZED` and `Conclusion: APPROVED`.

None exists for this project.

**2. `OWNER_APPROVED_ALTERNATIVE`:** the alternative named in the frozen B1 wording. **This is the basis in use.** The record must:
- name the project owner and a decision date that equals the date in the file name;
- cite the owner-approved alternative and a logged protocol amendment that exists in `docs/research/protocol-amendments/`;
- name an official dataset source and the download mechanism;
- record `NO` for third-party mirroring, public redistribution, repository data storage and website data exposure;
- record `External provider authorization: NONE`;
- never claim TCIA approval;
- have an approved route that names no Kaggle dataset, mirror, re-hosting or upload.

Authorization is **never** inferred from:
- the dataset being publicly downloadable;
- a TCIA web page;
- the CC BY 4.0 licence alone;
- Kaggle availability;
- a successful test download;
- API availability.

On 2026-09-30 this record accepted external evidence only. On 2026-10-01 the owner formally selected the owner-approved alternative that the frozen B1 wording permits. The decision is logged as amendment v1.0-A1, and the validator was extended to accept that source class under the rules above.

Synthetic authorization is kept apart from real authorization. A record carrying the synthetic test source class or any synthetic marker is refused by:
- the real gate;
- real acquisition ("synthetic authorization cannot authorize real-data acquisition");
- the repository scan, when it sits in a real evidence location.

The software is exercised on a synthetic fixture (`tests/fixtures/synthetic_b1/`) through a separate test-only state machine, `SYNTHETIC_TEST_B1: PENDING -> TEST_AUTHORIZED` (`src/brats_uncertainty/data/synthetic_b1.py`). That machine never reads or writes `docs/project_status.yaml`.

This record, the inquiry and the template are documentation and are always rejected as evidence.

## 5. How B1 was authorized

1. 2026-10-01: amendment v1.0-A1 was logged in `docs/research/protocol-amendments/`. Its scientific and methodological impact is none.
2. Evidence `docs/data/B1_EVIDENCE_2026-10-01.md` was written with source class `OWNER_APPROVED_ALTERNATIVE` and staged.
3. A dry run was performed, then the transition was applied:

   ```
   brats-uncertainty gate-transition B1 PASSED --evidence docs/data/B1_EVIDENCE_2026-10-01.md --on 2026-10-01 --approved-route "Direct official TCIA access into a private, access-restricted computational environment" --apply
   ```

   The transition:
   - set B1 to `PASSED` (shown as "Authorized — Owner-approved alternative");
   - set `data.authorization: APPROVED` and `data.approved_route` to the route above;
   - set B2 to `AUTHORIZED` (ready).

   B3–B12 stayed `LOCKED` and `data.acquired` stayed `false`.
4. The website data were regenerated with `brats-uncertainty export-site-data`.

## 6. Consequences now that B1 is authorized

- **B2** may be executed, only through the approved route and only with an adapter whose route equals `data.approved_route`. It has **not** been executed.
- **B3–B12** stay LOCKED until their prerequisites pass in order.
- **EXP-001** still needs its own D gates. D2 (approved data route) has not been closed.
- **Unchanged:** no data acquisition, hashing (B3–B4), manifest (B5), counts (B6), T_screen or patient grouping has taken place.

## 7. Change log of this record

| Date | Change |
|---|---|
| 2026-09-29 | Record created; status PENDING; inquiry prepared, not sent. |
| 2026-09-30 | B2–B6 software completed (tested on synthetic data only); B2–B6 set to LOCKED under the gate state machine; B1 unchanged (PENDING). |
| 2026-09-30 | Audit: B1 evidence must be `docs/data/B1_EVIDENCE_<date>.md` (template added), committed or staged, and must name the approved route. B1 remains PENDING. |
| 2026-09-30 | B1 workflow finalized. Inquiry rewritten with six questions and the three-way distinction (private computational storage, public redistribution, runtime-only access). Evidence template rewritten with all required fields. Validator set to accept only recorded external written authorization. Official sources re-verified. Inquiry **not sent**; B1 remains PENDING. |
| 2026-10-01 | Synthetic B1 workflow test added (SYNTHETIC_TEST_ONLY fixture, test-only state machine; synthetic authorization refused by the real gate, real acquisition and the repository scan). Evidence also requires `Source class:` and `Conditions:`. |
| 2026-10-01 | **B1 AUTHORIZED via the owner-approved alternative.** Amendment v1.0-A1 (DATA-ROUTE / OPERATIONAL) was logged. Evidence `B1_EVIDENCE_2026-10-01.md` has source class `OWNER_APPROVED_ALTERNATIVE` and external provider authorization NONE. Route: direct official TCIA access into a private, access-restricted computational environment. B2 AUTHORIZED (ready, not executed); B3–B12 LOCKED; no data acquired. Official sources re-verified. No TCIA authorization is claimed. |
