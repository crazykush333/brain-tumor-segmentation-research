# 06 — Baseline Strategy

Principle: baselines are chosen because a reviewer would reasonably ask for them, not because they are easy [B2]. Every third-party implementation is used at a pinned commit, with its licence recorded in `docs/ASSET_PROVENANCE.md` / `THIRD_PARTY_NOTICES` before use.

Licence entries marked "?" **must be checked on the repository before any code is copied or vendored.**

## 1. Segmentation baselines

| Baseline | Why relevant | Source | Reference | Compute [ESTIMATE] | Fairness requirements | Licence |
|---|---|---|---|---|---|---|
| **nnU-Net v2, 3d_fullres, full input** | The strongest widely-available baseline [B1, B2]; the BraTS reference point | github.com/MIC-DKFZ/nnUNet | [B1] | High (multi-session on T4/P100) | Same splits via a custom `splits_final.json`; fingerprint from TRAIN only | Apache-2.0 ? |
| **nnU-Net v2 + modality (channel) dropout** | Simple missing-modality baseline, externally validated [C7, C8] | nnU-Net + custom trainer (our code, small) | [C7, C8] | Same as above | Identical schedule to the full-input arm; dropout-probability policy pre-registered | ours + Apache-2.0 |
| **Per-subset nnU-Net** (selected subsets) | "Train on what you have" upper reference [C6] | nnU-Net | [C6] | 15× training if all subsets; use only a pre-registered subset (e.g. −T1c, −FLAIR, T1c+FLAIR) | Same schedule | Apache-2.0 ? |
| **MONAI SegResNet** | Lightweight fallback and pilot; BraTS-proven | MONAI | Myronenko 2018 (BrainLes) [R] | Moderate | Same preprocessing | Apache-2.0 |
| **Swin UNETR** (only if a direction needs a transformer reference) | Commonly requested by reviewers | MONAI | [B3] | High | Same budget | Apache-2.0 |
| **Specialized missing-modality models** (Direction 2): RFNet, mmFormer, M3AE, ShaSpec — final list by code availability | The methods under test | Official repos (to locate and pin) | [C2–C5] | High, per method | Published recipe **and** a matched-budget arm; our preprocessing and splits; sanity-reproduce a published internal number first | ? each |

## 2. Uncertainty / reliability baselines

| Method | Why | Cost |
|---|---|---|
| Softmax entropy / max-prob (single model) | Zero-cost reference | 1 forward pass |
| MC-dropout (T passes) | Standard [D12]; cheap alternative in [D2] | T× inference; needs dropout in the network (nnU-Net default has none, so this is an architectural change that must be documented) |
| Deep ensemble (seeds as members, M = 3; M = 5 if affordable) | Best-performing in [D2] | M× training (reuses seed runs) |
| Test-time augmentation (flips) | Common and cheap | ~8× inference |
| Temperature scaling (fit on validation) | Standard post-hoc calibration [D12] | Negligible |
| Aggregation: mean / ROI-mean / pairwise-DSC | [D2] | Negligible given the ensemble |
| Learned QC regressor (Direction 3) | [D4] | Moderate; simple re-implementation |

## 3. TTA baselines (Direction 5)

No adaptation; normalization-statistics re-estimation; TENT-style entropy minimization [E5]; augmentation-consistency. SmaRT [E1] if code and licence permit.

## 4. Fairness checklist (applies to every comparison)

- [ ] identical patient splits and preprocessing
- [ ] identical epoch/iteration budget, or both published and matched budgets reported
- [ ] identical post-processing (or none)
- [ ] identical inference (sliding window, overlap, TTA on/off)
- [ ] hyperparameters tuned on VALIDATION only, with equal tuning effort per arm (logged)
- [ ] the same number of seeds per arm
- [ ] third-party code: pinned commit, unmodified except documented adapters
