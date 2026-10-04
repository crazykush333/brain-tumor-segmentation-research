# Case-level reliability of glioma segmentation under missing MRI sequences

> **Status: Protocol v1.0 frozen. Experimental execution pending.**

A pre-registered, reproducible research pipeline for case-level uncertainty estimation under missing MRI sequences in brain tumour segmentation.

**REAL EXPERIMENT STATUS: pending official data acquisition and suitable GPU execution.** No BraTS data have been acquired, no model has been trained, no split has been created and no scientific result exists.

[![CI](https://github.com/crazykush333/brain-tumor-segmentation-research/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/crazykush333/brain-tumor-segmentation-research/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](pyproject.toml)
[![License](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)
[![Protocol](https://img.shields.io/badge/protocol-v1.0%20frozen-blue)](docs/research/FINAL_RESEARCH_PROTOCOL_v1.0.md)

## Research question

> Among cases with the same missing MRI sequence, can ensemble disagreement identify which enhancing-tumour segmentations are likely to fail — and does that signal, with its operating threshold, transfer to a held-out institution and an external population?

## Motivation

Clinical MRI protocols are often incomplete: a contrast-enhanced T1, T2 or FLAIR sequence may be missing or unusable. Segmentation networks can be trained to tolerate missing inputs, but deploying them safely also requires knowing *which individual cases* to trust. The identity of the missing sequence already tells us that some conditions are harder than others; this study asks whether model uncertainty adds information **within** a fixed missing-sequence condition, where knowing the condition alone cannot help, and whether the result holds outside the development population.

## Frozen protocol

The authoritative definition of the study is **[docs/research/FINAL_RESEARCH_PROTOCOL_v1.0.md](docs/research/FINAL_RESEARCH_PROTOCOL_v1.0.md)** — frozen 2026-09-28 (`protocol-v1.0`), SHA-256 `704c0b495917344f44b93e7548ade0e32a71220265419516a2c83d626fcd9811`, verified by `brats-uncertainty verify-protocol` and the regression tests. Changes are possible only through logged amendments; the one amendment so far (v1.0-A1) concerns the data route and changes no part of the scientific design.

**Primary hypothesis (H-W).** On the internal test set, for the modality-dropout (arm B) ensemble, the equal-weight mean over the four single-missing conditions C4 = {−T1, −T1c, −T2, −FLAIR} of the within-condition ET ΔAURC_c = AURC_c(U1) − AURC_c(I) is below 0 (risk = 1 − ET Dice). H-W is supported if the patient-group bootstrap 95% CI lies entirely below 0.

## Experimental design

| Element | Design |
|---|---|
| Arms | A: standard nnU-Net training; B: modality-dropout training (primary) |
| Conditions | C5 = {Full, −T1, −T1c, −T2, −FLAIR}; C4 (single-missing) is the primary estimand; Full is a control; C15 (all 15 subsets) secondary |
| Missingness | the normalized channel of a missing sequence is set to 0 (training and inference) |
| Uncertainty | U1 = mean pairwise Dice of the 3 ensemble members (primary); U2/U3 secondary/exploratory |
| Baseline | I = missingness indicator (constant within a condition = random ranking) |
| Endpoint | mean within-condition ET ΔAURC over C4; AURC with expected tie handling |
| Statistics | patient-group bootstrap, 10,000 replicates (seed 12345); Holm within secondary families F1–F4; F5 descriptive |
| Threshold transfer | τ_q fixed on validation C4 units, applied unchanged to internal test, UPenn and BraTS-Africa |
| Stopping rules | SR1–SR8 (compute, sanity, data, integrity, bugs, budget, licensing, platform) |

## Architecture

- **Models:** nnU-Net v2, 3d_fullres, region-based (WT/TC/ET), 250 epochs (150 only if SR1/SR6 require), seeds 0, 1, 2 per arm; 3-member mean ensembles; sliding window step 0.5, mirroring off, threshold 0.5.
- **Package** (`src/brats_uncertainty`): data gates and manifests (`data/`), patient grouping and split (`grouping/`, `splitting/`), metrics and uncertainty (`metrics/`, `uncertainty/`), statistics (`statistics/`), evaluation pipeline (`study/`), compute probe and resumable jobs (`compute/`), master orchestration (`orchestration/`), research-gate guards (`evaluation/`), provenance-stamped results and website export (`results/`).

## Dataset roles

| Role | Dataset | n |
|---|---|---|
| Development (train / validation / internal test, 70/10/20 by patient group) | BraTS 2021 training cases not from site 1 | 740 cases before grouping |
| Held-out institution | UPenn-origin BraTS 2021 cases (site 1) | 511 |
| External population | TCIA BraTS-Africa glioma cases | ≤ 95 (frozen at gate C3) |

Data are obtained only from the official providers through the approved route; see [Data policy](#data-policy).

## Reproducibility

- **One master entry point:** `python scripts/remote/master_run.py --resume --commit --push` (wrappers `scripts/remote/run_all.sh` / `.ps1`) runs every permitted step in protocol order and stops only at a genuine blocker with the exact gate, blocker and action.
- **Gates:** B1–B12 (data, grouping, split), D1–D6 (compute pilot), C1–C6 (pre-external evaluation); each needs committed evidence; failed gates are never reopened automatically.
- **Resume:** crashed sessions resume from verified state; completed work is never re-run; failed steps need an explicit `--retry`.
- **Provenance:** every record and artifact carries the git commit, protocol hash, config and input hashes.
- **Safe export:** only public-safe file types; imaging, checkpoints, licensed metadata and demo files are refused.
- **Evaluation integrity:** test and external sets are evaluated once, from the `eval-v1` tag, with an append-only ledger (SR4).

Details: [docs/reproducibility/](docs/reproducibility/REPRODUCIBILITY.md), [REMOTE_COMPUTE.md](docs/reproducibility/REMOTE_COMPUTE.md).

## Repository structure

```
.github/        CI (tests, lint, types, package build) and website build
configs/        protocol mirror, datasets, compute, experiments, evaluation
data/           README only — raw data are never stored in Git
docs/           frozen protocol, amendments, data and gate records, status, reproducibility
experiments/    experiment metadata; launcher notebooks (experiments/kaggle, experiments/vm)
results/        real-result status (status.json) and the synthetic demonstration (demo/)
scripts/        thin gated entry points, including the master runner
splits/         README only until the real split is created (IDs and hashes only)
src/            the brats_uncertainty package
tests/          unit, integration and regression tests (synthetic fixtures only)
website/        Next.js research website (static export)
```

## Execution workflow

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"                                # add ".[io,nnunet]" on the GPU machine
brats-uncertainty verify-protocol
brats-uncertainty master-run --plan --work-dir /data/brats_work    # show every step's status
export BRATS_WORK=/data/brats_work BRATS_OFFICIAL_DELIVERY=/data/delivery
bash scripts/remote/run_all.sh                         # run / resume the whole study
```

## Current research status

| Item | Status |
|---|---|
| Research protocol | ✅ Frozen (v1.0) |
| Execution engine and tests | ✅ Implemented, passing (synthetic fixtures) |
| Data route (B1), EXP-001 authorization (D1, D2) | ✅ Approved / closed |
| Official BraTS data (B2) | ⏳ Pending |
| GPU execution, compute pilot (D3–D6) | ⏳ Pending |
| Main training, validation | ⏳ Pending |
| Internal and external evaluation | ⏳ Pending |
| Scientific results | ⏳ Not available |

Full table: [docs/research/STATUS.md](docs/research/STATUS.md). Machine-readable state: [docs/project_status.yaml](docs/project_status.yaml).

## Data policy

Raw BraTS data are **not** stored in Git. Official data are acquired separately through the route approved at gate B1 as an **owner-approved alternative** (direct official TCIA access into a private, access-restricted computational environment; amendment v1.0-A1; no external TCIA authorization is claimed) and remain in private execution storage. Gate B2 is authorized but not executed: no data have been acquired. Patient imaging, masks, predictions, checkpoints, licensed metadata and credentials are never committed; manifests contain only permitted IDs, hashes and provenance. `brats-uncertainty check-repo` enforces this in CI. See [data/README.md](data/README.md) and [docs/data/DATA_ACCESS.md](docs/data/DATA_ACCESS.md).

## Results

### Current status

**Real BraTS scientific results: NOT YET AVAILABLE.** [`results/status.json`](results/status.json) reports `scientific_results_available: false`.

### Demonstration

A **synthetic** end-to-end demonstration shows how the result pipeline, statistics, figures and website will look once the real study is executed: [`results/demo/`](results/demo/). It is generated from deterministic synthetic toy volumes by the study's own code, every file is labelled `demo=true / synthetic=true / scientific_result=false`, and it is **not** a BraTS result and says nothing about the hypotheses.

## Website

The research website (`website/`, Next.js static export) presents the question, design, reproducibility system, live gate status and the results page (real-results status plus the clearly labelled synthetic demonstration). All content is generated from the repository's sources of truth (`brats-uncertainty export-site-data`).

## Citation

Cite the software via [CITATION.cff](CITATION.cff). No paper or scientific result exists yet. The development history of this project is preserved in an archival repository; see [docs/research/ARCHIVAL_PROVENANCE.md](docs/research/ARCHIVAL_PROVENANCE.md).

## License

Code: [Apache-2.0](LICENSE) (the licence choice is recorded as pending owner confirmation in docs/research/08 §2). Dataset licences are separate and are those of the providers (BraTS 2021 / TCIA: CC BY 4.0 and the TCIA Data Usage Policy; BraTS-Africa processed release: CC BY 4.0).

[Contributing](CONTRIBUTING.md) · [Code of conduct](CODE_OF_CONDUCT.md) · [Security](SECURITY.md)
