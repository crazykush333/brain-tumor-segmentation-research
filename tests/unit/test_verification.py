"""Independent result verification on SYNTHETIC studies (software tests only): the verifier
agrees with production, and every tampered number, table cell, replicate, figure point or
website value is caught. Nothing here is a scientific result."""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from brats_uncertainty.metrics.calibration import case_calibration
from brats_uncertainty.metrics.selective import aurc as production_aurc
from brats_uncertainty.preprocessing.modalities import C4_NAMES, C5_NAMES
from brats_uncertainty.statistics.thresholds import select_tau
from brats_uncertainty.study.freeze import apply_indicator, freeze_c5
from brats_uncertainty.study.inference import evaluate_cases
from brats_uncertainty.study.run import analyze_study
from brats_uncertainty.study.units import read_unit_rows, units_filename, write_units
from brats_uncertainty.uncertainty.scores import u1_pairwise_dice
from brats_uncertainty.verification import independent as ind
from brats_uncertainty.verification import provenance_checks as pc
from brats_uncertainty.verification.model import FAIL, NOT_PERFORMED, OK, PASS, Stage, expect
from brats_uncertainty.verification.verify import (
    MANIFEST,
    Lineage,
    check_public_export,
    check_website,
    consistency_audit,
    verify_scientific,
    write_outputs,
    write_pending,
)
from tests.conftest import REPO_ROOT
from tests.unit.test_study_pipeline import SyntheticSource, make_cases

N_REP = 120
CFG = REPO_ROOT / "configs/evaluation/evaluation.yaml"


# ============================================================ independent arithmetic
def test_independent_aurc_matches_production_including_ties() -> None:
    rng = np.random.default_rng(1)
    for n in (1, 2, 7, 40):
        conf = np.round(rng.random(n), 1)  # many ties
        risk = rng.random(n)
        assert ind.aurc(conf.tolist(), risk.tolist()) == pytest.approx(
            production_aurc(conf, risk), abs=1e-12
        )
    assert ind.aurc([0.5] * 5, [0.1, 0.2, 0.3, 0.4, 0.5]) == pytest.approx(
        0.3
    )  # constant score = mean


def test_independent_unit_metrics_match_production() -> None:
    rng = np.random.default_rng(2)
    masks = [rng.random((6, 6, 4)) > t for t in (0.5, 0.55, 0.6)]
    vox = [int(m.sum()) for m in masks]
    pairs = [int((masks[a] & masks[b]).sum()) for a, b in ((0, 1), (0, 2), (1, 2))]
    assert float(ind.u1_counts(vox, pairs)) == u1_pairwise_dice(masks)
    assert ind.dice_counts(0, 0, 0) == 1 and ind.dice_counts(5, 0, 0) == 0
    prob = rng.random((8, 8, 6)).astype(np.float32)
    gt = rng.random((8, 8, 6)) > 0.8
    from brats_uncertainty.study.units import verification_primitives

    prim = verification_primitives([prob >= 0.5] * 3, prob >= 0.5, gt, prob)
    bins = [
        (int(c), float(sp), int(sy))
        for c, sp, sy in (b.split(":") for b in prim["calibration_bins"].split(";"))
    ]
    ece, brier, n = ind.ece_brier_bins(bins, float(prim["brier_sse"]))
    ref = case_calibration(prob, gt)
    assert n == ref["roi_voxels"]
    assert ece == pytest.approx(ref["ece"], abs=1e-12) and brier == pytest.approx(
        ref["brier"], abs=1e-12
    )


