"""``evaluate-set`` and ``analyze-study``: run from the clean ``eval-v1`` worktree.

Gate records are read from the live main checkout (``--main-repo``); the code checks
(HEAD is the eval-v1 commit, clean tree) apply to the worktree that runs (guards
``status_root``). The evaluation ledger (SR4) is the main checkout's.
"""

from __future__ import annotations

import importlib
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from brats_uncertainty.evaluation.guards import EVAL_TAG, require_action
from brats_uncertainty.evaluation.ledger import LEDGER_RELPATH, record_evaluation
from brats_uncertainty.preprocessing.modalities import C5_NAMES
from brats_uncertainty.utils.git import git_commit
from brats_uncertainty.utils.io import read_json, read_yaml

ACTIONS = {
    "internal_test": "evaluate_internal_test",
    "upenn_hoi": "evaluate_upenn_hoi",
    "brats_africa": "evaluate_brats_africa",
}
ARM_A_EXTERNAL_REDUCED = ("Full", "-T1c", "-FLAIR")  # SR6 step 1


class _NoOps:
    def __getattr__(self, name: str) -> Any:
        raise RuntimeError(f"no side effects in the tagged command ({name})")


def _context(main_repo: Path, work_dir: Path) -> Any:
    from brats_uncertainty.orchestration.steps import Context, load_master_config

    return Context(
        repo_root=main_repo,
        work_dir=work_dir,
        state_dir=work_dir / "state",
        cfg=load_master_config(main_repo),
        environ=dict(os.environ),
        ops=_NoOps(),
    )


def load_hd95(eval_cfg: dict[str, Any]) -> Callable[..., float] | None:
    spec = (eval_cfg.get("hd95") or {}).get("evaluator")
    if not spec:
        return None
    module, _, func = str(spec).partition(":")
    fn: Callable[..., float] = getattr(importlib.import_module(module), func)
    return fn


def evaluate_set_command(
    worktree: Path, dataset: str, work_dir: Path, out_dir: Path, main_repo: Path
) -> dict[str, Path]:
    from brats_uncertainty.orchestration.steps import crosswalk_rows, split_partitions
    from brats_uncertainty.orchestration.study_steps import (
        AFRICA_RECORD,
        FROZEN_C5,
        _groups,
        _sources,
    )
    from brats_uncertainty.study.run import evaluate_set

    require_action(ACTIONS[dataset], worktree, status_root=main_repo)
    ctx = _context(main_repo, work_dir)
    frozen = read_json(main_repo / FROZEN_C5)
    budget = read_json(main_repo / ctx.cfg["paths"]["exp001_dir"] / "budget_projection.json")
    arm_a = (
        C5_NAMES
        if int(budget["final"]["plan"]["arm_a_external_conditions"]) == 5
        else ARM_A_EXTERNAL_REDUCED
    )
    if dataset == "internal_test":
        cases = split_partitions(ctx)["internal_test"]
        groups = _groups(ctx.splits / "patient_groups_dev.csv")
        conds = {"A": C5_NAMES, "B": C5_NAMES}
    elif dataset == "upenn_hoi":
        hoi = str(
            read_yaml(main_repo / "configs/protocol/protocol_v1.0.yaml")["cohorts"]["hoi_site_id"]
        )
        cases = sorted(r.case_id for r in crosswalk_rows(ctx) if r.site_id == hoi)
        groups = _groups(ctx.splits / "patient_groups_hoi.csv")
        conds = {"A": arm_a, "B": C5_NAMES}
    else:
        cases = list(read_json(main_repo / AFRICA_RECORD)["C3_eligible"])
        groups = {c: c for c in cases}  # distinct patients (§6.2)
        conds = {"A": arm_a, "B": C5_NAMES}
    commit = git_commit(worktree) or ""

    def ledger(arm: str) -> None:
        record_evaluation(main_repo / LEDGER_RELPATH, dataset, arm, commit, EVAL_TAG)

    sources = (
        _africa_sources(ctx, cases) if dataset == "brats_africa" else _sources(ctx, dataset, cases)
    )
    return evaluate_set(
        dataset=dataset,
        cases=cases,
        group_of=groups,
        sources=sources,
        out_dir=out_dir,
        arm_conditions=conds,
        frozen=frozen,
        record_ledger=ledger,
        hd95=load_hd95(read_yaml(worktree / "configs/evaluation/evaluation.yaml")),
    )


def _africa_sources(ctx: Any, cases: list[str]) -> dict[str, Any]:  # pragma: no cover - GPU
    from brats_uncertainty.orchestration.study_steps import AFRICA_CONFIG, _member_folders
    from brats_uncertainty.preprocessing.labels import BRATS_AFRICA_EXPECTED_REGIONS
    from brats_uncertainty.preprocessing.modalities import MODALITIES
    from brats_uncertainty.study.africa import case_files
    from brats_uncertainty.study.nnunet_inference import NnUNetEnsembleSource

    cfg = read_yaml(ctx.repo_root / AFRICA_CONFIG)
    root = Path(ctx.environ[cfg["data_root_env"]])
    files = {c: case_files(root, c, cfg) for c in cases}
    images = {c: [files[c][m] for m in MODALITIES] for c in cases}
    labels = {c: files[c]["label"] for c in cases}
    return {
        arm: NnUNetEnsembleSource(
            _member_folders(ctx, arm), images, labels, BRATS_AFRICA_EXPECTED_REGIONS
        )
        for arm in ("A", "B")
    }


def analyze_study_command(
    worktree: Path, units_dir: Path, frozen: Path, out_dir: Path, main_repo: Path, work_dir: Path
) -> dict[str, Any]:
    from brats_uncertainty.protocol import load_protocol
    from brats_uncertainty.study.run import analyze_study

    require_action("evaluate_internal_test", worktree, status_root=main_repo)
    runs = sorted(
        p.parent.name for p in (work_dir / "nnunet_results" / "MAIN").glob("*/run_manifest.json")
    )
    return analyze_study(
        units_dir=units_dir,
        frozen_path=frozen,
        out_dir=out_dir,
        git_commit=git_commit(worktree) or "",
        protocol_sha256=str(load_protocol(worktree).raw["protocol"]["sha256"]),
        config_path=worktree / "configs/evaluation/evaluation.yaml",
        run_ids=runs,
        repo_root=main_repo,
    )
