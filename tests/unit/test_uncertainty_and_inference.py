from __future__ import annotations

import numpy as np
import pytest

from brats_uncertainty.errors import ProtocolDeviationError
from brats_uncertainty.inference.ensemble import binarize, ensemble_mean, member_masks
from brats_uncertainty.models.nnunet import (
    InferenceSettings,
    RunSpec,
    all_run_specs,
    build_dataset_json,
    build_splits_final,
    train_command,
)
from brats_uncertainty.uncertainty.scores import (
    binary_entropy_bits,
    case_scores,
    indicator_scores,
    u1_pairwise_dice,
    u2_negative_entropy,
    u3_max_probability,
)
from tests.fixtures.synthetic import synthetic_member_probs


def test_u1_all_empty_is_one() -> None:
    z = np.zeros((4, 4, 4), bool)
    assert u1_pairwise_dice([z, z, z]) == 1.0


def test_u1_discordant_empty_gives_mass_at_zero() -> None:
    z = np.zeros((4, 4, 4), bool)
    o = z.copy()
    o[1, 1, 1] = True
    # pairs: (z,z)=1, (z,o)=0, (z,o)=0 -> 1/3; with two non-empty identical: (o,o)=1 -> 1/3
    assert u1_pairwise_dice([z, z, o]) == pytest.approx(1 / 3)
    assert u1_pairwise_dice([z, o, o]) == pytest.approx(1 / 3)


def test_u1_requires_three_members() -> None:
    z = np.zeros((2, 2), bool)
    with pytest.raises(ProtocolDeviationError):
        u1_pairwise_dice([z, z])


def test_u2_u3_empty_roi() -> None:
    roi = np.zeros((3, 3, 3), bool)
    assert u2_negative_entropy(np.full((3, 3, 3), 0.5), roi) == 0.0
    assert u3_max_probability(np.full((3, 3, 3), 0.5), roi) == 1.0


def test_u2_bounds() -> None:
    roi = np.ones((2, 2, 2), bool)
    assert u2_negative_entropy(np.full((2, 2, 2), 0.5), roi) == pytest.approx(-1.0)
    assert u2_negative_entropy(np.ones((2, 2, 2)), roi) == pytest.approx(0.0, abs=1e-9)
    assert binary_entropy_bits(np.array([0.5]))[0] == pytest.approx(1.0)


def test_case_scores_on_synthetic_members() -> None:
    probs = synthetic_member_probs(np.random.default_rng(2))
    s = case_scores(probs)
    assert set(s) == {"U1", "U2", "U3"}
    assert 0.0 <= s["U1"] <= 1.0
    assert -1.0 <= s["U2"] <= 0.0
    assert 0.5 <= s["U3"] <= 1.0


def test_indicator_scores_negative_validation_risk() -> None:
    assert indicator_scores({"-T1c": 0.4}) == {"-T1c": -0.4}
    with pytest.raises(ValueError):
        indicator_scores({"-T1c": 1.4})


def test_ensemble_and_threshold() -> None:
    probs = [np.full((2, 2), v, dtype=np.float32) for v in (0.2, 0.5, 0.8)]
    np.testing.assert_allclose(ensemble_mean(probs), 0.5)
    assert binarize(np.array([0.49, 0.5])).tolist() == [False, True]
    assert [m.all() for m in member_masks(probs)] == [False, True, True]
    with pytest.raises(ProtocolDeviationError):
        binarize(np.array([0.3]), threshold=0.4)
    with pytest.raises(ProtocolDeviationError):
        ensemble_mean(probs[:2])


def test_inference_settings_frozen() -> None:
    InferenceSettings()
    with pytest.raises(ProtocolDeviationError):
        InferenceSettings(use_mirroring=True)
    with pytest.raises(ProtocolDeviationError):
        InferenceSettings(tile_step_size=0.25)


def test_run_specs_and_commands() -> None:
    specs = all_run_specs()
    assert len(specs) == 6
    assert {(s.arm, s.seed) for s in specs} == {(a, s) for a in "AB" for s in (0, 1, 2)}
    with pytest.raises(ProtocolDeviationError):
        RunSpec("C", 0)
    with pytest.raises(ProtocolDeviationError):
        RunSpec("A", 3)
    cmd = train_command(501, RunSpec("B", 1))
    assert cmd[:4] == ["nnUNetv2_train", "501", "3d_fullres", "0"]
    assert "ModalityDropout" in cmd[-1]


def test_dataset_json_and_splits() -> None:
    dj = build_dataset_json(10)
    assert dj["channel_names"] == {"0": "T1", "1": "T1c", "2": "T2", "3": "FLAIR"}
    assert dj["labels"]["enhancing_tumor"] == [3]
    assert build_splits_final(["b", "a"], ["c"]) == [{"train": ["a", "b"], "val": ["c"]}]
    with pytest.raises(ProtocolDeviationError):
        build_splits_final(["a"], ["a"])
