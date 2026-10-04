# 09 — Literature Matrix

Status: **working draft, research-design phase.** No experiments in this repository have been run.

## How to read this matrix

**Verification tag** (on every entry):

- **[V]**: bibliographic details and the summarized claim were checked against the arXiv, PubMed, publisher or dataset page on 2026-09-27. The URL is given.
- **[R]**: recalled from prior knowledge of the field. The citation is very likely correct, but DOI, venue and author list **must be checked before the entry goes into a manuscript**. Numbers are not quoted for [R] entries.

**Result tags.** Every number below is a **[LITERATURE RESULT]**: it is what the cited authors report, taken from the abstract or dataset page. It is not a result of this project. Numbers from different papers are **not comparable** with each other: splits, dataset versions, metrics (voxel-wise vs lesion-wise) and post-processing differ.

**Blank fields.** "n/r" means not reported in the abstract or landing page we checked, not that the paper lacks it. The full text has to be read before a manuscript claim relies on an n/r field.

Fields that do not apply to a paper type (e.g. "architecture" for a dataset paper) are left out of that entry.

---

## A. Datasets and challenge papers

### A1. The RSNA-ASNR-MICCAI BraTS 2021 Benchmark on Brain Tumor Segmentation and Radiogenomic Classification [V]
- Authors / year / venue: Baid U. et al., 2021, arXiv:2107.02314
- URL: https://arxiv.org/abs/2107.02314 ; TCIA: https://wiki.cancerimagingarchive.net/display/DOI/RSNA-ASNR-MICCAI-BraTS-2021 (DOI 10.7937/jc8x-9874)
- Data: pre-operative adult glioma mpMRI (T1, T1c, T2, FLAIR), multi-institutional. The challenge covers 2,040 patients; the TCIA collection lists 1,480. Labels are necrotic/non-enhancing core, edema and enhancing tumour, evaluated as the ET/TC/WT regions.
- Access: Synapse (challenge) and TCIA, which requires a signed **TCIA Restricted License Agreement** because images could allow face reconstruction. The collection is described as CC BY-licensed contributions.
- Relevance: the de facto large source domain. It overlaps with UCSF-PDGM and UPenn-GBM (see A6, A7), and **that overlap must be removed** before either is used as an external test set.

### A2. The Multimodal Brain Tumor Image Segmentation Benchmark (BRATS) [R]
- Menze B. et al., IEEE TMI 2015. Foundational benchmark paper, cited as a BraTS data-use requirement.

### A3. Advancing the Cancer Genome Atlas glioma MRI collections with expert segmentation labels and radiomic features [R]
- Bakas S. et al., Scientific Data 2017. Standard citation required by BraTS data-use terms.

### A4. The 2024 BraTS Challenge: Glioma Segmentation on Post-treatment MRI [V]
- de Verdier M. C. et al. (first author per arXiv listing; verify), 2024, arXiv:2405.18368. https://arxiv.org/abs/2405.18368
- Labels: enhancing tissue (ET), surrounding non-enhancing FLAIR hyperintensity (SNFH), non-enhancing tumor core (NETC), and **resection cavity (RC)**.
- Relevance: a natural **clinical-shift** test (pre-op → post-treatment). Its label schema differs from the pre-op schema, so a label-harmonization protocol is required.

### A5. The BraTS-Africa Dataset: Expanding the Brain Tumor Segmentation Data to Capture African Populations [V]
- Adewole M. et al., Radiology: Artificial Intelligence 2025; 7(4): e240528. DOI 10.1148/ryai.240528. Challenge description: arXiv:2305.19369.
- Data: 146 adult patients with pre-operative brain tumours, from institutions in Nigeria. Per secondary reports, acquisition includes lower-field scanners and heterogeneous protocols.
- Licence: **CC BY 4.0**, hosted on TCIA and Synapse.
- Reported shift [LITERATURE RESULT, secondary source]: one follow-up paper reports roughly a 20% reduction in mean Dice when BraTS-2021-trained models are applied to BraTS-Africa validation cases (see arXiv:2412.14100). The primary figure must be verified in the full text.
- Relevance: the strongest publicly available **acquisition/population-shift** external test set for adult glioma.