def test_independent_tau_and_holm() -> None:
    rng = np.random.default_rng(3)
    cond = np.repeat(np.array(C4_NAMES), 25)
    u1 = np.round(rng.random(100), 2)
    for q in (0.8, 0.7, 0.9, 0.2):
        t, cov = ind.tau_q(u1.tolist(), cond.tolist(), q, C4_NAMES)
        ref = select_tau(u1, cond, q)
        assert t == ref.tau and float(cov) == pytest.approx(ref.realized_coverage, abs=1e-15)
    from brats_uncertainty.statistics.multiplicity import holm_adjust

    p = {"a": 0.01, "b": 0.04, "c": 0.03, "d": 0.5}
    assert ind.holm(p) == pytest.approx(holm_adjust(p))
    assert ind.percentile([1.0, 2.0, 3.0, 4.0], 0.025) == pytest.approx(
        np.quantile([1, 2, 3, 4], 0.025)
    )


# ============================================================ end-to-end synthetic study
def _build(tmp: Path) -> dict[str, Any]:
    raw, units = tmp / "raw", tmp / "units"
    raw.mkdir(parents=True)
    units.mkdir()

    def build(ds: str, arm: str, n: int, start: int, q: float = 1.0) -> list[dict[str, str]]:
        cases, groups = make_cases("SYNTH", n, start)
        out = raw / units_filename(ds, arm)
        evaluate_cases(
            cases=cases,
            group_of=groups,
            dataset=ds,
            arm=arm,
            conditions=C5_NAMES,
            source=SyntheticSource(1 if arm == "A" else 2, q),
            out=out,
        )
        return read_unit_rows(out)

    va, vb = build("validation", "A", 14, 0, 3.0), build("validation", "B", 14, 0)
    frozen = freeze_c5(va, vb)
    (tmp / "c5.json").write_text(json.dumps(frozen), encoding="utf-8")
    data = {("validation", "A"): va, ("validation", "B"): vb}
    for ds, start, n in (
        ("internal_test", 100, 16),
        ("upenn_hoi", 200, 14),
        ("brats_africa", 300, 10),
    ):
        for arm in ("A", "B"):
            data[(ds, arm)] = apply_indicator(
                build(ds, arm, n, start, 3.0 if arm == "A" else 1.0), frozen
            )
    for (ds, arm), rows in data.items():
        write_units(units / units_filename(ds, arm), rows)
    return {"units": units, "frozen": tmp / "c5.json"}


def _analyze(env: dict[str, Any], out: Path) -> None:
    analyze_study(
        units_dir=env["units"],
        frozen_path=env["frozen"],
        out_dir=out,
        git_commit="f" * 40,
        protocol_sha256="a" * 64,
        config_path=CFG,
        run_ids=["SYNTHETIC"],
        synthetic=True,
        n_replicates=N_REP,
    )


LINEAGE = Lineage(
    "m" * 64,
    "c" * 64,
    "u" * 64,
    "s" * 64,
    "g" * 64,
    "h" * 64,
    {"A": ["a0", "a1", "a2"], "B": ["b0", "b1", "b2"]},
    ["e" * 64],
    "a" * 64,
)


def _prov() -> list[Stage]:
    return [
        Stage(s, s, [expect("SYNTHETIC fixture provenance", True)]).finish()
        for s in ("DATA", "SPLIT", "RUNS", "CHECKPOINTS", "EXTERNAL")
    ]


def _verify(env: dict[str, Any], analysis: Path, tmp: Path, rerun: bool = True) -> Any:
    return verify_scientific(
        units_dir=env["units"],
        frozen_path=env["frozen"],
        analysis_out=analysis,
        out_dir=tmp / "ver",
        provenance_stages=_prov(),
        lineage=LINEAGE,
        rerun=(lambda o: _analyze(env, o)) if rerun else None,
        rerun_dir=tmp / f"rerun_{analysis.name}",
        expected_replicates=N_REP,
    )


