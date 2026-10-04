# Protocol v1.0 amendment A1: B1 operational data route

Amendment ID: v1.0-A1
Amendment type: DATA-ROUTE / OPERATIONAL
Date: 2026-10-01
Owner: Ayush Kushwaha
Protocol: v1.0 (frozen 2026-09-28, tag `protocol-v1.0`, SHA-256 `704c0b495917344f44b93e7548ade0e32a71220265419516a2c83d626fcd9811`). The frozen file and its tag are unchanged.
Sections: Checklist gate B1; §5.1 "Other data-handling rules" (operational data route); SR7
Test-set data seen before amendment: No

## Versioning

The freeze rule requires any post-freeze change to be logged as an amendment in §25, recording the date, version, sections, change, reason and whether test data had been seen. The protocol defines no version-number convention for post-freeze amendments. This amendment is therefore identified as **v1.0-A1** (amendment 1 to v1.0).

The frozen v1.0 text is not edited, the protocol document version stays **v1.0**, and `protocol-v1.0` is neither moved nor recreated. Under `docs/research/protocol-amendments/README.md`, this file is the logged §25 entry.

## Previous state

The operational route was pending an external TCIA response. Protocol §5.1 says the route is "pending owner confirmation after the TCIA reply" (gates B1/D2; SR7). Gate B1 was PENDING.

## Reason

No external TCIA response was received in the required timeframe. The prepared inquiry (`docs/data/TCIA_DATA_ROUTE_INQUIRY.md`) was not sent. The owner therefore formally selects the owner-approved alternative already permitted by B1:

> B1. Approved data route: TCIA confirmation on private third-party re-hosting (or an owner-approved alternative), per §5.1 and SR7.

SR7 provides for this case. Where confirmation from TCIA has not been obtained, compute halts "until a compliant workflow is established and approved by the owner".

## Change

The §5.1 bullet "The operational data route is pending owner confirmation after the TCIA reply" is resolved, without a TCIA reply, as follows.

**New state:** owner-approved direct official TCIA access into a private, access-restricted computational environment. In the status file this is the exact value of `data.approved_route`: "Direct official TCIA access into a private, access-restricted computational environment".

- The official TCIA source remains the source of record: https://www.cancerimagingarchive.net/analysis-result/rsna-asnr-miccai-brats-2021/ (DOI 10.7937/jc8x-9874).
- Data are obtained only through the official TCIA download route on that page:
  - the public TCIA IBM Aspera Faspex package for the challenge data;
  - direct HTTPS from www.cancerimagingarchive.net for the ID crosswalk.
- Acquired research data remain in the private, access-restricted computational environment used for the study, with no persistent copy on a third-party dataset or storage service.

The project will not:

- create a public mirror;
- create a private Kaggle dataset mirror;
- redistribute the dataset;
- upload the raw dataset to GitHub;
- expose the raw dataset through the website (Vercel/Netlify);
- use an unofficial mirror as the source of record.

| Item | Status |
|---|---|
| Third-party re-hosting | Not authorized |
| Kaggle mirroring | Not authorized |
| Public redistribution | Not authorized |
| External provider authorization | NONE. This owner decision does not claim that TCIA separately approved this alternative. |
| TCIA response | NONE |

Private third-party re-hosting (for example, private Kaggle dataset storage) still needs TCIA confirmation under §5.1. It is outside this amendment.

## Impact

- **Scientific impact:** none.
- **Methodological impact:** none.
- **Unchanged:** research question, hypotheses, endpoints, dataset population, grouping, T_screen, split, model, missingness policy, uncertainty definitions, statistics and external evaluation.
- **Effective before:** any real data acquisition. No study imaging or label-volume data have been accessed. B2–B12 have not executed.
- **Status effect,** committed in the same change:
  - B1 moves from PENDING to PASSED, which the website shows as "Authorized — owner-approved alternative". The evidence is `docs/data/B1_EVIDENCE_2026-10-01.md`, with source class `OWNER_APPROVED_ALTERNATIVE`.
  - `data.authorization` becomes APPROVED, and `data.approved_route` records the route above.
  - B2 becomes AUTHORIZED (ready, not executed).
  - B3–B12 stay LOCKED.
  - The machine-readable protocol mirror (`configs/protocol/`) is unchanged, because no design parameter changes.