### A6. The University of California San Francisco Preoperative Diffuse Glioma MRI Dataset (UCSF-PDGM) [V]
- Calabrese E. et al., Radiology: AI 2022. DOI 10.1148/ryai.220058. TCIA collection.
- Data: 501 adult diffuse glioma patients, pre-operative, 3T, standardized protocol that includes advanced sequences.
- **Leakage warning:** TCIA provides a BraTS-2021 ID mapping so that overlapping cases can be excluded. One secondary report excluded 298 duplicates (to verify against the TCIA spreadsheet).

### A7. The University of Pennsylvania Glioblastoma (UPenn-GBM) cohort [V]
- Bakas S. et al., Scientific Data 9:453 (2022). DOI 10.1038/s41597-022-01560-7.
- Data: 630 de novo GBM patients with structural, DSC/DTI and clinical/genomic data. Licence CC BY 4.0 (TCIA).
- **Label provenance must be verified.** Our current understanding is that part of the segmentations are automated and part manually revised, but the exact split has not been confirmed. Only manually-revised cases should be used as a strict external test.
- **Leakage warning:** it overlaps with BraTS. Öchsner et al. 2026 (C7) used it as external validation, so there is precedent for the de-duplication procedure.

### A8. The Erasmus Glioma Database (EGD) [V]
- van der Voort S. R. et al., Data in Brief 2021. PubMed 34159239.
- Data: 774 pre-op glioma patients (T1, T1c, T2, FLAIR). **Whole-tumour labels only**: 374 manual, 400 automatic.
- Access: data usage agreement via Health-RI.
- Relevance: an external WT-only test, from a European multi-scanner single-center. Sub-region metrics are not possible.

### A9. The LUMIERE dataset: Longitudinal Glioblastoma MRI with expert RANO evaluation [V]
- Suter Y. et al., Scientific Data 2022. DOI 10.1038/s41597-022-01881-7.
- Data: 91 GBM patients, 638 study dates, RANO ratings. Segmentations are **automated** (not manual ground truth).
- Relevance: limited for segmentation evaluation, possible for downstream/RANO-consistency analysis.

### A10. RHUH-GBM [V]
- Cepeda S. et al., 2023 (arXiv:2305.00005; Scientific Data, verify).
- Data: 40 patients, pre-op, early post-op and recurrence. Sub-region labels reviewed by two neurosurgeons.
- Relevance: a small external test that includes post-op timepoints.

### A11. MU-Glioma-Post [V]
- Scientific Data 2025 (PubMed 41266380). Post-treatment glioma, multi-sequence. Linked by secondary sources to the BraTS 2024 post-treatment data.
- **Case count and label provenance (automated vs expert) to be verified**: the title says "automated MR multi-sequence segmentation".

### A12. BraSyn — Brain MR Image Synthesis for Tumor Segmentation (BraTS 2023/2024) [V]
- Li H. B. et al., arXiv:2305.09011. PubMed 37608932.
- Relevance: an official BraTS task on **missing sequences**, which confirms clinical motivation. Synthesis is one of the established solution families.

### A13. BraTS-PEDs 2023 [V] and BraTS 2023 Meningioma [V]
- arXiv:2305.17033 / 2407.08855 (PEDs); arXiv:2405.09787 (MEN).
- Relevance: different tumour types. They could serve as **far-OOD** inputs for failure/OOD detection, **not** as glioma external validation.

### A14. BraTS-Lighthouse 2025 [V]
- Synapse: https://www.synapse.org/brats2025. METS analysis: arXiv:2504.12527.
- Relevance: current challenge umbrella. Task definitions and data access terms must be checked on Synapse before any use.

---

## B. Architectures and training frameworks

### B1. nnU-Net: a self-configuring method for deep learning-based biomedical image segmentation [R]
- Isensee F. et al., Nature Methods 2021. Code: github.com/MIC-DKFZ/nnUNet (Apache-2.0; verify).
- Relevance: the mandatory strong baseline.

### B2. nnU-Net Revisited: A Call for Rigorous Validation in 3D Medical Image Segmentation [V]
- Isensee F., Wald T., Ulrich C., Baumgartner M., Roy S., Maier-Hein K., Jäger P., MICCAI 2024, pp. 488–498. arXiv:2404.09556.
- Claim [LITERATURE RESULT]: many recent architecture claims do not survive fair baselines. CNN U-Nets (ResNet/ConvNeXt variants) in the nnU-Net framework, scaled to the hardware, remain the recipe for state-of-the-art performance. Transformer and Mamba methods were benchmarked.
- Relevance: **core evidence that "new architecture" is a saturated contribution.**

