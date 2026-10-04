"""nnU-Net v2 implementation of ``EnsembleSource`` (requires torch + nnunetv2 + a GPU).

STATUS: written against the nnU-Net v2 inference API (``nnUNetPredictor``,
``preprocessor.run_case``, ``predict_logits_from_preprocessed_data``,
``convert_predicted_logits_to_segmentation_with_correct_shape``). It is exercised
for the first time by the EXP-001 inference-timing run (spec §2.9, I1) on the pinned
version, before any validation or test evaluation; a mismatch fails loudly there.

Protocol settings (§9, §10): sliding window step 0.5, mirroring OFF, Gaussian
weighting (nnU-Net default), checkpoint_final, mean of three members' sigmoid
probabilities, threshold 0.5 (applied by ``study.units``). Missing sequences are set
to 0 in the **preprocessed (normalized)** tensor (REPRODUCIBILITY.md §4 item 13).
Images and GT are read with nnU-Net's own reader, so both share one array space.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from brats_uncertainty.inference.ensemble import apply_missingness_preprocessed
from brats_uncertainty.models.nnunet import PROTOCOL_CHECKPOINT, InferenceSettings
from brats_uncertainty.preprocessing.modalities import ModalitySubset

REGION_ORDER = ("WT", "TC", "ET")  # dataset.json: whole_tumor, tumor_core, enhancing_tumor


class NnUNetEnsembleSource:  # pragma: no cover - requires torch, nnunetv2 and CUDA
    def __init__(
        self,
        member_folders: Sequence[Path],
        image_files: Mapping[str, Sequence[Path]],
        label_files: Mapping[str, Path],
        label_regions: Mapping[str, Sequence[int]],
    ) -> None:
        import torch
        from nnunetv2.inference.predict_from_raw_data import nnUNetPredictor

        settings = InferenceSettings()  # raises on any deviation from §9
        if len(member_folders) != settings.n_members:
            raise ValueError("exactly three member model folders (seeds 0, 1, 2)")
        self.predictors = []
        for folder in member_folders:
            p = nnUNetPredictor(
                tile_step_size=settings.tile_step_size,
                use_gaussian=True,
                use_mirroring=settings.use_mirroring,
                perform_everything_on_device=True,
                device=torch.device("cuda"),
                verbose=False,
                allow_tqdm=False,
            )
            p.initialize_from_trained_model_folder(
                str(folder), use_folds=(0,), checkpoint_name=PROTOCOL_CHECKPOINT
            )
            self.predictors.append(p)
        self.image_files, self.label_files = image_files, label_files
        self.label_regions = label_regions
        self._cache: tuple[str, Any, Any] | None = None

    def _preprocessed(self, case_id: str) -> tuple[Any, Any]:
        if self._cache is None or self._cache[0] != case_id:
            p = self.predictors[0]
            pre = p.configuration_manager.preprocessor_class(verbose=False)
            data, _, props = pre.run_case(
                [str(f) for f in self.image_files[case_id]],
                None,
                p.plans_manager,
                p.configuration_manager,
                p.dataset_json,
            )
            self._cache = (case_id, data, props)
        return self._cache[1], self._cache[2]

    def member_probabilities(
        self, case_id: str, subset: ModalitySubset
    ) -> Mapping[str, Sequence[NDArray[np.floating]]]:
        import torch
        from nnunetv2.inference.export_prediction import (
            convert_predicted_logits_to_segmentation_with_correct_shape,
        )

        data, props = self._preprocessed(case_id)
        zeroed = apply_missingness_preprocessed(np.asarray(data), subset)
        out: dict[str, list[NDArray[np.floating]]] = {r: [] for r in REGION_ORDER}
        for p in self.predictors:
            logits = p.predict_logits_from_preprocessed_data(torch.from_numpy(zeroed)).cpu()
            _, probs = convert_predicted_logits_to_segmentation_with_correct_shape(
                logits,
                p.plans_manager,
                p.configuration_manager,
                p.label_manager,
                props,
                return_probabilities=True,
            )
            probs = np.asarray(probs, dtype=np.float32)
            if probs.shape[0] != len(REGION_ORDER):
                raise ValueError(f"expected {len(REGION_ORDER)} region channels, got {probs.shape}")
            for i, r in enumerate(REGION_ORDER):
                out[r].append(probs[i])
        return out

    def ground_truth(self, case_id: str) -> Mapping[str, NDArray[np.bool_]]:
        rw = self.predictors[0].plans_manager.image_reader_writer_class()
        seg, _ = rw.read_seg(str(self.label_files[case_id]))
        lab = np.asarray(seg)[0]
        return {r: np.isin(lab, list(v)) for r, v in self.label_regions.items()}
