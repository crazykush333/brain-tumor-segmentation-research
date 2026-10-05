"""The pre-registered analyses (§2-§4, §12-§15, §19) on per-unit rows.

Everything is computed from unit rows produced by ``study.units`` and the frozen
C5 record; no number is typed in. Confirmatory structure:

- primary H-W: mean over C4 of ET Delta-AURC_c (internal test, arm B), percentile CI
  (BCa sensitivity), two-sided bootstrap p (§13); supported iff the CI is entirely < 0;
- F1 (S1, 4 tests), F4 (S2, 2 tests), F2 (S8, 2 tests), F3/F3b (S7 at q = 0.80, 3 tests
  each): Holm within each family only (§14);
- F5 (S9, arm A) and all S3-S6, S10, S12-S14, supporting and seed-variation analyses
  are descriptive (95 % CIs, no claims).

Bootstrap: patient-group level, 10,000 replicates, seed 12345 (``statistics.bootstrap``).
SR3: if BraTS-Africa has fewer than 30 eligible cases its analyses are descriptive
only, so F2/F3/F3b lose that test (a logged deviation; Holm over the remaining tests).

[Implementation choices, flagged for owner confirmation at C6 with the others in
docs/reproducibility/REPRODUCIBILITY.md §4: S13 case-weighted AURC uses the
weighted step integral with tie blocks replaced by their weighted mean risk; the
I-then-U1 ranker orders by validation risk (I), then U1, ties of both expected; the
supporting B-A margin of 1.5 Dice points is 0.015 on the [0, 1] Dice scale.]
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy.stats import spearmanr

from brats_uncertainty.errors import DataValidationError
from brats_uncertainty.metrics.selective import aurc
from brats_uncertainty.preprocessing.modalities import C4_NAMES, C5_NAMES
from brats_uncertainty.statistics.bootstrap import (
    PROTOCOL_REPLICATES,
    PROTOCOL_SEED,
    BootstrapResult,
    GroupIndex,
    bca_from_result,
    group_bootstrap,
)
from brats_uncertainty.statistics.multiplicity import holm_adjust, holm_family
from brats_uncertainty.statistics.primary import mean_delta_aurc, run_primary
from brats_uncertainty.statistics.thresholds import TauResult, threshold_transfer, transfer_labels
from brats_uncertainty.study.freeze import unit_table

SR3_MIN_AFRICA = 30
SUPPORTING_MARGIN = 0.015
S13_WEIGHTS = {
    "a_equal_C5": {c: 0.2 for c in C5_NAMES},
    "b_80_full": {"Full": 0.80, **{c: 0.05 for c in C4_NAMES}},
}


class Frame:
    """Column arrays of selected unit rows plus their patient-group index."""

    def __init__(self, rows: Sequence[Mapping[str, str]]) -> None:
        if not rows:
            raise DataValidationError("no unit rows selected")
        self.rows = list(rows)
        self.group = np.asarray([r["group_id"] for r in rows], dtype=str)
        self.case = np.asarray([r["case_id"] for r in rows], dtype=str)
        self.condition = np.asarray([r["condition"] for r in rows], dtype=str)
        self.groups = GroupIndex(self.group)

    def col(self, name: str) -> NDArray[np.float64]:
        return np.asarray(
            [float(r[name]) if r[name] != "" else np.nan for r in self.rows], dtype=np.float64
        )


def _select(rows: Sequence[Mapping[str, str]], **eq: Any) -> list[Mapping[str, str]]:
    out = []
    for r in rows:
        ok = True
        for k, v in eq.items():
            if isinstance(v, (tuple, list, set, frozenset)):
                ok = ok and r[k] in v
            else:
                ok = ok and r[k] == v
        if ok:
            out.append(r)
    return out


def _boot(
    stat: Callable[[NDArray[np.intp]], float], f: Frame, n: int, seed: int
) -> BootstrapResult:
    return group_bootstrap(stat, f.groups, n_replicates=n, seed=seed)


def _desc(res: BootstrapResult) -> dict[str, Any]:
    d = res.as_dict()
    d.pop("p_value_two_sided_approx")  # descriptive: no p-value is reported
    return d


def _nanmean(x: NDArray[np.float64]) -> float:
    x = x[np.isfinite(x)]
    return float(x.mean()) if x.size else float("nan")


Stat = Callable[[NDArray[np.intp]], float]


def _mean_stat(v: NDArray[np.float64]) -> Stat:
    return lambda i: _nanmean(v[i])


def _delta_aurc_stat(u: NDArray[np.float64], r: NDArray[np.float64]) -> Stat:
    return lambda i: aurc(u[i], r[i]) - float(r[i].mean())


def _rho_stat(u: NDArray[np.float64], d: NDArray[np.float64]) -> Stat:
    def rho(i: NDArray[np.intp]) -> float:
        if np.unique(u[i]).size < 2 or np.unique(d[i]).size < 2:
            return float("nan")
        return float(spearmanr(u[i], d[i]).statistic)

    return rho


def _fail_aurc_stat(fail: NDArray[np.float64], u: NDArray[np.float64]) -> Stat:
    def vf(i: NDArray[np.intp]) -> float:
        k = i[np.isfinite(fail[i])]
        return aurc(u[k], fail[k]) if k.size else float("nan")

    return vf


def _weighted_stat(s: NDArray[np.float64], r: NDArray[np.float64], w: NDArray[np.float64]) -> Stat:
    return lambda i: weighted_aurc(s[i], r[i], w[i])


# ------------------------------------------------------------------ weighted / pooled AURC
def weighted_aurc(
    conf: NDArray[np.float64], risk: NDArray[np.float64], w: NDArray[np.float64]
) -> float:
    if not (conf.size == risk.size == w.size) or conf.size == 0:
        raise ValueError("conf, risk and weights must be non-empty and equally long")
    order = np.argsort(-conf, kind="stable")
    c, r, ww = conf[order], risk[order].copy(), w[order]
    change = np.flatnonzero(np.diff(c) != 0) + 1
    for s, e in zip(np.concatenate(([0], change)), np.concatenate((change, [c.size])), strict=True):
        if e - s > 1:
            r[s:e] = float(np.sum(ww[s:e] * r[s:e]) / np.sum(ww[s:e]))
    cw = np.cumsum(ww)
    sel = np.cumsum(ww * r) / cw
    return float(np.sum(ww * sel) / cw[-1])


def lexicographic_score(
    i_score: NDArray[np.float64], u1: NDArray[np.float64]
) -> NDArray[np.float64]:
    """I first, then U1 within equal I (U1 in [0, 1]); equal (I, U1) pairs stay tied."""
    levels = np.unique(i_score)
    gap = float(np.min(np.diff(levels))) if levels.size > 1 else 1.0
    return i_score + (gap / 2.0) * u1


# ------------------------------------------------------------------ per-set blocks
ReplicateSink = dict[str, NDArray[np.float64]]


def delta_aurc_block(
    rows_b: Sequence[Mapping[str, str]],
    region: str,
    n: int,
    seed: int,
    *,
    with_bca: bool = False,
    sink: ReplicateSink | None = None,
    prefix: str = "",
) -> dict[str, Any]:
    t = unit_table(rows_b, region, C5_NAMES)
    res = run_primary(t, n_replicates=n, seed=seed)
    if sink is not None:  # production replicates, compared one by one by the verifier
        sink[f"{prefix}mean_c4"] = res.mean_c4.replicates
        for c, r in res.per_condition.items():
            sink[f"{prefix}{c}"] = r.replicates
    out: dict[str, Any] = {
        "mean_c4": res.mean_c4.as_dict(),
        "per_condition": {c: r.as_dict() for c, r in res.per_condition.items()},
        "ci_entirely_below_zero": res.ci_entirely_below_zero(),
    }
    if with_bca:
        groups = GroupIndex(t.group_id)
        lo, hi = bca_from_result(res.mean_c4, lambda i: mean_delta_aurc(t, i, C4_NAMES), groups)
        out["mean_c4"]["bca_ci_low"], out["mean_c4"]["bca_ci_high"] = lo, hi
    return out


def descriptive_block(
    rows: Sequence[Mapping[str, str]], conditions: Sequence[str], n: int, seed: int
) -> dict[str, Any]:
    """S3 (Dice, HD95), S4 (ECE/Brier), S5 (ET volume), S6 (Spearman) per condition."""
    out: dict[str, Any] = {}
    for cond in conditions:
        block: dict[str, Any] = {}
        for region in ("WT", "TC", "ET"):
            sel = _select(rows, condition=cond, region=region)
            if not sel:
                continue
            f = Frame(sel)
            reg: dict[str, Any] = {"n_units": len(sel)}
            for metric in ("dice", "ece", "brier", "hd95"):
                vals = f.col(metric)
                if np.isfinite(vals).any():
                    reg[metric] = _desc(_boot(_mean_stat(vals), f, n, seed))
                    reg[f"{metric}_n_undefined_units"] = int(np.sum(~np.isfinite(vals)))
            if region == "ET":
                ave = f.col("abs_vol_err_ml")
                reg["abs_vol_err_ml"] = _desc(_boot(_mean_stat(ave), f, n, seed))
                u1, d = f.col("U1"), f.col("dice")
                reg["spearman_U1_ET_dice"] = _desc(_boot(_rho_stat(u1, d), f, n, seed))
                for thr in ("40", "65"):
                    fail = f.col(f"vol_fail_{thr}")
                    elig = np.isfinite(fail)
                    reg[f"vol_fail_{thr}_n_eligible"] = int(elig.sum())
                    if elig.sum() >= 1:
                        reg[f"vol_fail_{thr}_aurc_U1"] = _desc(
                            _boot(_fail_aurc_stat(fail, u1), f, n, seed)
                        )
                        reg[f"vol_fail_{thr}_rate"] = float(np.mean(fail[elig]))
            block[region] = reg
        out[cond] = block
    return out


def c15_block(rows_b_c15: Sequence[Mapping[str, str]], n: int, seed: int) -> dict[str, Any]:
    """S10: arm B, internal test, all 15 subsets: ET Dice, within-condition Delta-AURC, ECE."""
    out = {}
    for cond in sorted({r["condition"] for r in rows_b_c15}):
        f = Frame(_select(rows_b_c15, condition=cond, region="ET"))
        d, u1, risk, ece = f.col("dice"), f.col("U1"), f.col("risk"), f.col("ece")
        out[cond] = {
            "et_dice": _desc(_boot(_mean_stat(d), f, n, seed)),
            "delta_aurc": _desc(_boot(_delta_aurc_stat(u1, risk), f, n, seed)),
            "ece": _desc(_boot(_mean_stat(ece), f, n, seed)),
        }
    return out


def pooled_block(rows_b: Sequence[Mapping[str, str]], n: int, seed: int) -> dict[str, Any]:
    """S12 rankers on pooled C5 ET units (needs I); S13 case-weighting mixtures."""
    f = Frame(_select(rows_b, region="ET", condition=C5_NAMES))
    u1, i_s, risk = f.col("U1"), f.col("I"), f.col("risk")
    if not np.isfinite(i_s).all():
        raise DataValidationError("S12 needs the frozen validation I on every unit (gate C5)")
    lex = lexicographic_score(i_s, u1)
    rankers = {"U1": u1, "I": i_s, "I_then_U1": lex}
    out: dict[str, Any] = {}
    for wname, wmap in S13_WEIGHTS.items():
        counts = {c: int(np.sum(f.condition == c)) for c in C5_NAMES}
        w = np.asarray([wmap[c] / counts[c] for c in f.condition], dtype=np.float64)
        out[wname] = {
            name: _desc(_boot(_weighted_stat(s, risk, w), f, n, seed))
            for name, s in rankers.items()
        }
    return out


def indicator_transfer_error(
    rows: Sequence[Mapping[str, str]], frozen: Mapping[str, Any], arm: str = "B"
) -> dict[str, float]:
    """S14: validation-estimated ET risk minus realized target ET risk, per condition."""
    out = {}
    for cond in C5_NAMES:
        r = [float(x["risk"]) for x in rows if x["region"] == "ET" and x["condition"] == cond]
        if r:
            out[cond] = float(frozen["indicator"][arm]["ET"][cond]["mean_risk"]) - float(np.mean(r))
    return out


def supporting_block(
    rows_a: Sequence[Mapping[str, str]], rows_b: Sequence[Mapping[str, str]], n: int, seed: int
) -> dict[str, Any]:
    """B - A ET Dice: per case over C5, then per patient group; Full-only vs +-0.015."""

    def per_group(conditions: Sequence[str]) -> tuple[list[str], NDArray[np.float64]]:
        def dmap(rows: Sequence[Mapping[str, str]]) -> dict[tuple[str, str], float]:
            return {
                (r["case_id"], r["condition"]): float(r["dice"])
                for r in rows
                if r["region"] == "ET" and r["condition"] in conditions
            }

        a, b = dmap(rows_a), dmap(rows_b)
        if set(a) != set(b):
            raise DataValidationError("arm A and arm B units differ")
        group_of = {r["case_id"]: r["group_id"] for r in rows_b}
        case_diff: dict[str, list[float]] = {}
        for (case, _), v in b.items():
            case_diff.setdefault(case, []).append(v - a[(case, _)])
        g_vals: dict[str, list[float]] = {}
        for case, diffs in case_diff.items():
            g_vals.setdefault(group_of[case], []).append(float(np.mean(diffs)))
        gids = sorted(g_vals)
        return gids, np.asarray([np.mean(g_vals[g]) for g in gids])

    out = {}
    for name, conds in (("c5_mean", C5_NAMES), ("full_input", ("Full",))):
        gids, vals = per_group(conds)
        groups = GroupIndex(gids)  # one value per patient group
        res = group_bootstrap(_mean_stat(vals), groups, n_replicates=n, seed=seed)
        d = _desc(res)
        if name == "full_input":
            d["margin"] = SUPPORTING_MARGIN
            d["ci_within_margin"] = bool(
                res.ci_low >= -SUPPORTING_MARGIN and res.ci_high <= SUPPORTING_MARGIN
            )
        out[name] = d
    return out


def seed_variation(rows: Sequence[Mapping[str, str]]) -> dict[str, Any]:
    """Single-member ET Dice per condition: mean over cases per seed, then mean +- SD."""
    out = {}
    for cond in C5_NAMES:
        sel = _select(rows, condition=cond, region="ET")
        if not sel:
            continue
        per_seed = [float(np.mean([float(r[f"dice_member_{s}"]) for r in sel])) for s in range(3)]
        out[cond] = {
            "per_seed_mean": per_seed,
            "mean": float(np.mean(per_seed)),
            "sd": float(np.std(per_seed, ddof=1)),
        }
    return out


# ------------------------------------------------------------------ dataset-level analyses
def internal_analysis(
    rows_b: Sequence[Mapping[str, str]],
    rows_a: Sequence[Mapping[str, str]],
    frozen: Mapping[str, Any],
    *,
    rows_b_c15: Sequence[Mapping[str, str]] | None = None,
    n_replicates: int = PROTOCOL_REPLICATES,
    seed: int = PROTOCOL_SEED,
    sink: ReplicateSink | None = None,
) -> dict[str, Any]:
    n = n_replicates
    primary = delta_aurc_block(rows_b, "ET", n, seed, with_bca=True, sink=sink, prefix="ET:")
    f1_p = {c: primary["per_condition"][c]["p_value_two_sided_approx"] for c in C4_NAMES}
    f1_adj = holm_family("F1", f1_p)
    s2 = {r: delta_aurc_block(rows_b, r, n, seed)["mean_c4"] for r in ("TC", "WT")}
    f4_adj = holm_family("F4", {r: s2[r]["p_value_two_sided_approx"] for r in ("TC", "WT")})
    s9 = delta_aurc_block(rows_a, "ET", n, seed)["per_condition"]
    out: dict[str, Any] = {
        "dataset": "internal_test",
        "primary_HW": {
            **primary["mean_c4"],
            "supported": primary["ci_entirely_below_zero"],
            "decision_rule": "H-W supported iff the 95% percentile CI lies entirely below 0",
        },
        "S1_F1": {
            c: {
                **primary["per_condition"][c],
                "holm_p": f1_adj[c],
                "claim_delta_below_zero": bool(
                    f1_adj[c] < 0.05 and primary["per_condition"][c]["estimate"] < 0
                ),
            }
            for c in C4_NAMES
        },
        "full_control": _desc_dict(primary["per_condition"].get("Full")),
        "S2_F4": {
            r: {
                **s2[r],
                "holm_p": f4_adj[r],
                "claim_delta_below_zero": bool(f4_adj[r] < 0.05 and s2[r]["estimate"] < 0),
            }
            for r in ("TC", "WT")
        },
        "S9_F5_armA_descriptive": {c: _desc_dict(s9[c]) for c in C4_NAMES if c in s9},
        "descriptive_armB": descriptive_block(rows_b, C5_NAMES, n, seed),
        "descriptive_armA": descriptive_block(rows_a, C5_NAMES, n, seed),
        "S12_S13_pooled_armB": pooled_block(rows_b, n, seed),
        "S14_indicator_transfer_error": indicator_transfer_error(rows_b, frozen),
        "supporting_B_minus_A_ET_dice": supporting_block(rows_a, rows_b, n, seed),
        "seed_variation": {"A": seed_variation(rows_a), "B": seed_variation(rows_b)},
    }
    if rows_b_c15 is not None:
        out["S10_C15_armB"] = c15_block(rows_b_c15, n, seed)
    return out


def _desc_dict(d: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if d is None:
        return None
    return {k: v for k, v in d.items() if k != "p_value_two_sided_approx"}


def external_analysis(
    dataset: str,
    rows_b: Sequence[Mapping[str, str]],
    frozen: Mapping[str, Any],
    *,
    n_replicates: int = PROTOCOL_REPLICATES,
    seed: int = PROTOCOL_SEED,
) -> dict[str, Any]:
    """S8 (mean over C4 tested in F2; components descriptive), S3-S6, S14 for one set."""
    block = delta_aurc_block(rows_b, "ET", n_replicates, seed)
    n_cases = len({r["case_id"] for r in rows_b})
    return {
        "dataset": dataset,
        "n_cases": n_cases,
        "S8_mean_c4": block["mean_c4"],
        "S8_components_descriptive": {c: _desc_dict(v) for c, v in block["per_condition"].items()},
        "descriptive_armB": descriptive_block(rows_b, C5_NAMES, n_replicates, seed),
        "S14_indicator_transfer_error": indicator_transfer_error(rows_b, frozen),
        "descriptive_only_SR3": dataset == "brats_africa" and n_cases < SR3_MIN_AFRICA,
    }


def transfer_analysis(
    validation_b: Sequence[Mapping[str, str]],
    target_b: Sequence[Mapping[str, str]],
    frozen: Mapping[str, Any],
    *,
    n_replicates: int = PROTOCOL_REPLICATES,
    seed: int = PROTOCOL_SEED,
    sink: ReplicateSink | None = None,
    prefix: str = "",
) -> dict[str, Any]:
    """S7 for one target set: q = 0.80 (F3/F3b) and 0.70 / 0.90 (sensitivity)."""
    v = unit_table(validation_b, "ET", C4_NAMES)
    t = unit_table(target_b, "ET", C4_NAMES)
    out = {}
    for q in ("0.80", "0.70", "0.90"):
        fr = frozen["tau_q"][q]
        tau = TauResult(
            q=float(q),
            tau=float(fr["tau"]),
            realized_coverage=float(fr["realized_validation_coverage"]),
        )
        res = threshold_transfer(v, t, tau, n_replicates=n_replicates, seed=seed)
        if sink is not None and q == "0.80":
            sink[f"{prefix}delta_risk"] = res.delta_risk.replicates
            sink[f"{prefix}delta_coverage"] = res.delta_coverage.replicates
        out[q] = {
            "tau": tau.tau,
            "validation_coverage": res.validation_coverage,
            "validation_risk": res.validation_risk,
            "target_coverage": res.target_coverage,
            "target_risk": res.target_risk,
            "delta_risk": res.delta_risk.as_dict(),
            "delta_coverage": res.delta_coverage.as_dict(),
        }
    return out


def assemble_families(
    internal: Mapping[str, Any],
    externals: Mapping[str, Mapping[str, Any]],
    transfers: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """F2, F3 and F3b across sets (Holm within family); SR3 drops a descriptive-only set."""
    deviations: list[str] = []
    tested = {k: v for k, v in externals.items() if not v.get("descriptive_only_SR3")}
    for k in set(externals) - set(tested):
        deviations.append(
            f"SR3: {k} has < {SR3_MIN_AFRICA} eligible cases; its analyses are descriptive only"
        )

    def holm(family: str, p: dict[str, float], full_size: int) -> dict[str, float]:
        if len(p) == full_size:
            return holm_family(family, p)
        deviations.append(f"{family}: Holm over {len(p)} of {full_size} tests (SR3)")
        return holm_adjust(p) if p else {}

    f2_p = {k: v["S8_mean_c4"]["p_value_two_sided_approx"] for k, v in tested.items()}
    f2 = holm("F2", f2_p, 2)
    tgt = {k: v for k, v in transfers.items() if k in ("internal_test", *tested)}
    f3 = holm(
        "F3", {k: v["0.80"]["delta_risk"]["p_value_two_sided_approx"] for k, v in tgt.items()}, 3
    )
    f3b = holm(
        "F3b",
        {k: v["0.80"]["delta_coverage"]["p_value_two_sided_approx"] for k, v in tgt.items()},
        3,
    )
    return {
        "F2": {
            k: {
                "estimate": tested[k]["S8_mean_c4"]["estimate"],
                "holm_p": f2[k],
                "claim_delta_below_zero": bool(
                    f2[k] < 0.05 and tested[k]["S8_mean_c4"]["estimate"] < 0
                ),
            }
            for k in f2
        },
        "F3_F3b": {
            k: {
                "delta_risk": tgt[k]["0.80"]["delta_risk"]["estimate"],
                "delta_coverage": tgt[k]["0.80"]["delta_coverage"]["estimate"],
                "holm_p_risk": f3[k],
                "holm_p_coverage": f3b[k],
                **transfer_labels(
                    tgt[k]["0.80"]["delta_risk"]["estimate"],
                    f3[k],
                    tgt[k]["0.80"]["delta_coverage"]["estimate"],
                    f3b[k],
                ),
            }
            for k in tgt
        },
        "deviations": deviations,
        "statement": "Holm within family only; no global FWER control; never 'equivalent'",
    }