### B3. Swin UNETR [R]
- Hatamizadeh A. et al., BrainLes (MICCAI workshop) 2021/2022, arXiv:2201.01266. MONAI implementation (Apache-2.0).

### B4. MedNeXt [R]
- Roy S. et al., MICCAI 2023. A ConvNeXt-style 3D segmentation network.

### B5. SegMamba [V]
- Xing Z. et al., MICCAI 2024. Evaluated on BraTS 2023 among others. https://papers.miccai.org/miccai-2024/676-Paper0663.html

### B6. U-Mamba [R]
- Ma J. et al., arXiv:2401.04722, 2024.

### B7. A Unified Benchmark of Deep Learning Models for Multi-task 3D Brain Tumor Segmentation from MRI [V]
- Torrejón D. J., Hernández L. Y., Sánchez J., arXiv:2607.28858 (July 2026).
- Compares 3D U-Net, SegResNet, Swin UNETR, SegMamba and SegMambaV2 on BraTS 2023 MEN and BraTS 2024 post-treatment glioma, looking at the accuracy/efficiency trade-off. Code n/r.
- Relevance: shows that architecture benchmarking on recent BraTS is already happening.

### B8. How we won BraTS 2023 Adult Glioma challenge? Just faking it! [V]
- Ferreira A. et al., arXiv:2402.17317.
- Method: GAN/registration-based augmentation with an ensemble of nnU-Net, Swin UNETR and the BraTS 2021 winner, evaluated with lesion-wise metrics.
- Relevance: shows challenge winners are ensembles of standard models plus data work, not novel architectures.

---

## C. Missing-modality segmentation

### C1. HeMIS: Hetero-Modal Image Segmentation [R]
- Havaei M. et al., MICCAI 2016. Earliest widely cited arbitrary-subset method.

### C2. RFNet: Region-aware Fusion Network for Incomplete Multi-modal Brain Tumor Segmentation [R]
- Ding Y., Yu X., Yang Y., ICCV 2021.

### C3. mmFormer: Multimodal Medical Transformer for Incomplete Multimodal Learning of Brain Tumor Segmentation [R]
- Zhang Y. et al., MICCAI 2022.

### C4. M3AE: Multimodal Representation Learning for Brain Tumor Segmentation with Missing Modalities [R]
- Liu H. et al., AAAI 2023.

### C5. ShaSpec: Multi-modal Learning with Missing Modality via Shared-Specific Feature Modelling [R]
- Wang H. et al., CVPR 2023.

**Common protocol across C1–C5 and most successors (C8–C12):** BraTS 2018 and/or 2020 training data, random internal splits (e.g. 199/29/57 for BraTS 2018, per one report — splits are inconsistent across papers), all 15 modality subsets simulated by zeroing channels, Dice only, single run, no external test, no calibration.

### C6. Brain tumour segmentation with incomplete imaging data [V]
- Ruffle J. K., Mohinta S., Gray R., Hyare H., Nachev P., Brain Communications 2023; 5(2): fcad118. DOI 10.1093/braincomms/fcad118. Code: github.com/high-dimensional/tumour-seg
- Design: nnU-Net-derived models trained for **every** sequence combination, with 5-fold CV on BraTS 2021 (1,251 patients).
- Finding [LITERATURE RESULT]: models with incomplete sequence sets still characterized tumours well.
- Relevance: a **strong, simple baseline** that specialized missing-modality methods often do not compare against.

### C7. Robust Glioblastoma Segmentation and Volumetry Without T2-FLAIR: External Validation of Targeted Dropout Training [V]
- Öchsner M. et al., arXiv:2602.20218 (v3 April 2026).
- Data: train on BraTS 2021 (n=848), **external test on UPenn GBM (n=403)**.
- Method: 3D nnU-Net with targeted FLAIR channel dropout.
- Reported [LITERATURE RESULT]:
  - Without FLAIR, whole-tumour DSC was 60.4% with standard training and 92.6% with dropout training.
  - With the full protocol, overall median DSC was 94.8% (dropout) vs 95.0% (standard).
