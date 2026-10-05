# Protocol v1.0 amendment A2: BraTS-Africa operational data route

Amendment ID: v1.0-A2
Amendment type: DATA-ROUTE / OPERATIONAL
Date: 2026-10-06
Owner: Ayush Kushwaha
Protocol: v1.0 (frozen 2026-09-28, tag `protocol-v1.0`, SHA-256 `704c0b495917344f44b93e7548ade0e32a71220265419516a2c83d626fcd9811`). The frozen file and its tag are unchanged.
Sections: Checklist gate C1; §5 (BraTS-Africa external population, operational data route); SR7
Test-set data seen before amendment: No

## Previous state

Gate C1 was REVIEW_REQUIRED. `configs/dataset/brats_africa.yaml` had `source.route: null`. Amendment v1.0-A1 (gate B1) covers the BraTS 2021 package only, so under SR7 no BraTS-Africa data could be acquired.

## Change

The owner approves the following operational route for the BraTS-Africa external evaluation set:

- **Route:** official TCIA BraTS-Africa download, processed release, into a private, access-restricted computational environment.
- **Source of record:** TCIA BraTS-Africa, Version 1 (updated 2024-09-04), DOI 10.7937/v8h6-8x67.
- **Licence:** CC BY 4.0 for the processed release.
- **Configuration:** `source.route` in `configs/dataset/brats_africa.yaml` is set to this route.

The rules of amendment v1.0-A1 also apply here:

- data stay in private session or VM storage;
- no persistent copy is kept on a third-party dataset or storage service;
- no Kaggle Dataset is created and nothing is redistributed;
- the metadata workbook (`BraTS-Africa_TCIA_datainfo_v2.xlsx`) is never committed.

## What does not change

- BraTS-Africa remains **external evaluation only**, used with `eval-v1` code. It is never used for training, tuning or thresholds.
- Inclusion stays the frozen `95 Glioma` sheet, with the final count frozen at C3.
- Gates C1–C3 still require their file-level verification:
  - labels;
  - layout;
  - no image identical to a BraTS 2021 image.

## Impact

- Scientific impact: none.
- Methodological impact: none. The route only makes the pre-registered external evaluation executable.
