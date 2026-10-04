# Data access

**Status (2026-10-01): gate B1 is AUTHORIZED through the owner-approved alternative (lifecycle `PASSED`; amendment v1.0-A1; external provider authorization NONE). B2 is AUTHORIZED (ready, not executed). B3–B12 are LOCKED. No study data have been acquired.** The B2–B6 software is implemented and tested on SYNTHETIC_TEST_DATA only ([B1_DATA_ROUTE_AUTHORIZATION.md](B1_DATA_ROUTE_AUTHORIZATION.md)).

Labels used below:

- **VERIFIED FACT** — read on an official source on the stated date.
- **PLANNED WORKFLOW** — what this project intends to do; not yet done.
- **PENDING PROVIDER CONFIRMATION** — must not be assumed until TCIA confirms in writing.

## 1. Official source information (VERIFIED FACT, 2026-09-29; TCIA pages re-verified 2026-09-30)

All sources are official TCIA pages, read in a browser. The statements are short summaries, not legal interpretation.

| Source | URL | Verified content |
|---|---|---|
| TCIA BraTS 2021 analysis result | https://www.cancerimagingarchive.net/analysis-result/rsna-asnr-miccai-brats-2021/ | DOI 10.7937/jc8x-9874. "Data Citation Required". Version 1, updated 2023/08/25. The page lists 1,480 subjects and 142 GB. The "Challenge data both tasks" package (DICOM and NIfTI) is **CC BY 4.0**, and its download lists the IBM Aspera Connect plugin as a requirement. The "ID Crosswalk map between BraTS ID and TCIA ID" (XLSX, 78.12 KB) is **CC BY 4.0**. Some linked original source DICOM falls under the NIH Controlled Data Access Policy; it is not needed. The page acknowledges Synapse ID syn25829067 and carries an April 2026 note on source-manifest updates. |
| TCIA Data Usage Policies and Restrictions | https://www.cancerimagingarchive.net/data-usage-policies-and-restrictions/ | No identification or contact of participants, and no identifying representations such as facial images. Datasets (DOI data citation) must be acknowledged. Anyone **mirroring** public datasets, or providing **direct access via another tool or website**, is directed to the Data Analysis Centers page. DACs must attribute each dataset, link to the policy and require the same downstream. Datasets that need data use agreements are hosted by the NCI CRDC (dbGaP) since April 2025. |
| TCIA Data Analysis Center (DAC) | https://www.cancerimagingarchive.net/tcia-data-analysis-center/ (legacy wiki page `pageId=22515655` redirects here) | A DAC is a tool or website that provides TCIA data via the REST API **or by mirroring collections**; developers contact the helpdesk. Kaggle is not in the legacy DAC listing reviewed; not being listed is neither permission nor prohibition. |
| TCIA Support | https://www.cancerimagingarchive.net/support/ | Helpdesk **help@cancerimagingarchive.net**, +1 385-275-8242. |
| UCSF-PDGM collection (gate B4 source) | https://www.cancerimagingarchive.net/collection/ucsf-pdgm/ | Links `UCSF-PDGM-metadata_v5.csv` at https://www.cancerimagingarchive.net/wp-content/uploads/UCSF-PDGM-metadata_v5.csv |

Carried over from protocol §5.1 (verified 2026-09-27/28; **not re-verified**): Synapse access requires an authenticated account and is subject to the Synapse Terms of Use. Kaggle's own terms of service were not reviewed.

Dataset roles (protocol §5):

| Role | Dataset | Planned size |
|---|---|---|
| Development and held-out institution | BraTS 2021 training cases | **Protocol verification targets** (not results): total 1,251, site 1 = 511, development 740. Verified only when gate B6 derives them from the hashed crosswalk. |
| External population | TCIA BraTS-Africa (DOI 10.7937/v8h6-8x67) | ≤ 95 (gates C1–C3) |

## 2. Approved acquisition route

**Direct official TCIA access into a private, access-restricted computational environment.** This is the exact value of `data.approved_route` in `docs/project_status.yaml`.