- Relevance: **strong evidence that simple modality dropout plus nnU-Net already solves single-sequence absence well, including externally.** This raises the bar for any missing-modality accuracy claim.

### C8. Multi-class glioma segmentation on real-world data with missing MRI sequences: comparison of three deep learning algorithms [V]
- Pemberton H. G. et al., Scientific Reports 2023; 13:18911. PubMed 37919354.
- Data: trained on BraTS 2021, with an external real-world test set (158 GBM + 69 LGG).
- Reported [LITERATURE RESULT]: nnU-Net was best of DeepMedic, nnU-Net and NVIDIA-net (DSC 0.86 internal, 0.93 external). With "sparsified training", missing sequences did not statistically affect performance.
- Relevance: real-world missingness plus external validation already exist for **accuracy**.

### C9. Set-Inclusive Uncertainty Modeling for Robust Brain Tumor Segmentation [V]
- Baek S. et al., arXiv:2606.30374 (June 2026). Data: BraTS 2018/2020.
- Method: Gaussian feature representations whose variance measures "uncertainty from missing evidence", with hierarchical subset constraints.
- Relevance: **the closest existing work to "uncertainty under missing modalities".** It is a novelty risk for Direction 1. It appears to evaluate on internal BraTS 2018/2020 only; calibration/failure-detection evaluation and external data need checking in the full text.

### C10. Uncertainty-aware feature mapping and adaptive inference for brain tumor segmentation with missing contrast-enhanced T1-weighted imaging (UAF-AIMM) [V]
- Liu W., Zhang Z., Deng F., Xiao Y., Frontiers in Neuroscience 2026. DOI 10.3389/fnins.2026.1828237.
- Setting: missing T1c. Uses an uncertainty-gated fusion plus single-image TTA, with a BraTS 2021 → 2023 transfer.
- Reported [LITERATURE RESULT]: 89.20% average Dice on BraTS 2021 (missing-T1c protocol).
- **Caveat to investigate:** BraTS 2023 glioma training data is believed to largely overlap with BraTS 2021, so "cross-dataset" 2021→2023 transfer may not be a genuine external shift. This is a methodological weakness in the field that is worth documenting.

### C11. Other 2024–2026 missing-modality methods [V: existence and topic only]
- Mind the Gap / MedMAP (Liu T. et al., arXiv:2409.19366; PubMed 40833905)
- Unveiling Incomplete Modality BTS (Sun Z. et al., arXiv:2406.08634)
- PASSION (arXiv:2407.14796)
- No Modality Left Behind (arXiv:2509.15017)
- AMGFormer (arXiv:2601.19349)
- CausalDisenSeg (arXiv:2604.13409)
- Uni-Encoder Meets Multi-Encoders (arXiv:2604.22177)
- D3Seg (arXiv:2605.22249; includes an external BraTS-MEN subset)
- Virtual-node GNN (arXiv:2605.16880)
- LASSNet (arXiv:2609.06733, Sept 2026)
- Relevance: **evidence of saturation.** There are ≥10 new architectures in about 2 years, almost all on BraTS 2018/2020 internal splits.

### C12. Awesome missing modality for medical images (curated list) [V]
- github.com/han-liu/awesome-missing-modality-for-medical-images. Use it as a search index only, not as a citation.

---

## D. Uncertainty, calibration, failure detection, quality control

### D1. QU-BraTS: MICCAI BraTS 2020 Challenge on Quantifying Uncertainty in Brain Tumor Segmentation [V]
- Mehta R. et al., MELBA 2022 (arXiv:2112.10074). 14 teams.
- Introduces an uncertainty score that rewards filtering out uncertain wrong voxels while keeping certain correct ones.
- Relevance: the voxel-level UQ evaluation standard for BraTS. It covers complete modalities and internal data only.

### D2. Comparative benchmarking of failure detection methods in medical image segmentation: unveiling the role of confidence aggregation [V]
- Zenk M., Zimmerer D., Isensee F., Traub J., Norajitra T., Jäger P. F., Maier-Hein K., Medical Image Analysis 101:103392 (2025). arXiv:2406.03323.
- Datasets:
  - brain tumour 2D: FeTS 2022 with artificial corruptions
  - brain tumour 3D: BraTS 2019 with a population shift toward LGG
  - M&Ms heart, prostate, COVID CT, KiTS23
