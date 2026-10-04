from __future__ import annotations

from itertools import combinations
from pathlib import Path

import numpy as np
import pytest

from brats_uncertainty.errors import DataValidationError, ProtocolDeviationError
from brats_uncertainty.grouping.groups import UnionFind, build_groups
from brats_uncertainty.grouping.review import (
    ReviewRecord,
    linked_pairs,
    read_reviews,
    resolve_reviews,
    write_reviews,
)
from brats_uncertainty.grouping.similarity import MaskIndex, pairwise_screen, wt_dice
from brats_uncertainty.grouping.tscreen import (
    PROTOCOL_POSITIVE_CONTROLS,
    TScreenRecord,
    compute_t_screen,
    run_screen,
)
from brats_uncertainty.metrics.dice import dice
from tests.fixtures.synthetic import sphere

SHAPE = (20, 20, 20)
REVIEWERS = ("Ayush Kushwaha", "Dr. Sreenivasa Chakravarthi")
FAKE_SHA = "0" * 64  # placeholder hash for synthetic in-memory masks (test only)


def _masks(n: int, seed: int = 0) -> dict[str, MaskIndex]:
    rng = np.random.default_rng(seed)
    out = {}
    for i in range(n):
        c = tuple(float(rng.uniform(6, 14)) for _ in range(3))
        m = sphere(SHAPE, c, float(rng.uniform(2, 5)))  # type: ignore[arg-type]
        out[f"SYN-{i:03d}"] = MaskIndex.from_mask(f"SYN-{i:03d}", m)
    return out


def test_wt_dice_matches_dense_dice() -> None:
    ms = _masks(8)
    dense = {k: np.zeros(SHAPE, bool) for k in ms}
    for k, m in ms.items():
        dense[k].flat[m.flat] = True
    for a, b in combinations(ms, 2):
        assert wt_dice(ms[a], ms[b]) == pytest.approx(dice(dense[a], dense[b]))


def test_pruned_screen_equals_brute_force() -> None:
    ms = _masks(25, seed=3)
    t = 0.3
    brute = {tuple(sorted((a, b))) for a, b in combinations(ms, 2) if wt_dice(ms[a], ms[b]) >= t}
    res = pairwise_screen(ms, t)
    assert {p.key for p in res.flagged} == brute
    assert res.n_pairs_compared == 25 * 24 // 2


def _control_masks() -> dict[str, MaskIndex]:
    base = sphere(SHAPE, (10, 10, 10), 4)
    shifted = sphere(SHAPE, (10, 10, 11), 4)
    other = sphere(SHAPE, (10, 11, 10), 4)
    ids = [c for pair in PROTOCOL_POSITIVE_CONTROLS.values() for c in pair]
    arrays = [base, shifted, base, other]
    return {c: MaskIndex.from_mask(c, a) for c, a in zip(ids, arrays, strict=True)}


def test_t_screen_is_min_of_positive_controls() -> None:
    masks = _control_masks()
    rec = compute_t_screen(masks, {c: FAKE_SHA for c in masks})
    a = wt_dice(masks["BraTS2021_00626"], masks["BraTS2021_00758"])
    b = wt_dice(masks["BraTS2021_00639"], masks["BraTS2021_00557"])
    assert rec.value == min(a, b)
    rec.validate()


def test_t_screen_record_cannot_be_hand_set() -> None:
    masks = _control_masks()
    rec = compute_t_screen(masks, {c: FAKE_SHA for c in masks})
    forged = TScreenRecord(
        value=0.5,
        control_dice=rec.control_dice,
        control_pairs=rec.control_pairs,
        label_sha256=rec.label_sha256,
        computed_at=rec.computed_at,
    )
    with pytest.raises(ProtocolDeviationError):
        forged.validate()
    with pytest.raises(ProtocolDeviationError):
        run_screen(masks, forged)


def test_run_screen_flags_positive_controls() -> None:
    masks = {**_control_masks(), **_masks(10, seed=9)}
    rec = compute_t_screen(masks, {c: FAKE_SHA for c in _control_masks()})
    res = run_screen(masks, rec)
    keys = {p.key for p in res.flagged}
    assert ("BraTS2021_00626", "BraTS2021_00758") in keys
    assert ("BraTS2021_00557", "BraTS2021_00639") in keys


def _rev(a: str, b: str, d: str, rnd: str = "primary") -> ReviewRecord:
    who = REVIEWERS[0] if rnd == "primary" else REVIEWERS[1]
    return ReviewRecord(a, b, d, who, rnd, "2000-01-01T00:00:00Z", "synthetic test reason")


