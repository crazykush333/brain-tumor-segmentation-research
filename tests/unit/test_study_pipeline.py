"""Evaluation pipeline on SYNTHETIC volumes only (never BraTS data): unit rows, resumable case
loop, SR2, C5 freeze, analyses (primary, families, descriptive), failure analysis, figures,
tables and provenance-stamped artifacts. Small bootstrap counts keep the tests fast; the
protocol values (10,000 / 12345) are the functions' defaults."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from brats_uncertainty.errors import DataValidationError, ProtocolDeviationError
from brats_uncertainty.metrics.selective import aurc
from brats_uncertainty.preprocessing.modalities import C4_NAMES, C5_NAMES, ModalitySubset
from brats_uncertainty.study.analysis import (
    SUPPORTING_MARGIN,
    assemble_families,
    external_analysis,
    internal_analysis,
    lexicographic_score,
    transfer_analysis,
    weighted_aurc,
)
from brats_uncertainty.study.failure import categorize, figure_cases
from brats_uncertainty.study.freeze import apply_indicator, freeze_c5, sr2_check
from brats_uncertainty.study.inference import evaluate_cases
from brats_uncertainty.study.run import analyze_study, evaluate_set
from brats_uncertainty.study.units import UNIT_FIELDS, read_unit_rows, unit_rows, units_filename
from tests.conftest import REPO_ROOT

SHAPE = (8, 8, 6)
N_REP = 40


class SyntheticSource:
    """SYNTHETIC ensemble: GT blob per case; members = GT + condition-dependent noise."""

    def __init__(self, seed: int, quality: float = 1.0) -> None:
        self.seed, self.quality = seed, quality
        self.calls = 0

    def _rng(self, case: str, extra: int = 0) -> np.random.Generator:
        return np.random.default_rng([self.seed, int(case.split("_")[-1]), extra])

    def ground_truth(self, case_id: str) -> Mapping[str, np.ndarray]:
        rng = self._rng(case_id)
        wt = np.zeros(SHAPE, dtype=bool)
        x, y = rng.integers(1, 4, size=2)
        wt[x : x + 4, y : y + 4, 1:5] = True
        tc = wt.copy()
        tc[x, :, :] = False
        et = tc.copy()
        if int(case_id.split("_")[-1]) % 7 == 0:
            et[:] = False  # some cases without ET
        return {"WT": wt, "TC": tc, "ET": et}

    def member_probabilities(
        self, case_id: str, subset: ModalitySubset
    ) -> Mapping[str, Sequence[np.ndarray]]:
        self.calls += 1
        gt = self.ground_truth(case_id)
        noise = (0.15 + 0.1 * len(subset.missing)) / self.quality
        out = {}
        for i, r in enumerate(("WT", "TC", "ET")):
            members = []
            for s in range(3):
                rng = self._rng(case_id, 100 * i + 10 * s + len(subset.missing))
                p = np.clip(gt[r].astype(np.float32) * 0.8 + rng.normal(0.1, noise, SHAPE), 0, 1)
                members.append(p.astype(np.float32))
            out[r] = members
        return out


def make_cases(prefix: str, n: int, start: int = 0) -> tuple[list[str], dict[str, str]]:
    cases = [f"{prefix}_{i:05d}" for i in range(start, start + n)]
    groups = {c: f"G{prefix}{i // 2}" for i, c in enumerate(cases)}  # pairs share a group
    return cases, groups


def build(
    tmp: Path, dataset: str, arm: str, n: int, start: int, conditions=C5_NAMES, quality=1.0
) -> list[dict[str, str]]:
    cases, groups = make_cases("SYNTH", n, start)
    out = tmp / units_filename(dataset, arm)
    evaluate_cases(
        cases=cases,
        group_of=groups,
        dataset=dataset,
        arm=arm,
        conditions=conditions,
        source=SyntheticSource(1 if arm == "A" else 2, quality),
        out=out,
    )
    return read_unit_rows(out)


@pytest.fixture(scope="module")
def study(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    tmp = tmp_path_factory.mktemp("units")
    val_a = build(tmp, "validation", "A", 16, 0, quality=3.0)
    val_b = build(tmp, "validation", "B", 16, 0)
    frozen = freeze_c5(val_a, val_b)
    test_a = apply_indicator(build(tmp, "internal_test", "A", 20, 100), frozen)
    test_b = apply_indicator(build(tmp, "internal_test", "B", 20, 100), frozen)
    hoi_b = apply_indicator(build(tmp, "upenn_hoi", "B", 18, 200), frozen)
    afr_b = apply_indicator(build(tmp, "brats_africa", "B", 12, 300), frozen)
    return dict(
        tmp=tmp,
        val_a=val_a,
        val_b=val_b,
        frozen=frozen,
        test_a=test_a,
        test_b=test_b,
        hoi_b=hoi_b,
        afr_b=afr_b,
    )


# ============================================================ units
def test_unit_rows_contents_and_conventions() -> None:
    src = SyntheticSource(2)
    rows = unit_rows(
        case_id="SYNTH_00007",
        group_id="G",
        dataset="validation",
        arm="B",
        condition="-T1c",
        member_probs=src.member_probabilities("SYNTH_00007", ModalitySubset.from_name("-T1c")),
        gt=src.ground_truth("SYNTH_00007"),
    )
    assert [r["region"] for r in rows] == ["WT", "TC", "ET"] and set(rows[0]) == set(UNIT_FIELDS)
    et = rows[2]
    assert et["gt_voxels"] == "0" and et["vol_fail_40"] == ""  # GT ET < 1 mL: ineligible (S5)
    assert et["I"] == "" and et["hd95"] == ""  # I only after C5; HD95 only via the C6 evaluator
    assert float(rows[0]["risk"]) == pytest.approx(1 - float(rows[0]["dice"]))
    with pytest.raises(ProtocolDeviationError):
        unit_rows(
            case_id="x",
            group_id="g",
            dataset="validation",
            arm="B",
            condition="Full",
            member_probs={r: [np.zeros(SHAPE)] * 2 for r in ("WT", "TC", "ET")},
            gt={r: np.zeros(SHAPE, bool) for r in ("WT", "TC", "ET")},
        )


def test_case_loop_resumes_and_never_recomputes(tmp_path: Path) -> None:
    cases, groups = make_cases("SYNTH", 4)
    src = SyntheticSource(2)
    out = tmp_path / "u.csv"

    class CrashError(Exception):
        pass

    def boom(case: str) -> None:
        if case == cases[1]:
            raise CrashError

    with pytest.raises(CrashError):
        evaluate_cases(
            cases=cases,
            group_of=groups,
            dataset="validation",
            arm="B",
            conditions=C5_NAMES,
            source=src,
            out=out,
            on_case=boom,
        )
    assert not out.exists() and (tmp_path / "u.csv.partial.jsonl").is_file()
    before = src.calls
    evaluate_cases(
        cases=cases,
        group_of=groups,
        dataset="validation",
        arm="B",
        conditions=C5_NAMES,
        source=src,
        out=out,
    )
    assert src.calls - before == 2 * len(C5_NAMES)  # only the two unfinished cases
    assert len(read_unit_rows(out)) == 4 * 5 * 3
    evaluate_cases(
        cases=cases,
        group_of=groups,
        dataset="validation",
        arm="B",
        conditions=C5_NAMES,
        source=src,
        out=out,
    )  # completed: returns immediately
    assert src.calls - before == 2 * len(C5_NAMES)


# ============================================================ SR2 / C5
def test_sr2_and_c5_freeze_use_validation_only(study: dict[str, Any]) -> None:
    sr2 = sr2_check(study["val_a"])
    assert sr2["n_cases"] == 16 and sr2["passed"] == (sr2["mean_et_dice"] >= 0.75)
    with pytest.raises(ProtocolDeviationError):
        sr2_check(study["test_a"])  # never test units
    fr = study["frozen"]
    assert set(fr["tau_q"]) == {"0.80", "0.70", "0.90", "0.20"}
    assert fr["tau_q"]["0.80"]["realized_validation_coverage"] >= 0.80
    assert fr["indicator"]["B"]["ET"]["-T1c"]["I"] == pytest.approx(
        -fr["indicator"]["B"]["ET"]["-T1c"]["mean_risk"]
    )
    with pytest.raises(ProtocolDeviationError):
        freeze_c5(study["val_a"], study["test_b"])
    assert all(r["I"] != "" for r in study["test_b"])


# ============================================================ analyses
def test_internal_analysis_structure_and_rules(study: dict[str, Any]) -> None:
    res = internal_analysis(study["test_b"], study["test_a"], study["frozen"], n_replicates=N_REP)
    p = res["primary_HW"]
    assert (
        p["supported"] == (p["ci_high"] < 0) and p["n_replicates"] == N_REP and p["seed"] == 12345
    )
    assert "bca_ci_low" in p and set(res["S1_F1"]) == set(C4_NAMES)
    for d in res["S1_F1"].values():
        assert d["claim_delta_below_zero"] == (d["holm_p"] < 0.05 and d["estimate"] < 0)
        assert d["holm_p"] >= d["p_value_two_sided_approx"]
    assert "p_value_two_sided_approx" not in res["full_control"]  # descriptive control
    assert all("p_value_two_sided_approx" not in v for v in res["S9_F5_armA_descriptive"].values())
    assert set(res["S2_F4"]) == {"TC", "WT"}
    assert res["supporting_B_minus_A_ET_dice"]["full_input"]["margin"] == SUPPORTING_MARGIN
    assert set(res["S12_S13_pooled_armB"]) == {"a_equal_C5", "b_80_full"}
    assert set(res["seed_variation"]["B"]["Full"]) == {"per_seed_mean", "mean", "sd"}


def test_external_transfer_and_families(study: dict[str, Any]) -> None:
    ext = {
        ds: external_analysis(ds, study[k], study["frozen"], n_replicates=N_REP)
        for ds, k in (("upenn_hoi", "hoi_b"), ("brats_africa", "afr_b"))
    }
    assert ext["brats_africa"]["descriptive_only_SR3"]  # 12 < 30 eligible cases (SR3)
    assert not ext["upenn_hoi"]["descriptive_only_SR3"]
    tr = {
        ds: transfer_analysis(study["val_b"], study[k], study["frozen"], n_replicates=N_REP)
        for ds, k in (
            ("internal_test", "test_b"),
            ("upenn_hoi", "hoi_b"),
            ("brats_africa", "afr_b"),
        )
    }
    assert set(tr["internal_test"]) == {"0.80", "0.70", "0.90"}
    fam = assemble_families({}, ext, tr)
    assert set(fam["F2"]) == {"upenn_hoi"} and any("SR3" in d for d in fam["deviations"])
    for d in fam["F3_F3b"].values():
        assert d["unsafe_transfer"] == (d["holm_p_risk"] < 0.05 and d["delta_risk"] > 0)
        assert d["inefficient_transfer"] == (
            d["holm_p_coverage"] < 0.05 and d["delta_coverage"] < 0
        )


def test_weighted_aurc_and_lexicographic() -> None:
    rng = np.random.default_rng(3)
    c, r = rng.random(30), rng.random(30)
    assert weighted_aurc(c, r, np.ones(30)) == pytest.approx(aurc(c, r))
    tied = np.zeros(10)
    assert weighted_aurc(tied, r[:10], np.ones(10)) == pytest.approx(r[:10].mean())
    lex = lexicographic_score(np.array([-0.5, -0.5, -0.2]), np.array([0.1, 0.9, 0.0]))
    assert np.argsort(-lex).tolist() == [2, 1, 0]


def test_failure_analysis_rules(study: dict[str, Any]) -> None:
    cats = categorize(study["test_b"], float(study["frozen"]["tau_q"]["0.20"]["tau"]))
    assert set(cats) == set(C5_NAMES)
    for cond, block in cats.items():
        for case in block["cases"]["hallucinated_ET"]:
            row = next(
                r
                for r in study["test_b"]
                if r["case_id"] == case and r["condition"] == cond and r["region"] == "ET"
            )
            assert row["gt_voxels"] == "0" and int(row["pred_voxels"]) > 0
    chosen = figure_cases(cats)
    assert chosen == figure_cases(cats) and len(chosen) <= 20  # rule-based, seed 7


# ============================================================ study runner
def test_evaluate_set_requires_frozen_and_records_ledger(tmp_path: Path) -> None:
    cases, groups = make_cases("SYNTH", 3)
    srcs = {"A": SyntheticSource(1), "B": SyntheticSource(2)}
    with pytest.raises(DataValidationError, match="frozen"):
        evaluate_set(
            dataset="internal_test",
            cases=cases,
            group_of=groups,
            sources=srcs,
            out_dir=tmp_path,
            arm_conditions={"A": C5_NAMES, "B": C5_NAMES},
        )
    ledger: list[str] = []
    val = evaluate_set(
        dataset="validation",
        cases=cases,
        group_of=groups,
        sources=srcs,
        out_dir=tmp_path,
        arm_conditions={"A": C5_NAMES, "B": C5_NAMES},
    )
    frozen = freeze_c5(read_unit_rows(val["A"]), read_unit_rows(val["B"]))
    out = evaluate_set(
        dataset="internal_test",
        cases=cases,
        group_of=groups,
        sources=srcs,
        out_dir=tmp_path,
        arm_conditions={"A": C5_NAMES, "B": C5_NAMES},
        frozen=frozen,
        record_ledger=ledger.append,
    )
    assert ledger == ["A", "B"] and set(out) == {"A", "B", "B_C15"}
    c15 = read_unit_rows(out["B_C15"])
    assert len({r["condition"] for r in c15}) == 10  # the 15 subsets minus C5


def test_analyze_study_writes_provenance_stamped_outputs(
    study: dict[str, Any], tmp_path: Path
) -> None:
    units = tmp_path / "units"
    units.mkdir()
    from brats_uncertainty.study.units import write_units

    for key, ds, arm in (
        ("val_b", "validation", "B"),
        ("test_b", "internal_test", "B"),
        ("test_a", "internal_test", "A"),
        ("hoi_b", "upenn_hoi", "B"),
        ("afr_b", "brats_africa", "B"),
    ):
        write_units(units / units_filename(ds, arm), study[key])
    frozen = tmp_path / "c5_frozen.json"
    frozen.write_text(json.dumps(study["frozen"]), encoding="utf-8")
    res = analyze_study(
        units_dir=units,
        frozen_path=frozen,
        out_dir=tmp_path / "out",
        git_commit="f" * 40,
        protocol_sha256="a" * 64,
        config_path=REPO_ROOT / "configs/evaluation/evaluation.yaml",
        run_ids=["SYNTHETIC"],
        synthetic=True,
        n_replicates=N_REP,
    )
    assert res["families_complete"] and set(res["datasets"]) == {
        "internal_test",
        "upenn_hoi",
        "brats_africa",
    }
    art = json.loads(
        (tmp_path / "out/analysis/internal_test_analysis.json").read_text(encoding="utf-8")
    )
    assert art["provenance"]["synthetic"] is True and len(art["provenance"]["input_sha256"]) >= 5
    for name in (
        "primary_delta_aurc_forest.png",
        "threshold_transfer_q080.svg",
        "risk_coverage_upenn_hoi.png",
    ):
        assert (tmp_path / "out/figures" / name).is_file()
        assert (tmp_path / "out/figures" / f"{name}.provenance.json").is_file()
    table = (tmp_path / "out/tables/main_results.md").read_text(encoding="utf-8")
    assert "primary H-W" in table and "F2" in table
