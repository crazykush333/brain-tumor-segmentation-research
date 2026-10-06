"""Automated B8 adjudication (amendment v1.0-A3) on SYNTHETIC volumes only."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from scipy import ndimage

from brats_uncertainty.grouping import auto_b8 as ab
from tests.conftest import REPO_ROOT

CFG = ab.AutoB8Config.load(REPO_ROOT / ab.CONFIG_RELPATH)
SHAPE = (40, 40, 24)


def _anatomy(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return ndimage.gaussian_filter(rng.normal(size=SHAPE), 2.0) * 10 + 100


def _case(patient: int, visit: int) -> tuple[dict[str, np.ndarray], np.ndarray]:
    base = _anatomy(1000 + patient)
    rng = np.random.default_rng(10 * patient + visit)
    lesion = np.zeros(SHAPE, dtype=np.uint8)
    lesion[10 + visit : 16 + visit, 12:18, 8:12] = 2  # the lesion moves between visits
    imgs = {
        m: base * (1 + 0.1 * k) + rng.normal(scale=0.3, size=SHAPE) + 5 * (lesion > 0)
        for k, m in enumerate(CFG.modalities)
    }
    return imgs, lesion


def _cohort() -> tuple[dict[str, tuple[int, int]], dict[str, ab.CaseMeta], dict[str, list[str]]]:
    """10 patients; patients 0 and 1 have two visits (the verified groups A and B)."""
    cases: dict[str, tuple[int, int]] = {}
    meta: dict[str, ab.CaseMeta] = {}
    i = 0
    for p in range(10):
        for v in range(2 if p < 2 else 1):
            cid = f"SYN_{i:03d}"
            cases[cid] = (p, v)
            real = p >= 4  # patients 4..9 carry real TCIA IDs in one collection
            meta[cid] = ab.CaseMeta(
                collection="SYNTH-COLL" if real else "SYNTH-NEW",
                site="18",
                tcia_id=f"SYN-P{p}" if real else None,
            )
            i += 1
    groups = {"A": ["SYN_000", "SYN_001"], "B": ["SYN_002", "SYN_003"]}
    return cases, meta, groups


def _descriptor(cases: dict[str, tuple[int, int]]) -> Any:
    def d(cid: str) -> ab.Descriptor:
        imgs, lab = _case(*cases[cid])
        return ab.case_descriptor(imgs, lab, CFG)

    return d


def test_config_is_the_pre_specified_file() -> None:
    assert CFG.raw["amendment"] == "v1.0-A3"
    assert CFG.raw["reference_negatives"]["quantile"] == 0.999
    assert CFG.raw["acceptance"]["max_group_size"] == 8
    assert len(CFG.sha256) == 64


def test_metadata_rules_in_order() -> None:
    m = {
        "a": ab.CaseMeta("C1", "18", "P1"),
        "b": ab.CaseMeta("C1", "18", "P1"),
        "c": ab.CaseMeta("C1", "18", "P2"),
        "d": ab.CaseMeta("C2", "4", "P9"),
        "e": ab.CaseMeta("U", "18", None, sex="M", idh="wildtype"),
        "f": ab.CaseMeta("U", "18", None, sex="F", idh="wildtype"),
        "g": ab.CaseMeta("U", "18", None, sex="M", idh=None),
    }
    v = {"A": ["c", "d"]}
    assert ab.metadata_rule("c", "d", m, v) == (ab.SAME, "R1")  # verified beats R3
    assert ab.metadata_rule("a", "b", m, v) == (ab.SAME, "R2")
    assert ab.metadata_rule("a", "c", m, v) == (ab.DIFFERENT, "R3")
    assert ab.metadata_rule("a", "d", {**m, "d": ab.CaseMeta("C2", "4", "P1")}, {}) == (
        ab.SAME,
        "R2",
    )
    assert ab.metadata_rule("e", "f", m, v) == (ab.DIFFERENT, "R4")
    assert ab.metadata_rule("e", "g", m, v) is None  # unknown IDH never decides
    assert ab.idh_class("IDH1 p.R132H") == "mutant" and ab.idh_class("unknown") is None
    assert ab.real_tcia_id("new-not-previously-in-TCIA") is None


def test_adjudication_separates_same_and_different_patients() -> None:
    cases, meta, groups = _cohort()
    ids = sorted(cases)
    flagged = [(a, b) for i, a in enumerate(ids) for b in ids[i + 1 :]]  # every pair flagged
    adj = ab.adjudicate(flagged, ids, meta, groups, _descriptor(cases), CFG)
    assert adj.accepted, adj.acceptance
    assert adj.tau_ctrl > adj.tau_neg
    dec = {k: v["decision"] for k, v in adj.decisions.items()}
    assert dec[("SYN_000", "SYN_001")] == ab.SAME and dec[("SYN_002", "SYN_003")] == ab.SAME
    # different synthetic patients without metadata identity are decided by anatomy (R8)
    assert dec[("SYN_000", "SYN_004")] == ab.DIFFERENT
    assert adj.decisions[("SYN_000", "SYN_004")]["rule"] == "R8"
    sizes = sorted(len(g) for g in adj.groups)
    assert sizes[-1] == 2 and sum(sizes) == len(ids)
    s = ab.summary(adj, len(ids))
    assert s["largest_group"] == 2 and s["accepted"] is True
    again = ab.adjudicate(flagged, ids, meta, groups, _descriptor(cases), CFG)
    assert again.decisions == adj.decisions and again.tau_neg == adj.tau_neg  # deterministic


def test_pathological_giant_group_is_rejected_not_accepted() -> None:
    """If every case looks like one patient, the procedure must stop (acceptance fails)."""
    cases, meta, groups = _cohort()
    ids = sorted(cases)
    flagged = [(a, b) for i, a in enumerate(ids) for b in ids[i + 1 :]]
    meta = {c: ab.CaseMeta("SYNTH-NEW", "18", None) for c in ids}  # no metadata negatives

    def same_anatomy(cid: str) -> ab.Descriptor:
        imgs, lab = _case(0, cases[cid][1])
        return ab.case_descriptor(imgs, lab, CFG)

    adj = ab.adjudicate(flagged, ids, meta, groups, same_anatomy, CFG)
    assert not adj.accepted
    assert math.isnan(adj.tau_neg) or not adj.acceptance["max_group_size"]


def test_site1_in_development_fails_acceptance() -> None:
    cases, meta, groups = _cohort()
    ids = sorted(cases)
    meta["SYN_005"] = ab.CaseMeta("SYNTH-NEW", "1", None)
    adj = ab.adjudicate([], ids, meta, groups, _descriptor(cases), CFG)
    assert adj.acceptance["no_site1_in_development"] is False and not adj.accepted


def test_descriptor_excludes_the_lesion(tmp_path: Path) -> None:
    imgs, lab = _case(3, 0)
    d = ab.case_descriptor(imgs, lab, CFG)
    big = lab.copy()
    big[:] = 2  # everything is lesion -> no valid block
    assert ab.case_descriptor(imgs, big, CFG).valid.sum() == 0
    assert 0 < d.valid.sum() <= d.n_brain_blocks
    s, _cov, n = ab.pair_similarity(d, ab.case_descriptor(imgs, big, CFG), CFG)
    assert math.isnan(s) and n == 0
    with pytest.raises(KeyError):
        ab.case_descriptor({"T1": imgs["T1"]}, lab, CFG)  # all four sequences are required


def test_automated_decisions_must_cover_exactly_the_flagged_pairs(tmp_path: Path) -> None:
    from brats_uncertainty.errors import DataValidationError, ProtocolDeviationError
    from brats_uncertainty.grouping.review import read_automated_decisions

    flagged = [("SYN_001", "SYN_000"), ("SYN_002", "SYN_003")]
    p = tmp_path / "d.csv"
    header = ",".join(ab.DECISION_FIELDS) + "\n"
    p.write_text(
        header
        + "SYN_000,SYN_001,SAME_PATIENT,R1,,\nSYN_002,SYN_003,DIFFERENT_PATIENT,R8,0.1,0.9\n",
        encoding="utf-8",
    )
    assert read_automated_decisions(p, flagged) == {
        ("SYN_000", "SYN_001"): "SAME_PATIENT",
        ("SYN_002", "SYN_003"): "DIFFERENT_PATIENT",
    }
    p.write_text(header + "SYN_000,SYN_001,SAME_PATIENT,R1,,\n", encoding="utf-8")
    with pytest.raises(ProtocolDeviationError, match="exactly the flagged"):
        read_automated_decisions(p, flagged)
    p.write_text(header + "SYN_000,SYN_001,MAYBE,R1,,\n", encoding="utf-8")
    with pytest.raises(DataValidationError, match="invalid automated decision"):
        read_automated_decisions(p, flagged)


def test_runner_uses_the_automated_b8_procedure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from brats_uncertainty.orchestration import steps as st
    from tests.unit.test_orchestration import make_ctx

    ctx = make_ctx(tmp_path)
    assert st.b8_automated(ctx)  # the committed configuration selects amendment v1.0-A3
    (ctx.records / "B7").mkdir(parents=True)
    (ctx.records / "B7" / "flagged_pairs.csv").write_text(
        "case_a,case_b\nSYN_000,SYN_001\n", encoding="utf-8"
    )
    import brats_uncertainty.protocol as protocol_mod

    real_load = protocol_mod.load_protocol
    monkeypatch.setattr(protocol_mod, "load_protocol", lambda root: real_load(REPO_ROOT))
    seen: list[Any] = []
    monkeypatch.setattr(st, "produce_b8_automated", lambda c, f: seen.append(f) or [])
    st.produce_b8(ctx)
    assert seen == [[("SYN_000", "SYN_001")]]