- Methods: 13, including MC-dropout, deep ensembles, aggregation schemes, pairwise-DSC, quality regression, Mahalanobis and VAE.
- Metric: **AURC** (risk–coverage).
- Findings [LITERATURE RESULT]: ensemble + pairwise-DSC is best across datasets; MC-dropout + pairwise-DSC is a cheaper alternative; OOD detection ≠ failure detection.
- Relevance: **the methodological reference for case-level failure detection.** Missing-modality inputs and real acquisition-shift glioma cohorts (e.g. BraTS-Africa) are **not** among its shifts.

### D3. Better than Average: Spatially-Aware Aggregation of Segmentation Uncertainty Improves Downstream Performance [V]
- Guarino V. E. et al., CVPR 2026 (arXiv:2603.29941). Ten datasets, OOD and failure detection.
- Finding: spatially-aware aggregators beat the global mean, but no single aggregator wins everywhere. A meta-aggregator is proposed.
- Relevance: shows that **generic aggregation methods are actively being covered** by strong groups.

### D4. QCResUNet: Joint Subject-level and Voxel-level Segmentation Quality Prediction [V]
- Qiu P. et al., arXiv:2412.07156 (Medical Image Analysis, per listing; verify).
- Brain tumour QC with external BraTS-SSA and WUSM data. Reported [LITERATURE RESULT] MAE 0.060 for DSC prediction.
- Relevance: learned QC for glioma segmentation **already includes BraTS-Africa as an external set.**

### D5. Confidence calibration and predictive uncertainty estimation for deep medical image segmentation [R]
- Mehrtash A. et al., IEEE TMI 2020. Brain tumour among its tasks.

### D6. Assessing reliability and challenges of uncertainty estimations for medical image segmentation [R]
- Jungo A., Reyes M., MICCAI 2019. BraTS.

### D7. Average Calibration Losses for Reliable Uncertainty in Medical Image Segmentation [V: existence]
- arXiv:2506.03942.

### D8. Segmenting with confidence through uncertainty quantification for brain tumor imaging [V]
- npj Digital Medicine 2026. Meningioma, evidential ensembles, external validation on 353 patients.

### D9. Rethinking Uncertainty in Segmentation: From Estimation to Decision [V]
- Maganti S., arXiv:2604.13262 (2026). Retinal data only.
- Finding [LITERATURE RESULT]: calibration improvement did not necessarily improve deferral decisions.
- Relevance: supports evaluating uncertainty **by its decision utility** (risk–coverage), not by ECE alone.

### D10. Are we using appropriate segmentation metrics? [R]
- Kofler F. et al., MELBA 2023. Brain tumour metric/expert-rating mismatch.

### D11. Metrics Reloaded: recommendations for image analysis validation [V]
- Maier-Hein L. et al., Nature Methods 21:195–212 (2024). DOI 10.1038/s41592-023-02151-z. Reference implementation in MONAI.
- Relevance: metric-selection protocol to follow.

### D12. Foundational UQ methods [R]
- Gal & Ghahramani (MC-dropout), ICML 2016
- Lakshminarayanan et al. (deep ensembles), NeurIPS 2017
- Guo et al. (temperature scaling / calibration), ICML 2017
- Geifman & El-Yaniv (selective classification / risk–coverage), NeurIPS 2017

---

## E. Domain shift, test-time adaptation, federated learning

### E1. SmaRT: Style-Modulated Robust Test-Time Adaptation for Cross-Domain Brain Tumor Segmentation in MRI [V]
- arXiv:2509.17925 (2025). Source-free TTA validated on sub-Saharan African and pediatric cohorts.

### E2. A Large Scale Benchmark for Test Time Adaptation Methods in Medical Image Segmentation (MedSeg-TTA) [V]
- Yu W. et al., arXiv:2512.02497 (Dec 2025). 20 TTA methods, 7 modalities.
- Finding [LITERATURE RESULT]: no paradigm is best everywhere, and several methods deteriorate under strong inter-center shift.

