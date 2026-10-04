# 01 — Research Landscape (2022–2026)

Status: research-design phase. Every factual claim below is backed by an entry in [09_LITERATURE_MATRIX.md](09_LITERATURE_MATRIX.md), cited by its matrix ID (e.g. **[C7]**). This document contains no experimental results from this project.

## 1. Scope and method of the review

- Sources were arXiv, PubMed/PMC, MICCAI open-access pages, publisher pages (RSNA, Nature, Elsevier, Springer, Oxford), TCIA and Synapse, searched on 2026-09-27. Emphasis was on 2024–2026.
- **Limitation:** this is a *targeted* review done in one session, not a systematic review (no PRISMA protocol). It is sufficient to identify saturated areas and candidate gaps. It is **not** sufficient to support a manuscript novelty claim. A structured search (Section 5 of [11_NOVELTY_RISK_ASSESSMENT.md](11_NOVELTY_RISK_ASSESSMENT.md)) is required before the second approval gate.

## 2. Landscape by topic

Each topic is marked as **Saturated** (S), **Active/crowded** (A) or **Under-explored** (U). This is a qualitative judgement from the evidence cited, not a score.

| Topic | State | Evidence and comment |
|---|---|---|
| A–B. BraTS segmentation accuracy (pre-op adult glioma) | **S** | Challenge winners since 2021 are ensembles of nnU-Net, Swin UNETR and similar models, plus data work [B8]. Isensee et al. show new-architecture claims often fail fair comparison [B2]. |
| C. Multimodal MRI fusion | **S/A** | Most missing-modality papers are fusion designs [C1–C11]. |
| D. Missing-modality segmentation (accuracy) | **S** | ≥10 new architectures in 2024–2026 [C11], almost all on BraTS 2018/2020 internal splits, Dice only. Simple nnU-Net per-subset training or channel dropout performs strongly, even externally [C6, C7, C8]. |
| D′. Missing modality × reliability (calibration, failure detection) | **U (narrowing)** | The closest works are [C9] (variance as missing-evidence uncertainty, internal only) and [C10] (uncertainty-gated fusion for missing T1c). No systematic *failure-detection / calibration* evaluation under missing sequences was found (search limitation applies). |
| E–H. Domain generalization / adaptation / scanner shift | **A** | BraTS-Africa adaptation is crowded [E3]. The TTA benchmark shows fragility under inter-center shift [E2]. Federated learning is covered at scale by FeTS [E4]. |
| G/Z. Cross-dataset / external validation | **U in method papers, A in clinical papers** | Clinical-style external validations exist [C7, C8, D8], but most method papers validate only internally [C1–C5, C9]. The field-wide overlap between BraTS 2021/2023, UCSF-PDGM and UPenn-GBM means some "external" tests are not external [A6, A7, C10]. |
| I–J. Uncertainty quantification and calibration | **S (generic), A (applied)** | QU-BraTS [D1], Mehrtash [D5] and Jungo [D6] are established. Generic "MC-dropout on BraTS" is saturated. |
| K–L. Selective prediction and failure detection | **A** | Zenk et al. provide a strong benchmark and AURC protocol [D2]. Spatial aggregation is covered at CVPR 2026 [D3]. Learned QC with BraTS-SSA as an external set exists [D4]. |
| M. OOD detection | **A** | It is part of [D2, D3]. OOD ≠ failure detection [D2]. |
| N. Robust segmentation (corruptions, artefacts) | **A** | FeTS corruptions in [D2]. |
| O. Efficient segmentation | **A** | Architecture/efficiency benchmarks on BraTS 2023/2024 exist [B7]. |
| P–R. CNN / Transformer / Mamba | **S** | See [B2–B7]. |
| S. Foundation models | **A** | BrainSegFounder [F1], MedSAM [F2], BrainDINO/Triad [F3]. Heavy compute. |
| T. Knowledge distillation | **S within missing-modality** | Used in [C11] (e.g. "No Modality Left Behind", "Mind the Gap"). |
| U. Modality fusion | **S** | See C / D. |
| V–W. Federated learning / privacy | **A** | FeTS [E4]. Compute/infrastructure is hard to reproduce on free GPUs. |
| X. Explainability | **A** | Not reviewed in depth. Weak link to a testable segmentation hypothesis in our setting. |
| Y. Reproducibility | **U (as a contribution)** | [B2] shows the need. Inconsistent BraTS 2018 splits across missing-modality papers [C-common] are a concrete reproducibility problem. |
| AA. Clinically meaningful evaluation | **A** | Metrics Reloaded [D11], Kofler [D10], lesion-wise BraTS metrics [B8], and volume bias in [C7]. |
| Post-treatment glioma | **A (new)** | BraTS 2024 [A4] and MU-Glioma-Post [A11]. Label schema differs from pre-op. |

