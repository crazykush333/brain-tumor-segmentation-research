"""Study-level runners: evaluate one dataset (units) and analyse all units (artifacts).

``evaluate_set`` turns ensemble predictions into per-unit rows for one dataset and
both arms (arm B also C15 on the internal test, S10). Test and external sets are
recorded once in the evaluation ledger first (SR4) and run only under their research
gates from the ``eval-v1`` checkout. ``analyze_study`` computes every pre-registered
analysis from the unit files and the frozen C5 record and writes provenance-stamped
artifacts, figures and tables. Neither invents a value: a missing input stops it.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from brats_uncertainty.errors import DataValidationError
from brats_uncertainty.preprocessing.modalities import C5_NAMES, all_subsets
from brats_uncertainty.results.artifacts import ArtifactProvenance, ResultArtifact, write_artifact
from brats_uncertainty.study.analysis import (
    assemble_families,
    external_analysis,
    internal_analysis,
    transfer_analysis,
)
from brats_uncertainty.study.failure import categorize, figure_cases
from brats_uncertainty.study.figures import (
    figure_primary_forest,
    figure_risk_coverage,
    figure_transfer,
    table_rows,
    write_tables,
)
from brats_uncertainty.study.freeze import apply_indicator
from brats_uncertainty.study.inference import EnsembleSource, evaluate_cases
from brats_uncertainty.study.units import Hd95Fn, read_unit_rows, units_filename, write_units
from brats_uncertainty.utils.hashing import sha256_file
from brats_uncertainty.utils.io import read_json

EVAL_CONFIG = Path("configs/evaluation/evaluation.yaml")
C15_NAMES = tuple(s.name for s in all_subsets())


def evaluate_set(
    *,
    dataset: str,
    cases: Sequence[str],
    group_of: Mapping[str, str],
    sources: Mapping[str, EnsembleSource],
    out_dir: Path,
    arm_conditions: Mapping[str, Sequence[str]],
    frozen: Mapping[str, Any] | None = None,
    hd95: Hd95Fn | None = None,
    record_ledger: Callable[[str], None] | None = None,
) -> dict[str, Path]:
    """Units files per arm (and C15 for arm B on the internal test). Resumable per case."""
    if dataset != "validation" and frozen is None:
        raise DataValidationError("test/external evaluation needs the frozen C5 record (I)")
    out: dict[str, Path] = {}
    for arm, conditions in sorted(arm_conditions.items()):
        if record_ledger is not None:
            record_ledger(arm)  # SR4: refused if this (dataset, arm) was evaluated before
        raw = out_dir / f"raw_{units_filename(dataset, arm)}"
        evaluate_cases(
            cases=cases,
            group_of=group_of,
            dataset=dataset,
            arm=arm,
            conditions=conditions,
            source=sources[arm],
            out=raw,
            hd95=hd95,
        )
        final = out_dir / units_filename(dataset, arm)
        if not final.exists():
            rows = read_unit_rows(raw)
            write_units(final, apply_indicator(rows, frozen) if frozen else rows)
        out[arm] = final
    if dataset == "internal_test" and "B" in sources:
        raw = out_dir / f"raw_{units_filename(dataset, 'B', 'C15')}"
        extra = [c for c in C15_NAMES if c not in C5_NAMES]
        evaluate_cases(
            cases=cases,
            group_of=group_of,
            dataset=dataset,
            arm="B",
            conditions=extra,
            source=sources["B"],
            out=raw,
            hd95=hd95,
        )
        out["B_C15"] = raw
    return out


def _provenance(
    inputs: Sequence[Path],
    *,
    git_commit: str,
    protocol_sha256: str,
    config_path: Path,
    synthetic: bool,
) -> ArtifactProvenance:
    return ArtifactProvenance(
        experiment_id="MAIN",
        git_commit=git_commit,
        config_sha256=sha256_file(config_path),
        protocol_sha256=protocol_sha256,
        input_sha256={p.name: sha256_file(p) for p in inputs},
        generated_at=datetime.now(UTC).isoformat(),
        synthetic=synthetic,
    )


def analyze_study(
    *,
    units_dir: Path,
    frozen_path: Path,
    out_dir: Path,
    git_commit: str,
    protocol_sha256: str,
    config_path: Path,
    run_ids: Sequence[str],
    synthetic: bool = False,
    repo_root: Path | None = None,
    n_replicates: int = 10_000,
    seed: int = 12_345,
) -> dict[str, Any]:
    """All analyses from the available unit files; returns the list of written outputs."""
    frozen = read_json(frozen_path)

    def rows(dataset: str, arm: str, subsets: str = "C5") -> list[dict[str, str]] | None:
        p = units_dir / units_filename(dataset, arm, subsets)
        return read_unit_rows(p) if p.is_file() else None

    val_b, int_b, int_a = (
        rows("validation", "B"),
        rows("internal_test", "B"),
        rows("internal_test", "A"),
    )
    if val_b is None or int_b is None or int_a is None:
        raise DataValidationError(
            "validation and internal-test unit files (both arms) are required"
        )
    c15_path = units_dir / f"raw_{units_filename('internal_test', 'B', 'C15')}"
    c15 = read_unit_rows(c15_path) if c15_path.is_file() else None
    used = [frozen_path] + sorted(units_dir.glob("units_*.csv")) + ([c15_path] if c15 else [])
    prov = _provenance(
        used,
        git_commit=git_commit,
        protocol_sha256=protocol_sha256,
        config_path=config_path,
        synthetic=synthetic,
    )
    kw = {"n_replicates": n_replicates, "seed": seed}
    internal = internal_analysis(int_b, int_a, frozen, rows_b_c15=c15, **kw)
    externals = {
        ds: external_analysis(ds, r, frozen, **kw)
        for ds in ("upenn_hoi", "brats_africa")
        if (r := rows(ds, "B")) is not None
    }
    targets = {
        "internal_test": int_b,
        **{ds: r for ds in externals if (r := rows(ds, "B")) is not None},
    }
    transfers = {ds: transfer_analysis(val_b, t, frozen, **kw) for ds, t in targets.items()}
    families = assemble_families(internal, externals, transfers) if len(externals) == 2 else None
    tau020 = float(frozen["tau_q"]["0.20"]["tau"])
    failures = {ds: categorize(t, tau020) for ds, t in targets.items()}
    fig_cases = {ds: figure_cases(c) for ds, c in failures.items()}
    analysis_dir, fig_dir, tab_dir = out_dir / "analysis", out_dir / "figures", out_dir / "tables"
    written: list[Path] = []

    def artifact(name: str, kind: str, payload: dict[str, Any]) -> None:
        art = ResultArtifact(kind=kind, name=name, payload=payload, provenance=prov)
        written.append(write_artifact(analysis_dir / f"{name}.json", art, repo_root=repo_root))

    artifact("internal_test_analysis", "bootstrap_result", internal)
    for ds, e in externals.items():
        artifact(f"{ds}_analysis", "bootstrap_result", e)
    artifact("threshold_transfer", "bootstrap_result", transfers)
    if families is not None:
        artifact("families_F2_F3_F3b", "bootstrap_result", families)
    artifact(
        "failure_analysis", "report", {"categories": failures, "figure_cases_ids_only": fig_cases}
    )
    sidecar = {**prov.__dict__, "run_ids": list(run_ids)}
    written += figure_primary_forest(
        internal, fig_dir / "primary_delta_aurc_forest", sidecar, synthetic=synthetic
    )
    for ds, t in targets.items():
        written += figure_risk_coverage(
            t,
            fig_dir / f"risk_coverage_{ds}",
            sidecar,
            synthetic=synthetic,
            title=f"{ds}: ET risk-coverage, arm B, C4",
        )
    written += figure_transfer(
        transfers, fig_dir / "threshold_transfer_q080", sidecar, synthetic=synthetic
    )
    written += write_tables(
        table_rows(internal, families, externals), tab_dir / "main_results", sidecar
    )
    return {
        "written": [str(p) for p in written],
        "families_complete": families is not None,
        "datasets": sorted(targets),
    }