def test_review_resolution_rules() -> None:
    flagged = [("x1", "x2"), ("x3", "x4"), ("x5", "x6"), ("x7", "x8")]
    recs = [
        _rev("x1", "x2", "SAME_PATIENT"),
        _rev("x3", "x4", "DIFFERENT_PATIENT"),
        _rev("x5", "x6", "SAME_PATIENT"),
        _rev("x5", "x6", "DIFFERENT_PATIENT", "second"),  # disagreement -> UNRESOLVED
        _rev("x8", "x7", "DIFFERENT_PATIENT"),
        _rev("x8", "x7", "DIFFERENT_PATIENT", "second"),  # agreement -> confirmed
    ]
    final = resolve_reviews(flagged, recs, REVIEWERS)
    assert final == {
        ("x1", "x2"): "SAME_PATIENT",
        ("x3", "x4"): "DIFFERENT_PATIENT",
        ("x5", "x6"): "UNRESOLVED",
        ("x7", "x8"): "DIFFERENT_PATIENT",
    }
    assert linked_pairs(final) == [("x1", "x2"), ("x5", "x6")]


def test_review_procedure_violations() -> None:
    with pytest.raises(DataValidationError, match="lack a primary review"):
        resolve_reviews([("a", "b")], [], REVIEWERS)
    with pytest.raises(ProtocolDeviationError, match="not flagged"):
        resolve_reviews([("a", "b")], [_rev("a", "c", "SAME_PATIENT")], REVIEWERS)
    bad = ReviewRecord("a", "b", "SAME_PATIENT", "Someone Else", "primary", "t", "r")
    with pytest.raises(ProtocolDeviationError, match="protocol reviewer"):
        resolve_reviews([("a", "b")], [bad], REVIEWERS)
    with pytest.raises(DataValidationError):
        ReviewRecord("a", "b", "MAYBE", REVIEWERS[0], "primary", "t", "r")
    with pytest.raises(DataValidationError):
        ReviewRecord("a", "b", "SAME_PATIENT", REVIEWERS[0], "primary", "t", " ")


def test_review_csv_roundtrip(tmp_path: Path) -> None:
    recs = [_rev("a", "b", "UNRESOLVED"), _rev("a", "b", "UNRESOLVED", "second")]
    p = tmp_path / "reviews.csv"
    write_reviews(p, recs)
    assert read_reviews(p) == sorted(recs, key=lambda r: r.round == "second")


def test_union_find_transitive() -> None:
    uf = UnionFind(["a", "b", "c", "d", "e"])
    uf.union("a", "b")
    uf.union("c", "b")
    uf.union("d", "e")
    assert uf.components() == [["a", "b", "c"], ["d", "e"]]


def test_build_groups_transitive_and_deterministic() -> None:
    ids = [f"SYN-{i}" for i in range(8)] + ["BraTS2021_00626", "BraTS2021_00758"]
    g = build_groups(
        ids,
        prefix="DEV",
        verified_groups={"A": ("BraTS2021_00626", "BraTS2021_00758")},
        shared_tcia_groups=[["SYN-6", "SYN-7"]],
        linked_review_pairs=[("SYN-0", "SYN-1"), ("SYN-1", "SYN-2")],
    )
    assert g.case_to_group["SYN-0"] == g.case_to_group["SYN-2"]
    assert g.case_to_group["BraTS2021_00626"] == g.case_to_group["BraTS2021_00758"]
    assert g.case_to_group["SYN-6"] == g.case_to_group["SYN-7"]
    assert len(g.groups) == 10 - 2 - 1 - 1
    assert g.groups["DEV-0001"] == ("BraTS2021_00626", "BraTS2021_00758")
    g2 = build_groups(
        list(reversed(ids)),
        prefix="DEV",
        verified_groups={"A": ("BraTS2021_00626", "BraTS2021_00758")},
        shared_tcia_groups=[["SYN-6", "SYN-7"]],
        linked_review_pairs=[("SYN-1", "SYN-2"), ("SYN-0", "SYN-1")],
    )
    assert g.sha256 == g2.sha256
    assert g.audit()["n_multi_case_groups"] == 3


def test_build_groups_partial_verified_group_raises() -> None:
    with pytest.raises(DataValidationError, match="partly present"):
        build_groups(
            ["BraTS2021_00626", "SYN-1"],
            prefix="DEV",
            verified_groups={"A": ("BraTS2021_00626", "BraTS2021_00758")},
            shared_tcia_groups=[],
            linked_review_pairs=[],
        )