@pytest.fixture(scope="module")
def study(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    tmp = tmp_path_factory.mktemp("vstudy")
    env = _build(tmp)
    _analyze(env, tmp / "analysis")
    env["tmp"], env["analysis"] = tmp, tmp / "analysis"
    env["result"] = _verify(env, tmp / "analysis", tmp)
    return env


def test_clean_synthetic_study_verifies(study: dict[str, Any]) -> None:
    res = study["result"]
    assert res.scientific_status == "VERIFIED", {k: v.status for k, v in res.stages.items()}
    assert res.stages["CLEAN_ENV"].status == NOT_PERFORMED  # recorded honestly, never faked
    assert res.rerun["comparison_status"] == PASS
    assert res.rerun["first_run_hash"] == res.rerun["second_run_hash"]
    idx = res.result_index
    assert {
        "PRIMARY-HW-C4-ET-DELTA-AURC",
        "F1-MINUS-T1C-ET-DELTA-AURC",
        "FULL-CONTROL-ET-DELTA-AURC",
    } <= set(idx)
    internal = json.loads((study["analysis"] / "analysis/internal_test_analysis.json").read_text())[
        "payload"
    ]
    assert idx["PRIMARY-HW-C4-ET-DELTA-AURC"]["estimate"] == pytest.approx(
        internal["primary_HW"]["estimate"], abs=1e-12
    )
    assert all(r["verification_status"] == "VERIFIED" for r in res.records)
    assert all(a["answer"] in (PASS, "NOT_APPLICABLE", FAIL) for a in consistency_audit(res.stages))


def _tampered(study: dict[str, Any], name: str) -> Path:
    dst = study["tmp"] / f"tamper_{name}"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(study["analysis"], dst)
    return dst


def _edit_csv(path: Path, row: int, col: str, value: str) -> None:
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    rows[row][col] = value
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


@pytest.mark.parametrize(
    ("what", "stage"),
    [
        ("table_cell", "TABLES"),
        ("replicate", "BOOTSTRAP"),
        ("figure_point", "FIGURES"),
        ("primary_estimate", "PRIMARY_AURC"),
        ("failure_list", "FAILURES"),
    ],
)
def test_every_tampering_is_caught(study: dict[str, Any], what: str, stage: str) -> None:
    a = _tampered(study, what)
    if what == "table_cell":
        _edit_csv(a / "tables/main_results.csv", 0, "estimate", "-0.5")
    elif what == "replicate":
        _edit_csv(a / "bootstrap/bootstrap_replicates_primary.csv", 3, "ET:-T1c", "0.123")
    elif what == "figure_point":
        p = next((a / "figures").glob("risk_coverage_internal_test.csv"))
        _edit_csv(p, 2, "selective_risk", "0.999")
    else:
        p = (
            a
            / "analysis"
            / (
                "internal_test_analysis.json"
                if what == "primary_estimate"
                else "failure_analysis.json"
            )
        )
        body = json.loads(p.read_text(encoding="utf-8"))
        if what == "primary_estimate":  # e.g. Full accidentally pooled into the C4 mean
            per = body["payload"]["S1_F1"]
            body["payload"]["primary_HW"]["estimate"] = (
                sum(per[c]["estimate"] for c in C4_NAMES)
                + body["payload"]["full_control"]["estimate"]
            ) / 5
        else:
            cats = body["payload"]["categories"]["internal_test"]["Full"]["cases"]
            cats["hallucinated_ET"] = [*cats["hallucinated_ET"], "SYNTH_99999"]
        p.write_text(json.dumps(body), encoding="utf-8")
    res = _verify(study, a, study["tmp"], rerun=False)
    assert res.stages[stage].status == FAIL
    assert res.scientific_status == "BLOCKED"


def test_tampered_unit_metric_is_caught(study: dict[str, Any], tmp_path: Path) -> None:
    env = dict(study)
    units = tmp_path / "units"
    shutil.copytree(study["units"], units)
    p = units / units_filename("internal_test", "B")
    _edit_csv(p, 5, "dice", "0.5")
    env["units"] = units
    res = verify_scientific(
        units_dir=units,
        frozen_path=study["frozen"],
        analysis_out=study["analysis"],
        out_dir=tmp_path / "v",
        provenance_stages=_prov(),
        lineage=LINEAGE,
        rerun=None,
        rerun_dir=tmp_path / "r",
        expected_replicates=N_REP,
    )
    assert res.stages["METRICS"].status == FAIL


def test_missing_lineage_blocks(study: dict[str, Any], tmp_path: Path) -> None:
    lin = Lineage(
        None, "c" * 64, "u" * 64, "s" * 64, "g" * 64, None, {"B": ["b0"]}, ["e"], "a" * 64
    )
    res = verify_scientific(
        units_dir=study["units"],
        frozen_path=study["frozen"],
        analysis_out=study["analysis"],
        out_dir=tmp_path / "v",
        provenance_stages=_prov(),
        lineage=lin,
        rerun=None,
        rerun_dir=tmp_path / "r",
        expected_replicates=N_REP,
    )
    assert res.stages["LINEAGE"].status == FAIL and res.scientific_status == "BLOCKED"


def test_wrong_replicate_count_or_unverified_provenance_blocks(
    study: dict[str, Any], tmp_path: Path
) -> None:
    res = verify_scientific(
        units_dir=study["units"],
        frozen_path=study["frozen"],
        analysis_out=study["analysis"],
        out_dir=tmp_path / "v",
        provenance_stages=_prov(),
        lineage=LINEAGE,
        rerun=None,
        rerun_dir=tmp_path / "r",
    )  # protocol requires 10,000
    assert res.stages["BOOTSTRAP"].status == FAIL
    bad = [*_prov()[:-1], pc.not_applicable("EXTERNAL", "x", "y")]
    bad[0] = Stage("DATA", "d", [pc.Check("training tree present", NOT_PERFORMED)]).finish()
    res2 = verify_scientific(
        units_dir=study["units"],
        frozen_path=study["frozen"],
        analysis_out=study["analysis"],
        out_dir=tmp_path / "v2",
        provenance_stages=bad,
        lineage=LINEAGE,
        rerun=None,
        rerun_dir=tmp_path / "r2",
        expected_replicates=N_REP,
    )
    assert res2.stages["DATA"].status == FAIL and res2.scientific_status == "BLOCKED"


# ============================================================ website / export / outputs
def _page(index: dict[str, Any], *, digits: int = 3, extra: str = "") -> str:
    cells = "".join(
        f'<span data-result-id="{rid}" data-field="{f}" data-value="{v[f]!r}">'
        f"{v[f]:.{digits}f}</span>"
        for rid, v in index.items()
        for f in ("estimate", "ci_low", "ci_high")
        if f in v
    )
    return f"<html><body><h1>Results</h1>{cells}{extra}</body></html>"


def test_website_check(study: dict[str, Any]) -> None:
    res = study["result"]
    assert check_website(_page(res.result_index), res).status in OK
    assert check_website(_page(res.result_index, digits=2), res).status == FAIL  # display rounding
    assert check_website(_page(res.result_index, extra="<p>SYNTHETIC DEMO</p>"), res).status == FAIL
    stale = _page({"OLD-RESULT": {"estimate": 0.1}})
    assert check_website(stale, res).status == FAIL  # number not in the verified index
    blocked = type(res)(
        res.stages | {"DATA": Stage("DATA", "d", status=FAIL)}, res.result_index, [], {}, ""
    )
    assert (
        check_website(_page(res.result_index), blocked).status == FAIL
    )  # shown before verification
    assert (
        check_website("<p>Scientific results are being independently verified.</p>", blocked).status
        in OK
    )


def test_public_export_and_outputs(study: dict[str, Any], tmp_path: Path) -> None:
    res = study["result"]
    good = tmp_path / "results/public-safe/analysis.json"
    good.parent.mkdir(parents=True)
    good.write_text('{"a": 1}', encoding="utf-8")
    st, hashes = check_public_export([good], tmp_path)
    assert st.status in OK and list(hashes) == ["results/public-safe/analysis.json"]
    demo = tmp_path / "results/public-safe/x.json"
    demo.write_text(json.dumps({"demo": True, "synthetic": True}), encoding="utf-8")
    assert check_public_export([good, demo], tmp_path)[0].status == FAIL
    res.stages["WEBSITE"] = check_website(_page(res.result_index), res)
    res.stages["PUBLIC_EXPORT"] = st
    paths = write_outputs(res, tmp_path / "ver", tmp_path / "REPORT.md", hashes)
    man = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    assert man["overall"] == "VERIFIED" and man["result_index"]
    cert = paths["certificate"].read_text(encoding="utf-8")
    assert "Overall verification: VERIFIED" in cert and "Reproducibility rerun | PASS" in cert
    assert "not a scientific result page" in paths["dashboard"].read_text(encoding="utf-8")
    assert len(json.loads(paths["audit"].read_text())["questions"]) == 23


def test_pending_state_never_claims_pass(tmp_path: Path) -> None:
    write_pending(tmp_path / "ver", tmp_path / "REPORT.md", "No real result exists yet.")
    man = json.loads((tmp_path / "ver/verification_manifest.json").read_text(encoding="utf-8"))
    assert man["overall"] == "NOT_RUN" and man["result_index"] == {}
    assert all(s["status"] == "NOT_RUN" for s in man["stages"])
    assert "BLOCKED" in (tmp_path / "ver/RESULT_VERIFICATION_CERTIFICATE.md").read_text(
        encoding="utf-8"
    )
    assert ">PASS<" not in (tmp_path / "ver/index.html").read_text(encoding="utf-8")
    for name in ("table_verification.csv", "public_artifact_hashes.json", "consistency_audit.json"):
        assert (tmp_path / "ver" / name).is_file()
    audit = json.loads((tmp_path / "ver/consistency_audit.json").read_text(encoding="utf-8"))
    assert len(audit["questions"]) == 23
    assert {q["answer"] for q in audit["questions"]} == {"NOT_RUN"}
    assert "production 0.30 vs independent recomputation 0.32" in (
        tmp_path / "REPORT.md"
    ).read_text(encoding="utf-8")


def test_site_export_publishes_values_only_when_verified(tmp_path: Path) -> None:
    from brats_uncertainty.errors import ProvenanceError
    from brats_uncertainty.results.site_export import verification_state

    assert verification_state(tmp_path, available=False)["result_index"] == {}
    assert verification_state(tmp_path, available=False)["scientific_status"] == "NOT_RUN"
    with pytest.raises(ProvenanceError, match="independent verification"):
        verification_state(tmp_path, available=True)  # published without verification
    man = tmp_path / "results/verification/verification_manifest.json"
    man.parent.mkdir(parents=True)
    index = {"PRIMARY-HW-C4-ET-DELTA-AURC": {"estimate": -0.01}}
    for status, idx, available, ok in (
        ("BLOCKED", {}, True, False),
        ("BLOCKED", index, False, False),  # an unverified manifest must not carry values
        ("VERIFIED", {}, False, False),
        ("VERIFIED", index, False, True),
        ("VERIFIED", index, True, True),
    ):
        man.write_text(
            json.dumps({"scientific_status": status, "overall": status, "result_index": idx}),
            encoding="utf-8",
        )
        if not ok:
            with pytest.raises(ProvenanceError):
                verification_state(tmp_path, available=available)
            continue
        shown = verification_state(tmp_path, available=available)["result_index"]
        assert shown == (index if available else {})  # values only once published


# ============================================================ provenance checks (synthetic)
def test_data_check_reenumerates_and_catches_changes(tmp_path: Path) -> None:
    root = tmp_path / "TrainingSet"
    for cid in ("BraTS2021_99990", "BraTS2021_99991"):
        d = root / "SYNTH" / cid
        d.mkdir(parents=True)
        for suf in ("t1", "t1ce", "t2", "flair", "seg"):
            (d / f"{cid}_{suf}.nii.gz").write_bytes(f"SYNTHETIC {cid} {suf}".encode())
    found = pc.enumerate_tree(root)
    mod = {"t1": "T1", "t1ce": "T1c", "t2": "T2", "flair": "FLAIR", "seg": None}
    files = [
        {
            "relpath": r,
            "size_bytes": s,
            "sha256": h,
            "case_id": Path(r).parent.name,
            "modality": mod[Path(r).name.split("_")[-1].split(".")[0]],
            "file_type": "label" if r.endswith("seg.nii.gz") else "image",
        }
        for r, (s, h) in found.items()
    ]
    inv = [
        type("E", (), {"relpath": f"PKG/TS/{r}", "size_bytes": s, "sha256": h})()
        for r, (s, h) in found.items()
    ]
    kw = dict(
        manifest={"files": files},
        inventory=inv,
        data_root_reference="PKG/TS",
        metadata_files={},
        crosswalk_case_ids=["BraTS2021_99990", "BraTS2021_99991"],
    )
    st = pc.check_data(training_root=root, **kw)
    assert all(c.status == PASS for c in st.checks if "count" not in c.name)
    (root / "SYNTH/BraTS2021_99990/BraTS2021_99990_t2.nii.gz").write_bytes(b"changed")
    st2 = pc.check_data(training_root=root, **kw)
    assert any(c.status == FAIL and "hash" in c.name for c in st2.checks)
    assert pc.check_data(training_root=None, **kw).status == FAIL


def test_run_check_catches_shared_or_mismatched_checkpoints(tmp_path: Path) -> None:
    import hashlib

    manifests, dirs = {}, {}
    expected = {f"JOB-0{i + 2}": ("A" if i < 3 else "B", i % 3, "T") for i in range(6)}
    for job, (arm, seed, tr) in expected.items():
        d = tmp_path / job
        (d / "f").mkdir(parents=True)
        ck = d / "f/checkpoint_final.pth"
        ck.write_bytes(f"SYNTHETIC {job}".encode())
        dirs[job] = d
        manifests[job] = {
            "arm": arm,
            "seed": seed,
            "trainer": tr,
            "status": "COMPLETED",
            "git_commit": "c",
            "dataset_manifest_sha256": "m",
            "split_sha256": "s",
            "checkpoint": {
                "path": "f/checkpoint_final.pth",
                "sha256": hashlib.sha256(ck.read_bytes()).hexdigest(),
            },
            "attempts": [{"environment_hash": "e", "git_commit": "c"}],
        }
    kw = dict(run_dirs=dirs, expected=expected, manifest_sha256="m", split_sha256="s")
    assert pc.check_runs(run_manifests=manifests, **kw).status == PASS
    (dirs["JOB-03"] / "f/checkpoint_final.pth").write_bytes(
        b"SYNTHETIC JOB-02"
    )  # copied between seeds
    assert pc.check_runs(run_manifests=manifests, **kw).status == FAIL
    manifests["JOB-04"]["status"] = "INVALIDATED"
    assert pc.check_runs(run_manifests=manifests, **kw).status == FAIL


# ============================================================ orchestration gating
def test_blocked_verification_publishes_nothing(
    study: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from brats_uncertainty.orchestration import study_steps as ss
    from brats_uncertainty.orchestration.steps import StepFailed
    from brats_uncertainty.verification.model import Check
    from brats_uncertainty.verification.run import load_result, save_result
    from tests.unit.test_orchestration import FakeOps, make_ctx

    ops = FakeOps()
    ctx = make_ctx(tmp_path, ops)
    path = ctx.work_dir / "verification/verification_result.json"
    save_result(study["result"], path)
    res = load_result(path)
    res.stages["PRIMARY_AURC"].checks.append(
        Check("ET ΔAURC -T1c", FAIL, -0.012, -0.011, 0.001, 0.09, "SYNTHETIC tamper")
    )
    res.stages["PRIMARY_AURC"].finish()
    save_result(res, path)
    status_changes: list[Any] = []
    monkeypatch.setattr(ss, "_set_status", lambda *a, **k: status_changes.append(a))
    with pytest.raises(StepFailed) as exc:
        ss.execute_verify(ctx)
    assert "BLOCKED RESULT: PRIMARY_AURC" in exc.value.action
    assert "EXACT DISCREPANCY: ET ΔAURC -T1c" in exc.value.action
    assert "REQUIRED RERUN" in exc.value.action
    assert not (ctx.repo_root / "results/public-safe").exists()
    assert not (ctx.repo_root / "results/index.json").exists()
    assert not status_changes  # results never marked available
    man = json.loads((ctx.repo_root / ss.VERIFICATION_DIR / MANIFEST).read_text(encoding="utf-8"))
    assert man["scientific_status"] == "BLOCKED" and man["result_index"] == {}
    assert any(c[0] == "milestone" and "BLOCKED" in c[1] for c in ops.calls)


def test_retract_removes_publication(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from brats_uncertainty.orchestration import study_steps as ss
    from tests.unit.test_orchestration import make_ctx

    ctx = make_ctx(tmp_path)
    pub = ctx.repo_root / "results/public-safe/analysis/internal_test_analysis.json"
    pub.parent.mkdir(parents=True)
    pub.write_text("{}", encoding="utf-8")
    (ctx.repo_root / "results/index.json").write_text("{}", encoding="utf-8")
    changes: list[Any] = []
    monkeypatch.setattr(ss, "_set_status", lambda _ctx, upd, **k: changes.append(upd))
    ss.retract(ctx)
    assert not pub.exists() and not (ctx.repo_root / "results/index.json").exists()
    assert changes[0][("results", "available")] is False
    assert changes[0][("results", "statement")] == (
        "Scientific results are being independently verified."
    )


def test_final_audit_verdict_requires_full_verification() -> None:
    from brats_uncertainty.orchestration.audit import final_status

    assert final_status(False, None).startswith("NOT VERIFIED - no real scientific result")
    assert final_status(False, {"overall": "NOT_RUN", "scientific_status": "NOT_RUN"}).startswith(
        "NOT VERIFIED"
    )
    blocked = {"overall": "BLOCKED", "scientific_status": "VERIFIED"}  # website check failed
    assert final_status(True, blocked).startswith("NOT VERIFIED")
    assert final_status(False, {"overall": "VERIFIED", "scientific_status": "VERIFIED"}) != (
        "REAL RESULTS VERIFIED"
    )
    verified = {"overall": "VERIFIED", "scientific_status": "VERIFIED"}
    assert final_status(True, verified) == "REAL RESULTS VERIFIED"


def test_verified_internal_results_never_claim_external_evaluation(
    study: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verified internal results with external prerequisites still blocked: the external
    section stays NOT_STARTED and the public statement says the external evaluation is
    pending (no external result is implied)."""
    from brats_uncertainty.orchestration import study_steps as ss
    from brats_uncertainty.verification.run import save_result
    from tests.unit.test_orchestration import FakeOps, make_ctx

    ctx = make_ctx(tmp_path, FakeOps())
    save_result(study["result"], ctx.work_dir / "verification/verification_result.json")
    dest = ctx.repo_root / "results/public-safe/analysis"
    dest.mkdir(parents=True)
    (dest / "internal_test_analysis.json").write_text("{}", encoding="utf-8")  # internal only
    changes: list[dict[Any, Any]] = []
    monkeypatch.setattr(ss, "_set_status", lambda _ctx, upd, **k: changes.append(upd))
    ss.execute_verify(ctx)
    merged = {k: v for c in changes for k, v in c.items()}
    assert merged[("evaluation", "internal")] == "COMPLETED"
    assert merged[("evaluation", "external")] == "NOT_STARTED"
    assert (
        "External evaluation pending for: brats_africa, upenn_hoi"
        in merged[("results", "statement")]
    )