### E3. BraTS-Africa adaptation papers [V: existence]
- Parameter-efficient fine-tuning (arXiv:2412.14100)
- Generative style transfer (arXiv:2501.04734)
- Domain-adaptive transformer (arXiv:2511.02928, NeurIPS 2025 workshop)
- nnU-Net on SSA (arXiv:2511.02893)
- BraTS-SSA 2025 winner (arXiv:2510.03568)
- Relevance: **BraTS-Africa accuracy adaptation is an active, crowded area.**

### E4. Federated learning enables big data for rare cancer boundary detection (FeTS) [R]
- Pati S. et al., Nature Communications 2022.

### E5. TENT: Fully test-time adaptation by entropy minimization [R]
- Wang D. et al., ICLR 2021.

---

## F. Foundation / self-supervised models

### F1. BrainSegFounder: Towards 3D foundation models for neuroimage segmentation [V]
- Cox J. et al. (verify), Medical Image Analysis 2024. arXiv:2406.10395; PubMed 39146701.
- Two-stage self-supervised pretraining on 41,400 participants, evaluated on BraTS and ATLAS v2.0.

### F2. MedSAM: Segment anything in medical images [R]
- Ma J. et al., Nature Communications 2024.

### F3. BrainDINO [V: existence] (arXiv:2604.27277) and Triad (arXiv:2502.14064)
- Brain/3D MRI foundation models.

---

## G. Items flagged for follow-up (not yet verified)

- Exact BraTS 2023 GLI training set composition vs BraTS 2021. It is believed to be identical at 1,251 cases, which would matter for any "cross-version" claim.
- UPenn-GBM: number of manually revised segmentations.
- UCSF-PDGM: exact overlap count with BraTS 2021, from the TCIA mapping file.
- BraTS-Africa: split of the 146 cases into public-labelled vs held-out.
- MU-Glioma-Post: case count and whether labels are expert-refined.
- Licences of mmFormer, M3AE, ShaSpec, RFNet repositories, and of nnU-Net.

---

## H. Added in the pre-protocol audit (2026-09-27)

Full closest-work audit: [12_PRE_PROTOCOL_AUDIT.md](12_PRE_PROTOCOL_AUDIT.md).

### H1. Reliability analysis for BraTS-GoAT segmentation: a controlled robustness study of deep-ensemble uncertainty [V]
- arXiv:2608.13223 (2026).
- Design: nnU-Net ResEnc-L with a 3-seed ensemble; ECE, AURC, per-region ET/TC/WT.
- Shifts: synthetic corruptions only. No missing sequences.
- Code: github.com/riyashet-hds/brats-goat-reliability

### H2. Confidence is Not Reliability: Rethinking MC Dropout in Brain Tumour Segmentation [V]
- Wong X. C. et al., MIUA 2026, arXiv:2606.19300.
- Region-specific ET calibration on 126 BraTS21 cases, complete inputs.

### H3. BMDS-Net [V]
- Zhou et al., arXiv:2601.17504 (2026).
- ECE reported on complete inputs only. Single-sequence removal evaluated for Dice only.

### H4. GlioMODA: Robust glioma segmentation in clinical routine [V]
- Canisius J., Buchner J., Rosier M. et al., Neuro-Oncology Advances 2026 (PubMed 41841144).
- 11 sequence protocols with volumetric error analysis.
- Code: github.com/BrainLesion/GlioMODA

### H5. AI-powered segmentation and prognosis with missing MRI in pediatric brain tumors [V]
- npj Precision Oncology 2026.
- Dropout-trained model for missing FLAIR/T1w in a pediatric cohort.

### H6. Modality redundancy for MRI-based glioblastoma segmentation [V]
- De Sutter S. et al., IJCARS 2024; 19(10):2101–2109.

### H7. Öchsner et al. — peer-reviewed version of [C7] [V]
- Frontiers in Neurology, 28 July 2026 (doi 10.3389/fneur.2026.1889198).

### H8. Efficient Bayesian Uncertainty Estimation for nnU-Net [V]
- Zhao Y. et al., MICCAI 2022.

