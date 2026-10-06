"""C1-C3 (BraTS-Africa verification), C4 (HOI grouping), EXP-001 harness parsing, trainer
selection/registration, stage-status writer, implementation confirmations. SYNTHETIC only."""

from __future__ import annotations

import copy
from pathlib import Path

import numpy as np
import pytest
import yaml

from brats_uncertainty.compute.pilot_harness import (
    NOT_MEASURABLE,
    PilotRecord,
    assemble_measurements,
    constraints_record,
    epoch_stats,
    parse_epoch_times,
    parse_gpu_monitor,
    poly_lr,
    resume_check,
)
from brats_uncertainty.data.crosswalk import CrosswalkRow
from brats_uncertainty.errors import ConfigError, DataValidationError, ProtocolDeviationError
from brats_uncertainty.grouping.similarity import MaskIndex
from brats_uncertainty.models.nnunet import RunSpec, train_command, trainer_for
from brats_uncertainty.models.trainer_registration import SHIM_TEXT, register_trainers
from brats_uncertainty.orchestration.budget import PilotMeasurements
from brats_uncertainty.orchestration.confirmations import (
    CONFIRMATIONS_RELPATH,
    missing_confirmations,
)
from brats_uncertainty.study.africa import require_route, verify_africa
from brats_uncertainty.study.hoi import freeze_hoi_groups, screen_hoi
from tests.conftest import REPO_ROOT

AFRICA_CFG = yaml.safe_load((REPO_ROOT / "configs/dataset/brats_africa.yaml").read_text("utf-8"))


# ============================================================ C1-C3
def _africa_tree(root: Path, ids: list[str], *, drop: dict[str, str] | None = None) -> None:
    lay = AFRICA_CFG["layout"]
    for cid in ids:
        d = root / cid
        d.mkdir(parents=True)
        for suf in (*lay["modality_suffixes"].values(), lay["label_suffix"]):
            if drop and drop.get(cid) == suf:
                continue
            (d / f"{cid}{suf}{lay['file_ending']}").write_bytes(f"SYNTHETIC {cid}{suf}".encode())


def test_africa_needs_an_approved_route() -> None:
    cfg = copy.deepcopy(AFRICA_CFG)
    cfg["source"]["route"] = None
    with pytest.raises(ConfigError, match="no approved data route"):
        require_route(cfg)
    cfg["source"]["route"] = "SYNTHETIC route"
    assert require_route(cfg) == "SYNTHETIC route"
    assert "amendment v1.0-A2" in require_route(AFRICA_CFG)  # owner-approved route (C1)


def test_africa_label_sequence_and_count_checks(tmp_path: Path) -> None:
    ids = ["BraTS-SSA-99991-000", "BraTS-SSA-99992-000", "BraTS-SSA-99993-000"]
    _africa_tree(tmp_path, ids, drop={"BraTS-SSA-99993-000": "-t2f"})
    labels = {
        "BraTS-SSA-99991-000": np.array([0, 1, 2, 3]),
        "BraTS-SSA-99992-000": np.array([0, 2]),
    }

    def load_label(p: Path) -> np.ndarray:
        return labels.get(p.parent.name, np.array([0]))

    res = verify_africa(
        tmp_path,
        [*ids, "BraTS-SSA-99999-000"],
        AFRICA_CFG,
        load_label=load_label,
        image_shape=lambda p: (4, 4, 4),
    )
    assert res["C3_eligible"] == ids[:2] and res["C3_eligible_count"] == 2
    assert res["C1_labels"]["BraTS-SSA-99992-000"]["subregions_present"] == {
        "NETC": False,
        "SNFH": True,
        "ET": False,
    }
    assert res["C2_sequences"]["BraTS-SSA-99993-000"]["missing"] == ["FLAIR"]
    assert res["C2_sequences"]["BraTS-SSA-99999-000"]["complete"] is False
    assert res["descriptive_only_SR3"]  # 2 < 30
    labels["BraTS-SSA-99991-000"] = np.array([0, 4])  # BraTS 2021 ET value: unexpected here
    with pytest.raises(DataValidationError, match="unexpected label values"):
        verify_africa(
            tmp_path, ids, AFRICA_CFG, load_label=load_label, image_shape=lambda p: (4, 4, 4)
        )


