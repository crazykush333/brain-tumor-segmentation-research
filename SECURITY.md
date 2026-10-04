# Security and data-exposure policy

## What must never be in this repository

- MRI scans or any imaging file (`.nii`, `.nii.gz`, `.dcm`, `.mha`, `.nrrd`, …)
- patient-level labels, predictions or arrays derived from patient data
- licensed metadata files (`BraTS2021_MappingToTCIA.xlsx`, `UCSF-PDGM-metadata_*.csv`, `BraTS-Africa_TCIA_datainfo_*.xlsx`)
- credentials: Kaggle (`kaggle.json`), Synapse (`.synapseConfig`), `.netrc`, `.env` files, API keys, tokens, private keys
- model checkpoints (unless the data providers confirm publication is acceptable, protocol §5.1)

The `.gitignore` blocks these patterns. `brats-uncertainty check-repo` (run in CI and by `make check`) fails on prohibited file types, licensed metadata names, likely secrets and files over 5 MiB.

## Secrets handling

- Compute credentials live only in platform secret stores (Kaggle/Colab secrets, CI secrets).
- The website is a static site and needs no secrets. Never put a secret in a `NEXT_PUBLIC_*` variable: such variables are embedded in the public JavaScript bundle.

## Reporting a vulnerability or accidental exposure

Do **not** open a public issue. Contact the project owner privately (see `CITATION.cff`) with:

1. what was exposed (file, commit, URL);
2. when it was noticed.

If data or a credential was committed, the owner will:

1. revoke or rotate the credential immediately;
2. remove the file and purge it from the git history;
3. notify the data provider where the data-use terms require it.

Deleting the file in a new commit is **not** enough: it remains in the history.