| Item | Value |
|---|---|
| Source class | `OWNER_APPROVED_ALTERNATIVE`: the alternative permitted by the frozen B1 wording (§5.1, SR7) |
| Basis | Owner decision of 2026-10-01, logged as protocol amendment [v1.0-A1](../research/protocol-amendments/2026-10-01_B1_data-route.md) (DATA-ROUTE / OPERATIONAL; scientific and methodological impact: none) |
| Evidence | [B1_EVIDENCE_2026-10-01.md](B1_EVIDENCE_2026-10-01.md) |
| External provider authorization | **NONE.** No TCIA response exists, and no TCIA authorization is claimed. |
| Source of record | the official TCIA BraTS 2021 page and its download links: the public TCIA Aspera Faspex package for the challenge data, and HTTPS from www.cancerimagingarchive.net for the crosswalk |
| Where the data live | only the private, access-restricted computational environment used for the study |

Restrictions:

- no public mirror;
- no private Kaggle mirror;
- no third-party re-hosting;
- no redistribution;
- no raw data in GitHub;
- no raw data exposed through the website (Vercel/Netlify);
- TCIA citation and attribution retained.

## 3. Routes that remain unauthorized (PENDING PROVIDER CONFIRMATION)

| Question | Status |
|---|---|
| Is a private, single-user copy on Kaggle or another third-party store permitted, or does it count as "mirroring"? | **Not authorized.** It would need TCIA confirmation under §5.1. The inquiry ([TCIA_DATA_ROUTE_INQUIRY.md](TCIA_DATA_ROUTE_INQUIRY.md)) has not been sent. |
| Is runtime-only download into Kaggle/Colab permitted? | Not separately authorized; outside the approved route |

**Nothing in this repository states or implies that Kaggle storage is permitted.** Documentation, URLs, public downloadability or platform access are never treated as authorization.

B1 changes from PENDING to AUTHORIZED (gate status `PASSED`) only on a recorded basis the validator accepts. There are two source classes:

- `EXTERNAL_PROVIDER_AUTHORIZATION`: a TCIA Help Desk written response, an explicit official TCIA written instruction, or another clearly authoritative written authorization. None exists for this project.
- `OWNER_APPROVED_ALTERNATIVE`: an owner decision under the frozen B1 wording, backed by a logged protocol amendment. This is the basis in use.

The external class follows the rules below. It is never inferred from public downloadability, a TCIA web page, the CC licence alone, Kaggle availability, a successful test download or API availability. B1 closes only through `brats-uncertainty gate-transition B1 PASSED --evidence docs/data/B1_EVIDENCE_<response date>.md --on <date> --approved-route "<route>" --apply`. The evidence must follow [B1_EVIDENCE_TEMPLATE.md](B1_EVIDENCE_TEMPLATE.md) with every field filled in from the reply, including `Authorization status: AUTHORIZED`, `Conclusion: APPROVED` and the provider's exact wording. It must be staged or committed in git and name the same route. The B1 record, the inquiry and the template are documentation and are rejected as evidence. That command sets `data.authorization: APPROVED` and unlocks B2 (AUTHORIZED); every other gate stays LOCKED.

## 4. Runtime acquisition procedure (PLANNED WORKFLOW; B2 ready, not executed)

The manual official download (IBM Aspera, `BraTS2021_TrainingSet` and the `.sums` file only, a disk-space preflight first, the official nested hierarchy kept) is described in [B2_OFFICIAL_DOWNLOAD_RUNBOOK.md](B2_OFFICIAL_DOWNLOAD_RUNBOOK.md).

```
approved source -> acquisition (B2) -> integrity verification -> manifest (B5) -> count verification (B6)
```

`brats-uncertainty acquire` is a **dry run by default**. It only prints the plan and never touches the network or the disk. With `--execute`, a real adapter runs only if all of the following hold, and otherwise fails closed with *"Real-data acquisition is locked because B1 data-route authorization has not been recorded."*:

