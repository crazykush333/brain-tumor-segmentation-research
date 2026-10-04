# B2 official download runbook (manual steps for the owner)

**Status: B2 is AUTHORIZED (ready) and has not been executed. No data have been downloaded.**

The owner's local Windows machine cannot run the study, so B2 is performed in a private remote GPU environment that receives the data directly from TCIA. There are two paths: runtime acquisition with a command confirmed in the session (notebook 00), or manual official delivery on a private VM. Both are described in [REMOTE_COMPUTE.md](../reproducibility/REMOTE_COMPUTE.md) §4 and run through notebook `experiments/kaggle/01_data_access_and_b2.ipynb` or the same CLI steps on a VM. The steps below are the manual path. These steps are performed manually by the project owner. Claude Code does not install software, download the dataset, or handle credentials.

| Item | Value |
|---|---|
| Gate | B2: official data acquired via the approved route |
| Approved route | Direct official TCIA access into a private, access-restricted computational environment (owner-approved alternative, amendment [v1.0-A1](../research/protocol-amendments/2026-10-01_B1_data-route.md); external provider authorization: NONE) |
| Official source | https://www.cancerimagingarchive.net/analysis-result/rsna-asnr-miccai-brats-2021/ (DOI 10.7937/jc8x-9874; Version 1, updated 2023/08/25) |
| Private destination | A folder on this machine **outside the Git repository**, for example `D:\BraTS2021_private\delivery\` (download) and `D:\BraTS2021_private\raw\` (import copy) |

## 1. What to download (and what not to)

The **DOWNLOAD (142GB)** link on the official page opens TCIA's public IBM Aspera Faspex package "RSNA-ASNR-MICCAI-BraTS-2021". Its listing was viewed during the B2 pre-flight on 2026-10-01; nothing was downloaded then.

Select **only**:

1. `RSNA-ASNR-MICCAI-BraTS-2021.sums`, the provider checksum file at the package root;
2. `RSNA-ASNR-MICCAI-BraTS-2021/BraTS2021_TrainingSet/`, the NIfTI training set. Its layout is `<collection>/BraTS2021_<ID>/` with collection folders such as ACRIN-FMISO-Brain, CPTAC-GBM, IvyGAP, TCGA-GBM, TCGA-LGG, UCSF-PDGM, UPENN-GBM and new-not-previously-in-TCIA.

Do **not** download `BraTS2021_TrainingSet_dcm`, `BraTS2021_ValidationSet` or `BraTS2021_ValidationSet_dcm`. The frozen protocol uses the BraTS 2021 training cases only.

Also download these two official files from TCIA by direct HTTPS. Save them **without opening or re-saving them** (no Excel, no editor), because B3 and B4 hash their exact bytes:

3. `BraTS2021_MappingToTCIA.xlsx` (78.12 KB), from https://www.cancerimagingarchive.net/wp-content/uploads/BraTS2021_MappingToTCIA.xlsx
4. `UCSF-PDGM-metadata_v5.csv`, from https://www.cancerimagingarchive.net/wp-content/uploads/UCSF-PDGM-metadata_v5.csv (linked from https://www.cancerimagingarchive.net/collection/ucsf-pdgm/)

## 2. Before the transfer: disk-space preflight

Do not assume a size. Select items 1 and 2 in the Aspera client and read the **selected size** it shows. Then run:

```bash
brats-uncertainty storage-preflight --selected-gib <size shown by the client> --delivery-dir "D:/BraTS2021_private/delivery" --storage-dir "D:/BraTS2021_private/raw"
```

The preflight:
- counts, for each copy, the client-reported selection plus an allowance for the two B3/B4 metadata files (16 MiB by default; `--metadata-mib`), which are downloaded separately;
- adds a 10 % margin per copy and keeps 10 GiB free per drive;
- counts the download and the import copy on the same drive when they share one;
- creates nothing.

**Start the transfer only if it prints `PREFLIGHT OK`.** If it fails, choose a drive with more space (or put the import copy on the other drive), or stop.

## 3. The transfer (manual)

1. Install the IBM Aspera client yourself, from IBM's official page linked on the TCIA BraTS 2021 page: https://www.ibm.com/products/aspera/downloads. Claude Code does not install software.
2. Open the TCIA **DOWNLOAD (142GB)** link and select only items 1 and 2.
3. Download into the delivery folder.
4. Put items 3 and 4 into the same delivery folder, at its top level.

The delivery folder should then look like this:

```
D:\BraTS2021_private\delivery\
    RSNA-ASNR-MICCAI-BraTS-2021.sums
    RSNA-ASNR-MICCAI-BraTS-2021\BraTS2021_TrainingSet\<collection>\BraTS2021_<ID>\...
    BraTS2021_MappingToTCIA.xlsx
    UCSF-PDGM-metadata_v5.csv
```

If the client nests the `.sums` file differently, keep whatever the client produced and tell Claude Code where it is.

**Keep the original directory hierarchy.** Do not move case folders out of their collection folders, flatten, rename, unzip or re-save anything. The software reads the official nested layout as delivered.

## 4. Hard rules

- No Kaggle dataset (public or private) and no Kaggle mirror.
- No Hugging Face, Google Drive sharing, S3 or other upload.
- No raw data in GitHub or Git LFS, and none exposed through the website.
- No sharing links to the raw data.
- No credentials in the repository, in logs or in chat. The download does not need a TCIA login; if a prompt appears, handle it yourself.

## 5. After the download: hand over to the gated B2 procedure

Tell Claude Code that the download has finished. Every step below is gated by the project status, and B2 is marked PASSED only after review:

1. **Provider checksums**, on the delivery exactly as downloaded:

   ```bash
   brats-uncertainty verify-checksums --sums "D:/BraTS2021_private/delivery/RSNA-ASNR-MICCAI-BraTS-2021.sums" --root "D:/BraTS2021_private/delivery" --select RSNA-ASNR-MICCAI-BraTS-2021/BraTS2021_TrainingSet --out data/manifests/B2_provider_checksums.json
   ```

   The `.sums` file is used exactly as delivered. An unknown line format stops with an explicit error instead of a guess.
2. **Local import.** Run a dry run first, then the same command with `--execute`:

   ```bash
   brats-uncertainty acquire --adapter local-import --delivered "D:/BraTS2021_private/delivery" --dataset-version "Version 1 (2023/08/25)" --route "Direct official TCIA access into a private, access-restricted computational environment" --storage-root "D:/BraTS2021_private/raw" --storage-label "owner private storage (D:)" --acquired-by "<name>" --out data/manifests/B2.json
   ```

   Files are copied byte-for-byte with their relative paths, so the official hierarchy is preserved and nothing is flattened. The copy fails closed if the storage drive lacks space. Absolute paths are never recorded.
3. Owner review of the B2 record; then B3, B4, B5 and B6 in order, as in [DATA_PROVENANCE.md](DATA_PROVENANCE.md) §3. B5 uses `--data-root <storage>/RSNA-ASNR-MICCAI-BraTS-2021/BraTS2021_TrainingSet` and `--data-root-reference RSNA-ASNR-MICCAI-BraTS-2021/BraTS2021_TrainingSet`, so every manifested file is cross-checked against the B2 inventory.