def test_africa_layout_mismatch_fails_closed(tmp_path: Path) -> None:
    (tmp_path / "Case_1").mkdir()
    with pytest.raises(DataValidationError, match="layout"):
        verify_africa(
            tmp_path,
            ["Case_1"],
            AFRICA_CFG,
            load_label=lambda p: np.zeros(1),
            image_shape=lambda p: (1,),
        )


# ============================================================ C4
def test_hoi_screen_and_grouping_are_gated_and_human_reviewed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pre_execution_root: Path
) -> None:
    from brats_uncertainty.errors import ResearchGateError
    from brats_uncertainty.study import hoi as hoi_mod

    root = pre_execution_root  # frozen pre-execution snapshot (B9 not passed)

    blob = np.zeros((6, 6, 6), bool)
    blob[1:4, 1:4, 1:4] = True
    masks = {c: MaskIndex.from_mask(c, blob) for c in ("BraTS2021_00001", "BraTS2021_00002")}
    masks["BraTS2021_00003"] = MaskIndex.from_mask("BraTS2021_00003", np.roll(blob, 3, axis=0))
    t = tmp_path / "t_screen.json"
    t.write_text('{"value": 0.9}', encoding="utf-8")
    with pytest.raises(ResearchGateError):
        screen_hoi(root, masks, t, tmp_path / "c4")
    monkeypatch.setattr(hoi_mod, "require_action", lambda action, root: None)
    flagged = screen_hoi(root, masks, t, tmp_path / "c4")
    assert flagged == [("BraTS2021_00001", "BraTS2021_00002")]
    rows = [CrosswalkRow(c, "1", "UPENN-GBM", None) for c in masks]
    with pytest.raises(FileNotFoundError):
        freeze_hoi_groups(root, rows, flagged, None, ("Ayush Kushwaha", "X"), tmp_path / "g.csv")
    reviews = tmp_path / "r.csv"
    reviews.write_text(
        "case_a,case_b,decision,reviewer,round,timestamp,reason\n"
        "BraTS2021_00001,BraTS2021_00002,UNRESOLVED,Ayush Kushwaha,primary,"
        "2000-01-01T00:00:00Z,SYNTHETIC\n",
        encoding="utf-8",
    )
    g = freeze_hoi_groups(root, rows, flagged, reviews, ("Ayush Kushwaha", "X"), tmp_path / "g.csv")
    assert (
        g.case_to_group["BraTS2021_00001"] == g.case_to_group["BraTS2021_00002"]
    )  # UNRESOLVED linked
    assert g.case_to_group["BraTS2021_00003"] != g.case_to_group["BraTS2021_00001"]


# ============================================================ EXP-001 harness
LOG = "\n".join(
    f"2026-01-01: Epoch {e}\n2026-01-01: Current learning rate: {poly_lr(e):.5f}\n"
    f"2026-01-01: Epoch time: {t} s"
    for e, t in zip(range(5), (130.0, 101.0, 99.0, 100.0, 102.0), strict=True)
)


def test_epoch_and_monitor_parsing() -> None:
    assert parse_epoch_times(LOG) == [130.0, 101.0, 99.0, 100.0, 102.0]
    st = epoch_stats(parse_epoch_times(LOG))
    assert st["median_s"] == pytest.approx(100.5) and st["n_epochs"] == 4 and st["sum_s"] == 532.0
    mon = parse_gpu_monitor("95, 9000\n60, 12000\n")
    assert mon["gpu_util_mean"] == 77.5 and mon["peak_mem_gb"] == pytest.approx(12000 / 1024)
    assert not mon["cpu_bound"] and parse_gpu_monitor("50, 1\n")["cpu_bound"]


def test_resume_check_rules() -> None:
    resumed = "\n".join(LOG.split("\n")[9:])  # starts at "Epoch 3"
    ok = resume_check(LOG, resumed, 3, completed=True)
    assert ok["resumed_at_epoch"] == 3 and ok["resume_pass"]
    assert not resume_check(LOG, LOG, 3, completed=True)["resume_pass"]  # restarted at epoch 0
    assert not resume_check(LOG, resumed, 3, completed=False)["resume_pass"]


