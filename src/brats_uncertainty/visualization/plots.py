"""Figures for risk-coverage curves and per-condition Delta-AURC estimates.

Every figure takes an explicit ``synthetic`` flag. Synthetic figures carry a
large "SYNTHETIC - NOT BraTS DATA" watermark and are for tests/documentation of
the plotting code only; they are never used as research results.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from brats_uncertainty.metrics.selective import RiskCoverageCurve

SYNTHETIC_WATERMARK = "SYNTHETIC - NOT BraTS DATA"


def _plt() -> Any:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "install the optional extra: pip install 'brats-uncertainty[viz]'"
        ) from exc
    return plt


def _finish(fig: Any, path: str | Path, synthetic: bool) -> Path:
    if synthetic:
        fig.text(
            0.5,
            0.5,
            SYNTHETIC_WATERMARK,
            ha="center",
            va="center",
            fontsize=22,
            color="red",
            alpha=0.35,
            rotation=25,
            transform=fig.transFigure,
        )
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        p,
        dpi=150,
        bbox_inches="tight",
        metadata={"Description": SYNTHETIC_WATERMARK if synthetic else ""},
    )
    _plt().close(fig)
    return p


def plot_risk_coverage(
    curves: Mapping[str, RiskCoverageCurve], path: str | Path, *, synthetic: bool, title: str = ""
) -> Path:
    plt = _plt()
    fig, ax = plt.subplots(figsize=(5, 4))
    for label, c in curves.items():
        ax.plot(c.coverage, c.selective_risk, label=label)
    ax.set_xlabel("Coverage")
    ax.set_ylabel("Selective risk (1 - ET Dice)")
    ax.set_xlim(0, 1)
    ax.set_title(title)
    ax.legend(frameon=False)
    return _finish(fig, path, synthetic)


def plot_delta_aurc_forest(
    estimates: Mapping[str, tuple[float, float, float]],
    path: str | Path,
    *,
    synthetic: bool,
    order: Sequence[str] | None = None,
) -> Path:
    """Forest plot of (estimate, ci_low, ci_high) per condition; zero line marked."""
    plt = _plt()
    names = list(order or estimates)
    fig, ax = plt.subplots(figsize=(5, 0.5 * len(names) + 1.2))
    for i, n in enumerate(names):
        est, lo, hi = estimates[n]
        ax.errorbar(est, i, xerr=[[est - lo], [hi - est]], fmt="o", color="black", capsize=3)
    ax.axvline(0.0, color="grey", ls="--", lw=1)
    ax.set_yticks(range(len(names)), names)
    ax.invert_yaxis()
    ax.set_xlabel("Delta AURC (U1 - I)")
    return _finish(fig, path, synthetic)