## 3. Saturated areas (and why)

1. **Basic 3D U-Net improvements.** nnU-Net's self-configuration already captures most of the gain available from architecture tweaks. Isensee et al. 2024 [B2] document that many claimed improvements are due to weak baselines.
2. **Generic attention or transformer modules.** Swin UNETR, SegMamba and many successors [B3–B7] are all evaluated on BraTS. Adding a module to a U-Net is not a research question and is unlikely to beat a tuned nnU-Net reliably [B2].
3. **Mamba / state-space backbones.** Several 2024–2026 variants exist [B5–B7], and [B2] includes Mamba baselines that do not outperform CNNs.
4. **Simple missing-modality training.** HeMIS → RFNet → mmFormer → M3AE → ShaSpec → a 2024–2026 wave [C1–C11]. Channel dropout plus nnU-Net is already validated externally [C7] and on real-world missingness [C8]. **Accuracy under missing modality is saturated.**
5. **Generic modality dropout.** It is the baseline in [C6, C7, C8] and not a contribution by itself.
6. **Generic uncertainty estimation on BraTS.** QU-BraTS 2020 [D1] and a long MC-dropout/ensemble literature [D5, D6, D12] already cover it.
7. **BraTS-Africa accuracy adaptation.** There are at least five 2024–2025 papers plus a challenge [E3].
8. **Arbitrary combinations** (e.g. "Mamba + missing modality + uncertainty"). Such combinations satisfy "nobody combined X and Y", which the project brief explicitly rejects as a gap.

## 4. Methodological weaknesses observed across the literature

These are recurring issues, each with a cited example. They are not claims about any single paper beyond what is cited.

- **W1. Weak baselines.** Specialized missing-modality architectures rarely compare against per-subset nnU-Net [C6] or dropout nnU-Net [C7].
- **W2. Inconsistent splits.** BraTS 2018 splits differ across missing-modality papers (e.g. 199/29/57 vs 80/20, per [C-common]), so numbers across papers are not comparable.
- **W3. Internal-only validation.** This applies to most missing-modality and architecture papers.
- **W4. Pseudo-external validation.** Transfer between BraTS versions or overlapping TCIA cohorts is sometimes presented as cross-dataset [C10; A6/A7 leakage warnings].
- **W5. Single-run reporting.** Seed variance and confidence intervals are rarely reported. This is to be confirmed per paper in the full-text review.
- **W6. Accuracy-only evaluation.** Calibration and failure detection are rarely evaluated when inputs are incomplete [D′ row].
- **W7. Metric/clinical mismatch.** Dice is not aligned with expert preference [D10]. Volume bias is clinically relevant [C7].

## 5. What this implies

Contributions most likely to be defensible are **not** new architectures. They are:

(a) rigorous, well-controlled *evaluation* questions with external data;
(b) *reliability* questions (does the model know when it is wrong?) under realistic clinical conditions — missing sequences, site shift, post-treatment anatomy — where the literature is thinner;
(c) small, well-motivated methods only if (a) or (b) exposes a specific failure that they target.

This is an observation about the literature. **It is not a recommendation of a direction.** See [03_PROJECT_OPTIONS.md](03_PROJECT_OPTIONS.md).