- gate B1 must have status PASSED (today: PASSED, owner-approved alternative);
- gate B2 must have status AUTHORIZED or RUNNING (today: AUTHORIZED, not executed);
- `data.authorization` is `APPROVED`;
- the adapter's `--route` equals `data.approved_route`.

| Adapter | Use | Notes |
|---|---|---|
| `local-import` | import files the operator obtained through the approved route (e.g. the TCIA Aspera download, run with the operator's own credentials) | byte-for-byte copy into the git-ignored storage |
| `https-file` | small public official files (e.g. the metadata CSV) | HTTPS only; refuses URLs carrying credentials; query strings and user-info are stripped from logs and records |
| `synthetic-fixture` | SYNTHETIC_TEST_DATA for software tests | generates data outside the repository only; records are `synthetic: true` and can never close a gate |

There is no `--force` or bypass flag. The B2 record stores:

- source: dataset, version, DOI, source URL and route;
- adapter;
- acquisition timestamp;
- acquirer;
- storage location, as a logical or repository-relative label (never an absolute path);
- the full file inventory (relative path, size, SHA-256);
- the provenance stamp: code commit, package version, protocol version and hash, config hashes and environment.

## 5. Integrity verification

`brats-uncertainty validate-data` (gated: B1 PASSED and B2 runnable or passed) checks:

- expected files, naming and modality completeness;
- label availability, duplicate or colliding IDs and unexpected files;
- corrupt files (gzip CRC plus NIfTI header);
- dimensional consistency and hash mismatches.

It reports every issue in one pass.

## 6. Manifest generation (B5)

`brats-uncertainty build-manifest` (gated: B1–B4 PASSED and B5 runnable) needs the crosswalk and UCSF-PDGM files **with their B3/B4 records** (`--metadata-file` and `--metadata-record`). Each file must still match its recorded SHA-256. The command re-runs the integrity audit, refuses empty trees and any error, and writes the **RAW DATA MANIFEST**: JSON following `configs/schemas/raw_data_manifest.schema.json`, with an optional CSV of the file table. For each file it records:

- case ID, file type and modality;
- file name, relative path and size;
- SHA-256.

It also records the dataset, source, DOI, version, a link to the B2 record fingerprint, the acquisition timestamp and provenance, plus summary counts and duplicate-content groups. Processed files get a separate **DERIVED/PROCESSED DATA MANIFEST** (`derived_data_manifest.schema.json`), linked to its parent manifest hash.

## 7. Count verification (B6)

`brats-uncertainty derive-counts` (gated: B1–B5 PASSED and B6 runnable) works in four steps:

1. It re-hashes the crosswalk and compares the hash with the B3 record.
2. It derives the counts from the file by the site-ID rule, never from constants.
3. It compares them with the protocol targets.
4. It writes a record with status **VERIFIED_FROM_SOURCE** (real data only) or **FAILED_VERIFICATION**, including diagnostics. Synthetic runs can at best reach **SYNTHETIC_TEST_ONLY**, which can never close B6.

On failure it stops (SR3). The protocol targets are never changed to fit the data. Before any real run, the only state is **EXPECTED_BY_PROTOCOL** (`brats-uncertainty count-targets`).

## 8. What is and is not stored in GitHub

| Stored in GitHub | Never stored in GitHub |
|---|---|
| code, configs, JSON Schemas, frozen protocol, documentation, `docs/project_status.yaml`, website | MRI scans, NIfTI/DICOM, label volumes, predictions, arrays |
| after owner review: B2–B6 records containing only file names, sizes, hashes, counts, ID-list hashes and provenance | licensed metadata files (crosswalk XLSX, UCSF-PDGM CSV, BraTS-Africa XLSX) |
| the manifest hash and summary | full real-data manifests (default; see DATA_PROVENANCE.md) |
| synthetic-data *code* | synthetic data files and synthetic records (generated in temporary folders only) |
| | credentials (`kaggle.json`, `.env`, Synapse config, tokens), checkpoints, archives |

`.gitignore` and `brats-uncertainty check-repo` (run in CI) enforce this. The scan also flags credential assignments and hard-coded personal paths.
