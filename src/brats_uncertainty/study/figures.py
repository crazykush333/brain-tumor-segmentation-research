"""Figures and tables generated only from analysis payloads and unit rows.

Every output gets a ``<name>.provenance.json`` sidecar (git commit, protocol hash,
SHA-256 of every input file, run IDs). Synthetic inputs produce watermarked
figures (``visualization.plots``) and can never become research results.
"""

from __future__ import annotations

import csv
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from brats_uncertainty.metrics.selective import risk_coverage_curve
from brats_uncertainty.preprocessing.modalities import C4_NAMES, C5_NAMES
from brats_uncertainty.utils.io import write_json
from brats_uncertainty.visualization.plots import _finish, _plt, plot_delta_aurc_forest


def _sidecar(path: Path, provenance: Mapping[str, Any]) -> None:
    write_json(path.with_name(path.name + ".provenance.json"), dict(provenance), overwrite=True)


def _both(fig_fn: Any, stem: Path, provenance: Mapping[str, Any], **kw: Any) -> list[Path]:
    out = []
    for ext in ("png", "svg"):
        p = fig_fn(path=stem.with_suffix(f".{ext}"), **kw)
        _sidecar(p, provenance)
        out.append(p)
    return out


def figure_primary_forest(
    internal: Mapping[str, Any], stem: Path, provenance: Mapping[str, Any], *, synthetic: bool
) -> list[Path]:
    est = {c: (v["estimate"], v["ci_low"], v["ci_high"]) for c, v in internal["S1_F1"].items()}
    full = internal.get("full_control")
    if full:
        est["Full (control)"] = (full["estimate"], full["ci_low"], full["ci_high"])
    p = internal["primary_HW"]
    est["Mean over C4 (H-W)"] = (p["estimate"], p["ci_low"], p["ci_high"])
    return _both(
        plot_delta_aurc_forest,
        stem,
        provenance,
        estimates=est,
        synthetic=synthetic,
        order=[*C4_NAMES, "Full (control)", "Mean over C4 (H-W)"] if full else None,
    )


def figure_risk_coverage(
    rows_b: Sequence[Mapping[str, str]],
    stem: Path,
    provenance: Mapping[str, Any],
    *,
    synthetic: bool,
    title: str,
) -> list[Path]:
    def draw(path: Path) -> Path:
        plt = _plt()
        fig, axes = plt.subplots(1, len(C4_NAMES), figsize=(4 * len(C4_NAMES), 3.6), sharey=True)
        for ax, cond in zip(np.atleast_1d(axes), C4_NAMES, strict=True):
            sel = [r for r in rows_b if r["region"] == "ET" and r["condition"] == cond]
            u1 = np.asarray([float(r["U1"]) for r in sel])
            risk = np.asarray([float(r["risk"]) for r in sel])
            c = risk_coverage_curve(u1, risk)
            ax.plot(c.coverage, c.selective_risk, label="U1")
            ax.axhline(float(risk.mean()), color="grey", ls="--", lw=1, label="I (random ranking)")
            ax.set_title(f"{cond} (n={len(sel)})")
            ax.set_xlabel("Coverage")
        np.atleast_1d(axes)[0].set_ylabel("Selective risk (1 - ET Dice)")
        np.atleast_1d(axes)[0].legend(frameon=False)
        fig.suptitle(title)
        return _finish(fig, path, synthetic)

    out = []
    for ext in ("png", "svg"):
        p = draw(stem.with_suffix(f".{ext}"))
        _sidecar(p, provenance)
        out.append(p)
    return out


def figure_transfer(
    transfers: Mapping[str, Mapping[str, Any]],
    stem: Path,
    provenance: Mapping[str, Any],
    *,
    synthetic: bool,
) -> list[Path]:
    def draw(path: Path) -> Path:
        plt = _plt()
        fig, axes = plt.subplots(1, 2, figsize=(9, 3.2))
        names = list(transfers)
        for ax, key, label in (
            (axes[0], "delta_risk", "Delta risk"),
            (axes[1], "delta_coverage", "Delta coverage"),
        ):
            for i, n in enumerate(names):
                d = transfers[n]["0.80"][key]
                ax.errorbar(
                    d["estimate"],
                    i,
                    xerr=[[d["estimate"] - d["ci_low"]], [d["ci_high"] - d["estimate"]]],
                    fmt="o",
                    color="black",
                    capsize=3,
                )
            ax.axvline(0.0, color="grey", ls="--", lw=1)
            ax.set_yticks(range(len(names)), names)
            ax.set_xlabel(f"{label} at tau_0.80")
        return _finish(fig, path, synthetic)

    out = []
    for ext in ("png", "svg"):
        p = draw(stem.with_suffix(f".{ext}"))
        _sidecar(p, provenance)
        out.append(p)
    return out


def table_rows(
    internal: Mapping[str, Any],
    families: Mapping[str, Any] | None,
    externals: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    def add(analysis: str, item: str, d: Mapping[str, Any], extra: str = "") -> None:
        rows.append(
            {
                "analysis": analysis,
                "item": item,
                "estimate": repr(d["estimate"]),
                "ci_low": repr(d["ci_low"]),
                "ci_high": repr(d["ci_high"]),
                "p_two_sided": repr(d["p_value_two_sided_approx"])
                if "p_value_two_sided_approx" in d
                else "",
                "note": extra,
            }
        )

    p = internal["primary_HW"]
    add("primary H-W (internal, arm B, ET)", "mean over C4", p, f"supported={p['supported']}")
    for c, d in internal["S1_F1"].items():
        add("S1/F1", c, d, f"holm_p={d['holm_p']!r}; claim={d['claim_delta_below_zero']}")
    if internal.get("full_control"):
        add("Full control (descriptive)", "Full", internal["full_control"])
    for r, d in internal["S2_F4"].items():
        add("S2/F4", r, d, f"holm_p={d['holm_p']!r}; claim={d['claim_delta_below_zero']}")
    for c, d in internal["S9_F5_armA_descriptive"].items():
        add("S9/F5 arm A (descriptive)", c, d)
    for ds, e in externals.items():
        add(
            f"S8 {ds}",
            "mean over C4",
            e["S8_mean_c4"],
            f"descriptive_only_SR3={e['descriptive_only_SR3']}",
        )
    if families:
        for ds, d in families["F2"].items():
            rows.append(
                {
                    "analysis": "F2",
                    "item": ds,
                    "estimate": repr(d["estimate"]),
                    "ci_low": "",
                    "ci_high": "",
                    "p_two_sided": "",
                    "note": f"holm_p={d['holm_p']!r}; claim={d['claim_delta_below_zero']}",
                }
            )
    return rows


def write_tables(
    rows: Sequence[Mapping[str, str]], stem: Path, provenance: Mapping[str, Any]
) -> list[Path]:
    stem.parent.mkdir(parents=True, exist_ok=True)
    fields = ("analysis", "item", "estimate", "ci_low", "ci_high", "p_two_sided", "note")
    csv_path = stem.with_suffix(".csv")
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    md = ["| " + " | ".join(fields) + " |", "|" + "---|" * len(fields)]
    md += ["| " + " | ".join(r[f] for f in fields) + " |" for r in rows]
    md_path = stem.with_suffix(".md")
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8", newline="\n")
    for p in (csv_path, md_path):
        _sidecar(p, provenance)
    return [csv_path, md_path]


__all__ = [
    "C5_NAMES",
    "figure_primary_forest",
    "figure_risk_coverage",
    "figure_transfer",
    "table_rows",
    "write_tables",
]
