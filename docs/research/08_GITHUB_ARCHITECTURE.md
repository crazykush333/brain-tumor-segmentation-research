# 08 — GitHub / Repository Architecture (planned)

**Nothing below exists yet except `docs/` and `README.md`.** It is built incrementally at milestones 1–15 ([10](10_RESEARCH_ROADMAP.md)). Nothing is pushed to GitHub without explicit approval.

## 1. Proposed structure

The brief's structure is kept, with a few justified changes, each marked ➕ or ✎:

```
BRATS-Research/
├── README.md, LICENSE, CITATION.cff, CONTRIBUTING.md, CODE_OF_CONDUCT.md,
│   SECURITY.md, CHANGELOG.md
├── THIRD_PARTY_NOTICES.md                ➕ licences of nnU-Net/MONAI/other code
├── pyproject.toml                         (single source of dependencies)
├── requirements.txt / environment.yml     (generated/pinned from pyproject)
├── Dockerfile                             (CPU image for tests; GPU image optional)
├── .gitignore, .github/workflows/ci.yml
├── configs/
│   ├── data/                              ➕ dataset paths are env-var based, no hard-coded paths
│   ├── baseline/  proposed/  ablations/
│   └── experiments/EXP-xxx.yaml           ➕ one file per registered experiment
├── splits/                                ➕ patient-ID lists only (no images), dedup lists
├── src/brats_research/
│   ├── data/            (loaders, modality order, label mapping)
│   ├── preprocessing/
│   ├── missingness/     ➕ subset generation / channel masking (if D1/D2)
│   ├── models/          (thin adapters around nnU-Net/MONAI, no re-implementation)
│   ├── training/        (nnU-Net custom trainer for dropout; resume logic)
│   ├── evaluation/      (Dice, HD95, NSD, lesion-wise, volume)
│   ├── uncertainty/     (MC-drop, ensemble, TTA, aggregation, calibration)
│   ├── robustness/
│   ├── stats/           ➕ paired tests, bootstrap, Holm, TOST
│   ├── inference/
│   ├── tracking/        ➕ experiment ID, git hash, environment capture
│   └── visualization/
├── scripts/  prepare_data.py, dedup_external.py ➕, train.py, evaluate.py,
│             infer.py, analyze_stats.py ➕, generate_figures.py
├── tests/    (synthetic volumes only; no dataset needed)
├── kaggle/README.md, kaggle/training/   colab/README.md, colab/training/
├── docs/     research/ methodology/ experiments/ reproducibility/ ASSET_PROVENANCE.md
├── results/  EXP-xxx/ {config.yaml, metrics.json, per_case.csv, training_log.json,
│             environment.json}   (small text files committed; predictions NOT committed)
├── figures/  (generated only by scripts, from results/)
├── assets/   architecture/ pipeline/  (diagrams made for this project)
└── paper/    manuscript/ figures/ tables/ supplementary/
```

## 2. Key decisions (to confirm at Milestone 1)

- **Code licence.** Candidates are Apache-2.0 (patent grant; compatible with nnU-Net and MONAI, which are believed to be Apache-2.0 — to verify) and MIT. Decision deferred to the owner. Either licence covers **code only**; data licences are separate.
- **Dependencies:** Python 3.10–3.12 (3.13 support in PyTorch/nnU-Net to verify), PyTorch, MONAI, nnU-Net v2, NiBabel, NumPy, SciPy, pandas, scikit-learn, Matplotlib. Tracking uses CSV/JSON files plus optional TensorBoard. No W&B/MLflow unless needed: they add accounts and dependencies.
- **Tooling:** pytest, ruff (lint and format), mypy on `src/` (lenient), pre-commit.
- **CI (GitHub Actions, CPU only):**
  1. install
  2. `ruff check`
  3. `pytest` on synthetic data
  4. validate all `configs/**/*.yaml` against a schema
  5. `python -c "import brats_research"`

  No GPU and no dataset are used in CI.
- **Large files:** checkpoints are *not* committed. If shared, they go to a release asset or Zenodo/Hugging Face with a model card, and only if the data licence permits distributing trained weights (to verify for BraTS).
- **Badges:** only for things that exist and pass (Python version, licence, CI status).

## 3. Result integrity mechanics

- `results/EXP-xxx/` is written only by `scripts/evaluate.py`, which records the git commit, a config hash and the environment.
- Figures are regenerated from `results/` by `scripts/generate_figures.py`. Each figure's caption file lists the source EXP IDs.
- A CI check fails if any figure lacks a provenance entry.
- README results tables are generated from `results/` and never hand-typed.