def test_measurements_assembly_marks_unmeasurable_quantities() -> None:
    rec = PilotRecord(platform="vm", gpu_names=["SYNTHETIC GPU"])
    rec.timings["P2"] = epoch_stats(parse_epoch_times(LOG))
    rec.timings["P5_seed1"] = epoch_stats([130, 104, 103, 105, 102])
    rec.wall_s["P2"] = 600.0
    rec.monitor = parse_gpu_monitor("95, 9000\n")
    rec.resume = {"resume_pass": True}
    rec.infer_s_per_case_condition = 12.0
    rec.quota_h_week = "not applicable: private VM (no quota)"
    rec.peak_mem_fits_default_plan = True
    m = assemble_measurements(rec, planned_cases=592)
    assert "p100_epoch_time_s" in m["not_measurable_on_platform"]
    assert "quota_h_week" not in m["not_measurable_on_platform"]
    assert m["spec_quantities"]["concurrent_2gpu_epoch_time_s"] == NOT_MEASURABLE
    inp = m["projection_inputs"]
    assert inp["overhead_frac"] == pytest.approx((600 - 532) / 532) and inp["quota_h_week"] is None
    PilotMeasurements(**inp)  # feeds the D6 budget directly
    c = constraints_record(["BraTS2021_00001"], {"D3": True, "D5": True})
    assert c["D3"] and c["D4"] and c["D5"]


# ============================================================ trainers
def test_trainer_selection_and_registration(tmp_path: Path) -> None:
    assert trainer_for("B", 250) == "nnUNetTrainer_BratsUnc_250ep_ModalityDropout"
    assert trainer_for("A", 150) == "nnUNetTrainer_BratsUnc_150ep"
    with pytest.raises(ProtocolDeviationError):
        trainer_for("A", 200)  # only 250 or the SR1/SR6 value 150
    cmd = train_command(501, RunSpec("A", 0), trainer=trainer_for("A", 150))
    assert cmd[-1] == "nnUNetTrainer_BratsUnc_150ep"
    shim = register_trainers(tmp_path)
    assert shim.read_text(encoding="utf-8") == SHIM_TEXT
    assert register_trainers(tmp_path) == shim


# ============================================================ stage status / confirmations
def test_stage_status_writer_validates(tmp_path: Path) -> None:
    from brats_uncertainty.evaluation.stage_status import set_stage_fields
    from tests.conftest import make_verbatim_status_repo

    root = make_verbatim_status_repo(tmp_path / "repo")
    with pytest.raises(ConfigError, match="B12"):
        set_stage_fields(root, {("training", "status"): "IN_PROGRESS"})  # B12 not closed
    with pytest.raises(ConfigError, match="cannot be set"):
        set_stage_fields(root, {("data", "acquired"): True})
    assert set_stage_fields(root, {("training", "status"): "NOT_STARTED"}) == []
    changes = set_stage_fields(root, {}, experiments={"EXP-001": "AUTHORIZED"})
    assert changes and "AUTHORIZED" in (root / "docs/project_status.yaml").read_text(
        encoding="utf-8"
    )


def test_confirmations_required_per_step(tmp_path: Path) -> None:
    assert missing_confirmations(tmp_path, "B8") == [5]
    assert missing_confirmations(tmp_path, "TRAIN-A0") == [12, 13]
    p = tmp_path / CONFIRMATIONS_RELPATH
    p.parent.mkdir(parents=True)
    p.write_text(
        "confirmed_by: Ayush Kushwaha\nitems:\n"
        "  5: {confirmed_on: '2000-01-01', decision: CONFIRMED}\n"
        "  12: {confirmed_on: '2000-01-01', decision: CHANGE_REQUESTED}\n",
        encoding="utf-8",
    )
    assert missing_confirmations(tmp_path, "B8") == []
    assert missing_confirmations(tmp_path, "TRAIN-B2") == [12, 13]