### H9. [CORRECTED 2026-09-27] MoFe loss and the TMI DOI are two different papers
- **DOI 10.1109/TMI.2025.3526818** is PNDC: Qiu Y. et al., *Does Adding a Modality Really Make Positive Impacts in Incomplete Multi-Modal Brain Tumor Segmentation?*, IEEE TMI 2025. Abstract only. Its "double calibration" is a region-level fusion correction. Full text UNVERIFIED.
- **MoFe ("More vs. Fewer") loss** is from SimMLM: Li S., Chen C., Han J., arXiv:2507.19264 (ICCV 2025 per a secondary listing).
  - BraTS 2018, all 15 subsets.
  - ECE/SCE per ET/TC/WT, **averaged over configurations**.
  - No case-level failure detection. No external data.
  - Code: github.com/LezJ/SimMLM
- The earlier entry conflated the two.

## I. Added in the pre-freeze audit (2026-09-27; see [13](13_PRE_FREEZE_AUDIT.md))

### I1. Missing Modality-Aware Calibration for Trustworthy Brain Tumor Segmentation (MMA-LTS) [V, full text]
- Lee S., Kim H., Hong S., Han D., Yi M. Y., MICCAI 2026. https://papers.miccai.org/miccai-2026/0659-Paper1236.html
- Voxel-wise post-hoc temperature scaling conditioned on modality availability.
- ECE per 15 combinations × WT/TC/ET on BraTS 2020 and FeTS 2024.
- No case-level failure detection. No external data. No statistical tests. Code N/A.
- **Closes voxel-level missingness-specific calibration.**

### I2. Foundation Model and Radiomics Distance Scores for Post-Hoc Segmentation Failure Detection [V, full text]
- Joham S. J. et al., UNSURE 2026.
- Pooled vs within-site E-AURC. Shows pooled ranking can reward between-site difficulty ordering.

### I3. Reliability, Not Accuracy, Is the Bottleneck in AI-assisted Post-Treatment Glioma Segmentation [V, full text]
- Badr M. A. M. et al., UNSURE 2026.
- Region-aware recalibration and risk-controlled triage on BraTS 2024 post-treatment data. No missing sequences.

### I4. Guarantees That Survive a Missing Scan: Modality-Conditional Conformal Prediction [V, abstract]
- Ajit A., MLMI 2026.
- Classification task. Conformal calibration stratified by missingness pattern.

### I5. Other screened, non-overlapping papers [V, title/abstract]
- MICCAI 2026: SAR-Net, HK-Fuse, MoCaf-Mamba, BrainAnytime
- MICCAI 2026 satellite: BrainWorks "Reliability-aware Multimodal Fusion" (full text; complete inputs)
- BraTS 2025 proceedings: BRAIN-CATS, "Enabling Uncertainty Measurement… BraTS 2025 Pediatrics"
- MICCAI 2025: MST-KDNet, DC-Seg, IM-Fuse, FedAMM

### I6. Pemberton et al. 2023 (C8) — full text now read via Europe PMC [V]
- No uncertainty, calibration or failure-detection analysis. "Quality control" refers to visual data checks only.

### Dataset corrections (from the official TCIA crosswalk `BraTS2021_MappingToTCIA.xlsx`)
- BraTS 2021 training contains **511 UPenn-origin (site 1)** cases: 403 `UPENN-GBM` + 108 `UPENN-GBM_Additional`.
- **[C7] Öchsner et al.** excluded only 403 (848 = 1,251 − 403). This implies 108 same-site cases remained in their development set [INFERENCE].
- **BraTS-Africa (TCIA v2 metadata):** 95 glioma + 51 other neoplasms, all labelled.

### Corrections to earlier entries
- **A5 (BraTS-Africa):** 146 cases = 95 glioma + 51 other CNS tumours. All scans are 1.5T. Labels were refined from nnU-Net pre-segmentations in a three-stage expert review. The count of public glioma labels needs verifying (sources say 60, 75 or 95).
- **A6 (UCSF-PDGM):** 495 unique patients after follow-up re-labelling. Labels come from an automated ensemble, then manual correction and approval by 2 reviewers. TCIA provides the BraTS-ID mapping.
- **A7 (UPenn-GBM):** labels are automated plus expert-revised/approved (per-case counts not given). The collection has 630 subjects, of which about 403 are inside BraTS 2021 (per [C7]). The BraTS 2021 mapping file lists UPenn as a source.
- **C7:** the external test is the UPenn subset **inside** BraTS 2021, with development on the remaining 848 cases. It is a held-out institution, not an independently preprocessed cohort.
