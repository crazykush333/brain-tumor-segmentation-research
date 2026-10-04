# data/ — private research data (NOT distributed through this repository)

**No research data are stored in Git.** Everything under `data/` except this README is
git-ignored, and `brats-uncertainty check-repo` (run in CI) refuses imaging, labels,
archives, arrays, licensed metadata, credentials and checkpoints anywhere in the
repository.

- **Raw BraTS data are not stored in Git.** The BraTS 2021 training data (and later
  BraTS-Africa) are acquired separately by each researcher from the official provider
  (TCIA), through the route approved at gate B1 (amendment v1.0-A1: direct official TCIA
  access into a private, access-restricted computational environment), under the
  providers' terms. See [`docs/data/DATA_ACCESS.md`](../docs/data/DATA_ACCESS.md).
- **Patient imaging is never committed** — no NIfTI, DICOM, masks, predictions or
  probability maps, and no images derived from them.
- **Manifests contain only permitted identifiers, hashes and provenance** (case IDs,
  file names, sizes, SHA-256, record fingerprints), committed as gate evidence in
  `docs/data/records/` once the corresponding gate has run.
- **Raw data remain in private execution storage** (`$BRATS_WORK` on the execution
  machine, outside the repository); nnU-Net folders and checkpoints live there too.

Current status: B1 has PASSED (owner-approved alternative); B2 (official acquisition) is
AUTHORIZED but **not executed — no data have been acquired**. Synthetic test data are
never generated here (the generator refuses any path inside the repository).

Optional local layout for a researcher's own machine (`brats-uncertainty init-data-dirs`):

| Path | Contents | Tracked by git? |
|---|---|---|
| `data/raw/` | official files exactly as acquired | **never** |
| `data/manifests/` | working copies of records produced by the code | no (evidence is committed under `docs/data/records/`) |
| `data/derived/` | anything computed from the images or labels | **never** |
| `data/cache/` | temporary files | **never** |

Rules: never type a hash, count or ID list by hand — the gated commands (`acquire`,
`hash-metadata`, `build-manifest`, `derive-counts`, …) produce them and fail until their
gates are open.
