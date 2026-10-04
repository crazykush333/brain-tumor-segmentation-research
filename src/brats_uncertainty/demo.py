"""Synthetic end-to-end demonstration of the result pipeline (NOT scientific results).

``generate_demo`` runs the study's own code (per-unit metrics, the C5 freeze, the
analyses, threshold transfer, failure analysis, figures) on a small deterministic
synthetic toy study (seed ``DEMO_SEED``) to show what the repository and website look
like once the real experiment has run. Nothing here reads BraTS data, private
storage, environment paths or gate records, and nothing it writes can become a
research result:

- every artifact carries ``demo = true``, ``synthetic = true``, ``scientific_result =
  false`` (JSON fields, CSV columns, SVG metadata and a visible label, Markdown header);
- inside the repository it writes only to ``results/demo/`` and refuses every real
  result namespace;
- case IDs are ``SYNTH_*`` (never BraTS IDs) and no dataset hash is recorded;
- the public export and the website results index refuse demo-flagged files.

Bootstrap replicates are reduced (``DEMO_REPLICATES``) to keep the demo fast; the real
analysis uses the protocol's 10,000.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from brats_uncertainty.errors import ProvenanceError
from brats_uncertainty.metrics.selective import risk_coverage_curve
from brats_uncertainty.preprocessing.modalities import C4_NAMES, C5_NAMES, ModalitySubset
from brats_uncertainty.utils.paths import is_within

DEMO_SEED = 20261004
DEMO_REPLICATES = 500
DEMO_LABEL = "SYNTHETIC DEMO — NOT REAL RESULTS"
DISCLAIMER = "Synthetic demonstration only — not a BraTS scientific result."
DEMO_FLAGS: dict[str, Any] = {"demo": True, "synthetic": True, "scientific_result": False}
DEMO_RELPATH = Path("results/demo")
SHAPE = (12, 12, 8)
N_VALIDATION, N_TEST = 24, 32
FILES = (
    "README.md",
    "synthetic_summary.json",
    "synthetic_metrics.csv",
    "synthetic_failure_analysis.csv",
    "synthetic_results_report.md",
    "synthetic_risk_coverage.svg",
    "synthetic_calibration.svg",
    "synthetic_uncertainty_vs_error.svg",
    "synthetic_failure_analysis.svg",
)


# ------------------------------------------------------------------ safety
def check_out_dir(out_dir: Path, repo_root: Path) -> None:
    """Inside the repository only ``results/demo`` is allowed (never a real namespace)."""
    if is_within(out_dir, repo_root) and not is_within(out_dir, repo_root / DEMO_RELPATH):
        raise ProvenanceError(
            f"demo artifacts may be written only to {DEMO_RELPATH.as_posix()}/ inside the "
            "repository, never to a real result namespace"
        )


def is_demo_artifact(path: Path) -> bool:
    """True if a file declares itself a demo/synthetic artifact (JSON, CSV, SVG, MD)."""
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    if path.suffix == ".json":
        try:
            body = json.loads(text)
        except json.JSONDecodeError:
            return False
        return isinstance(body, dict) and bool(body.get("demo") or body.get("synthetic") is True)
    if path.suffix == ".csv":
        header = text.splitlines()[0] if text else ""
        return "demo" in header.split(",") and ",true," in text.replace("True", "true")[:4096]
    return "demo=true" in text or DEMO_LABEL in text


# ------------------------------------------------------------------ synthetic study
class _Source:
    """Deterministic synthetic ensemble: GT blob per case; members = GT + noise that grows
    with the number of missing sequences (arm A is noisier under missingness)."""

    def __init__(self, seed: int, arm: str) -> None:
        self.seed, self.arm = seed, arm

    def _rng(self, case: str, extra: int = 0) -> np.random.Generator:
        return np.random.default_rng([self.seed, int(case.split("_")[-1]), extra, ord(self.arm)])

    def ground_truth(self, case_id: str) -> Mapping[str, NDArray[np.bool_]]:
        rng = self._rng(case_id, 7)
        wt = np.zeros(SHAPE, dtype=bool)
        x, y = rng.integers(1, 5, size=2)
        size = int(rng.integers(4, 7))
        wt[x : x + size, y : y + size, 1:6] = True
        tc = wt.copy()
        tc[x, :, :] = False
        et = tc.copy()
        if int(case_id.split("_")[-1]) % 9 == 0:
            et[:] = False
        return {"WT": wt, "TC": tc, "ET": et}

    def member_probabilities(
        self, case_id: str, subset: ModalitySubset
    ) -> Mapping[str, Sequence[NDArray[np.floating]]]:
        gt = self.ground_truth(case_id)
        hard = float(self._rng(case_id, 11).uniform(0.0, 0.45))  # case difficulty
        missing = len(subset.missing) * (1.6 if self.arm == "A" else 1.0)
        sd = 0.12 + hard + 0.08 * missing + (0.1 if "T1c" in subset.missing else 0.0)
        out: dict[str, list[NDArray[np.floating]]] = {}
        for i, r in enumerate(("WT", "TC", "ET")):
            out[r] = []
            for s in range(3):
                cond = sum(
                    1 << k
                    for k, m in enumerate(("T1", "T1c", "T2", "FLAIR"))
                    if m in subset.missing
                )
                noise = self._rng(case_id, 1000 + 100 * i + 10 * s + cond)
                p = gt[r].astype(np.float32) * 0.85 + noise.normal(0.08, sd, SHAPE)
                out[r].append(np.clip(p, 0.0, 1.0).astype(np.float32))
        return out


def _cases(prefix_start: int, n: int) -> tuple[list[str], dict[str, str]]:
    cases = [f"SYNTH_{i:05d}" for i in range(prefix_start, prefix_start + n)]
    return cases, {c: f"SYNTH_G{int(c[-5:]) // 2:04d}" for c in cases}


def _units(seed: int, arm: str, dataset: str, start: int, n: int) -> list[dict[str, str]]:
    from brats_uncertainty.study.units import unit_rows

    cases, groups = _cases(start, n)
    src = _Source(seed, arm)
    rows: list[dict[str, str]] = []
    for c in cases:
        gt = src.ground_truth(c)
        for name in C5_NAMES:
            rows += unit_rows(
                case_id=c,
                group_id=groups[c],
                dataset=dataset,
                arm=arm,
                condition=name,
                member_probs=src.member_probabilities(c, ModalitySubset.from_name(name)),
                gt=gt,
            )
    return rows


def _reliability(seed: int, n: int) -> dict[str, list[float]]:
    """Voxel reliability (ET, ensemble mean, protocol ROI) per condition, 15 bins."""
    from brats_uncertainty.inference.ensemble import binarize, ensemble_mean
    from brats_uncertainty.metrics.calibration import calibration_roi

    src = _Source(seed, "B")
    cases, _ = _cases(1000, n)
    edges = np.linspace(0, 1, 16)
    out: dict[str, list[float]] = {}
    for cond in ("Full", "-T1c"):
        p_all, y_all = [], []
        for c in cases:
            gt = src.ground_truth(c)["ET"]
            mean = ensemble_mean(src.member_probabilities(c, ModalitySubset.from_name(cond))["ET"])
            roi = calibration_roi(gt, binarize(mean))
            p_all.append(mean[roi])
            y_all.append(gt[roi])
        p, y = np.concatenate(p_all), np.concatenate(y_all)
        idx = np.clip(np.digitize(p, edges[1:-1]), 0, 14)
        out[cond] = [
            float(y[idx == b].mean()) if np.any(idx == b) else float("nan") for b in range(15)
        ]
    out["bin_centers"] = [float(x) for x in (edges[:-1] + edges[1:]) / 2]
    return out


# ------------------------------------------------------------------ figures
def _plt() -> Any:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def _save(fig: Any, path: Path, seed: int) -> Path:
    plt = _plt()
    fig.text(
        0.5,
        0.5,
        DEMO_LABEL,
        ha="center",
        va="center",
        fontsize=18,
        color="red",
        alpha=0.25,
        rotation=20,
        transform=fig.transFigure,
    )
    fig.text(
        0.99, 0.01, f"{DEMO_LABEL} · seed {seed}", ha="right", va="bottom", fontsize=7, color="red"
    )
    with plt.rc_context({"svg.hashsalt": f"demo-{seed}"}):
        fig.savefig(
            path,
            format="svg",
            bbox_inches="tight",
            metadata={
                "Date": None,
                "Description": "demo=true synthetic=true scientific_result=false",
            },
        )
    plt.close(fig)
    return path


def _fig_risk_coverage(rows: Sequence[Mapping[str, str]], path: Path, seed: int) -> Path:
    plt = _plt()
    fig, axes = plt.subplots(1, 4, figsize=(13, 3.4), sharey=True)
    for ax, cond in zip(axes, C4_NAMES, strict=True):
        sel = [r for r in rows if r["region"] == "ET" and r["condition"] == cond]
        u1 = np.asarray([float(r["U1"]) for r in sel])
        risk = np.asarray([float(r["risk"]) for r in sel])
        curve = risk_coverage_curve(u1, risk)
        ax.plot(curve.coverage, curve.selective_risk, label="U1 (ensemble agreement)")
        ax.axhline(float(risk.mean()), color="grey", ls="--", lw=1, label="I (random ranking)")
        ax.set_title(f"{cond} (synthetic, n={len(sel)})", fontsize=9)
        ax.set_xlabel("Coverage")
    axes[0].set_ylabel("Selective risk (1 − ET Dice)")
    axes[0].legend(frameon=False, fontsize=7)
    return _save(fig, path, seed)


def _fig_calibration(rel: Mapping[str, list[float]], path: Path, seed: int) -> Path:
    plt = _plt()
    fig, ax = plt.subplots(figsize=(4.2, 4))
    ax.plot([0, 1], [0, 1], color="grey", ls="--", lw=1, label="perfect calibration")
    for cond in ("Full", "-T1c"):
        ax.plot(rel["bin_centers"], rel[cond], marker="o", ms=3, label=cond)
    ax.set_xlabel("Ensemble-mean ET probability (15 bins)")
    ax.set_ylabel("Observed ET frequency")
    ax.legend(frameon=False, fontsize=8)
    return _save(fig, path, seed)


def _fig_uncertainty_vs_error(rows: Sequence[Mapping[str, str]], path: Path, seed: int) -> Path:
    plt = _plt()
    fig, ax = plt.subplots(figsize=(5, 4))
    for cond in C4_NAMES:
        sel = [r for r in rows if r["region"] == "ET" and r["condition"] == cond]
        ax.scatter(
            [float(r["U1"]) for r in sel],
            [float(r["dice"]) for r in sel],
            s=12,
            alpha=0.7,
            label=cond,
        )
    ax.set_xlabel("U1 (mean pairwise Dice of the 3 members)")
    ax.set_ylabel("ET Dice")
    ax.legend(frameon=False, fontsize=8)
    return _save(fig, path, seed)


def _fig_failures(failures: Mapping[str, Any], path: Path, seed: int) -> Path:
    plt = _plt()
    cats = ("confident_failure", "hallucinated_ET", "missed_ET")
    conds = list(failures)
    fig, ax = plt.subplots(figsize=(6, 3.4))
    width = 0.25
    for k, cat in enumerate(cats):
        ax.bar(
            np.arange(len(conds)) + (k - 1) * width,
            [failures[c]["counts"][cat] for c in conds],
            width,
            label=cat.replace("_", " "),
        )
    ax.set_xticks(range(len(conds)), conds)
    ax.set_ylabel("Cases (synthetic)")
    ax.legend(frameon=False, fontsize=8)
    return _save(fig, path, seed)


# ------------------------------------------------------------------ generator
def code_sha256(repo_root: Path) -> str:
    """Hash of the package source (verifiable in any copy of the repository)."""
    h = hashlib.sha256()
    for p in sorted((repo_root / "src/brats_uncertainty").rglob("*.py")):
        h.update(p.relative_to(repo_root).as_posix().encode())
        h.update(p.read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()


def _csv(path: Path, fields: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=[*fields, "demo", "synthetic", "scientific_result", "disclaimer"],
            lineterminator="\n",
        )
        w.writeheader()
        for r in rows:
            w.writerow(
                {
                    **{k: r.get(k, "") for k in fields},
                    "demo": "true",
                    "synthetic": "true",
                    "scientific_result": "false",
                    "disclaimer": DISCLAIMER,
                }
            )


def _r(x: float) -> float:
    return float(round(x, 6))


def generate_demo(
    out_dir: Path,
    *,
    repo_root: Path,
    seed: int = DEMO_SEED,
    n_replicates: int = DEMO_REPLICATES,
    git_commit: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    from brats_uncertainty.study.analysis import internal_analysis, transfer_analysis
    from brats_uncertainty.study.failure import categorize
    from brats_uncertainty.study.freeze import apply_indicator, freeze_c5
    from brats_uncertainty.utils.git import git_commit as head_commit

    check_out_dir(out_dir, repo_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    provenance = {
        **DEMO_FLAGS,
        "label": DEMO_LABEL,
        "disclaimer": DISCLAIMER,
        "demo_seed": seed,
        "git_commit": git_commit if git_commit is not None else head_commit(repo_root),
        "code_sha256": code_sha256(repo_root),
        "generated_at": generated_at or datetime.now(UTC).replace(microsecond=0).isoformat(),
        "bootstrap_replicates": n_replicates,
        "data": (
            "deterministic synthetic toy volumes (SYNTH_* cases); "
            "no BraTS, UPenn or BraTS-Africa data"
        ),
    }
    val = {arm: _units(seed, arm, "validation", 0, N_VALIDATION) for arm in ("A", "B")}
    frozen = freeze_c5(val["A"], val["B"])
    test = {
        arm: apply_indicator(_units(seed, arm, "internal_test", 500, N_TEST), frozen)
        for arm in ("A", "B")
    }
    analysis = internal_analysis(
        test["B"], test["A"], frozen, n_replicates=n_replicates, seed=12345
    )
    transfer = transfer_analysis(val["B"], test["B"], frozen, n_replicates=n_replicates, seed=12345)
    failures = categorize(test["B"], float(frozen["tau_q"]["0.20"]["tau"]))
    p = analysis["primary_HW"]
    summary = {
        **provenance,
        "synthetic_study": {
            "validation_cases": N_VALIDATION,
            "test_cases": N_TEST,
            "conditions": list(C5_NAMES),
        },
        "example_primary_statistic": {
            "name": "mean over C4 of ET Delta-AURC (U1 vs I), synthetic test set, arm B",
            "estimate": _r(p["estimate"]),
            "ci_low": _r(p["ci_low"]),
            "ci_high": _r(p["ci_high"]),
            "note": DISCLAIMER,
        },
        "example_delta_aurc_by_condition": {
            c: _r(v["estimate"]) for c, v in analysis["S1_F1"].items()
        },
        "example_tau_q": {q: _r(v["tau"]) for q, v in frozen["tau_q"].items()},
        "example_threshold_transfer_q080": {
            "delta_risk": _r(transfer["0.80"]["delta_risk"]["estimate"]),
            "delta_coverage": _r(transfer["0.80"]["delta_coverage"]["estimate"]),
            "validation_coverage": _r(transfer["0.80"]["validation_coverage"]),
            "target_coverage": _r(transfer["0.80"]["target_coverage"]),
        },
        "example_mean_ece_et": {
            c: _r(analysis["descriptive_armB"][c]["ET"]["ece"]["estimate"])
            for c in C5_NAMES
            if "ece" in analysis["descriptive_armB"][c]["ET"]
        },
        "example_failure_counts": {c: v["counts"] for c, v in failures.items()},
        "files": list(FILES),
    }
    (out_dir / "synthetic_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    metric_fields = (
        "case_id",
        "group_id",
        "arm",
        "condition",
        "region",
        "dice",
        "risk",
        "U1",
        "I",
        "ece",
        "brier",
        "gt_voxels",
        "pred_voxels",
    )
    rows = [{**r, "dataset": "synthetic_test"} for arm in ("A", "B") for r in test[arm]]
    _csv(out_dir / "synthetic_metrics.csv", metric_fields, rows)
    fail_rows = [
        {"condition": c, "category": k, "count": n}
        for c, v in failures.items()
        for k, n in v["counts"].items()
    ]
    _csv(out_dir / "synthetic_failure_analysis.csv", ("condition", "category", "count"), fail_rows)
    _fig_risk_coverage(test["B"], out_dir / "synthetic_risk_coverage.svg", seed)
    _fig_calibration(_reliability(seed, 12), out_dir / "synthetic_calibration.svg", seed)
    _fig_uncertainty_vs_error(test["B"], out_dir / "synthetic_uncertainty_vs_error.svg", seed)
    _fig_failures(failures, out_dir / "synthetic_failure_analysis.svg", seed)
    _write_report(out_dir / "synthetic_results_report.md", summary)
    _write_readme(out_dir / "README.md", provenance)
    return summary


def _header(provenance: Mapping[str, Any]) -> list[str]:
    return [
        f"> **{DEMO_LABEL}.** {DISCLAIMER}",
        ">",
        "> demo=true · synthetic=true · scientific_result=false · "
        f"seed {provenance['demo_seed']} · "
        f"generated {provenance['generated_at']} · "
        f"code commit `{str(provenance['git_commit'])[:12]}` · "
        f"code sha256 `{str(provenance['code_sha256'])[:16]}…`",
        "",
    ]


def _write_report(path: Path, s: Mapping[str, Any]) -> None:
    p = s["example_primary_statistic"]
    t = s["example_threshold_transfer_q080"]
    lines = [
        "# Synthetic Results Demonstration",
        "",
        *_header(s),
        "## Purpose",
        "",
        "This report demonstrates the repository's result-generation pipeline: the same code that "
        "will produce the real per-unit metrics, statistics and figures, run on deterministic "
        "synthetic toy volumes.",
        "",
        "## IMPORTANT",
        "",
        "These are synthetic examples. They are **not** generated from BraTS 2021, UPenn or "
        "BraTS-Africa, and they must not be interpreted as scientific findings. No value below "
        "supports or rejects the study's hypotheses.",
        "",
        "## Demonstrated pipeline",
        "",
        "- metric calculation (Dice with the protocol's empty-mask convention, risk = 1 − Dice)",
        "- uncertainty calculation (U1 ensemble agreement; I from the validation freeze)",
        "- risk–coverage and AURC with expected tie handling",
        "- calibration (ECE / Brier within the protocol ROI)",
        "- threshold transfer (τ_q frozen on validation C4 units, applied unchanged)",
        "- failure analysis (confident failure, hallucinated / missed ET)",
        "- figure generation, provenance and export",
        "",
        "## Example outputs (synthetic)",
        "",
        "| Example quantity | Synthetic value | Note |",
        "|---|---|---|",
        f"| Mean over C4 of ET ΔAURC (U1 − I) | {p['estimate']:.4f} "
        f"[{p['ci_low']:.4f}, {p['ci_high']:.4f}] | "
        f"{DISCLAIMER} |",
        *(
            f"| ΔAURC {c} | {v:.4f} | {DISCLAIMER} |"
            for c, v in s["example_delta_aurc_by_condition"].items()
        ),
        f"| τ_0.80 (validation C4) | {s['example_tau_q']['0.80']:.4f} | {DISCLAIMER} |",
        f"| Δrisk / Δcoverage at τ_0.80 | {t['delta_risk']:.4f} / "
        f"{t['delta_coverage']:.4f} | {DISCLAIMER} |",
        "",
        "Figures: `synthetic_risk_coverage.svg`, `synthetic_calibration.svg`, "
        "`synthetic_uncertainty_vs_error.svg`, `synthetic_failure_analysis.svg`. Tables: "
        "`synthetic_metrics.csv`, `synthetic_failure_analysis.csv`.",
        "",
        "## Real study status",
        "",
        "Official data acquisition is pending. No real model results are available. Real result "
        "artifacts are written only by the gated pipeline after the pre-registered experiment has "
        "been executed, and never to this directory.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def _write_readme(path: Path, provenance: Mapping[str, Any]) -> None:
    lines = [
        "# results/demo — SYNTHETIC DEMONSTRATION — NOT REAL BRATS RESULTS",
        "",
        *_header(provenance),
        "This directory shows what the finished repository and website will look like once the "
        "pre-registered experiment has run. Everything here comes from deterministic synthetic toy "
        "volumes (`SYNTH_*` cases, seed 20261004) processed by the study's real metric, statistics "
        "and figure code. It is **not** a scientific-results directory.",
        "",
        "- `synthetic_summary.json` — example statistics with full provenance flags",
        "- `synthetic_metrics.csv` — example per-unit metric rows (protocol §24 layout)",
        "- `synthetic_failure_analysis.csv` — example failure-category counts",
        "- `synthetic_*.svg` — example figures (each visibly labelled)",
        "- `synthetic_results_report.md` — the demonstration report",
        "",
        "Regenerate (deterministic): `brats-uncertainty demo --out results/demo`.",
        "",
        "Safeguards: demo files carry demo=true / synthetic=true / scientific_result=false; the "
        "generator refuses every real result namespace; the public export and the website results "
        "index refuse demo files; demo files can never serve as gate evidence.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
