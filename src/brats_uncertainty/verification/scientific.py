"""Scientific verification stages (Phases 7-18, 21): recompute and reconcile.

Every recomputation uses ``verification.independent`` (no production metric/statistics
function) on the canonical per-unit rows; production values come from the analysis
artifacts, the bootstrap replicate files, the table and the figure source data. The
bootstrap is re-evaluated on the *identical* declared resamples (regenerated from the
declared seed/method/group order and identified by SHA-256).
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections.abc import Callable, Mapping, Sequence
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np

from brats_uncertainty.verification import independent as ind
from brats_uncertainty.verification.model import (
    FAIL,
    NOT_APPLICABLE,
    NOT_PERFORMED,
    PASS,
    Check,
    Stage,
    compare_number,
    compare_series,
    expect,
)

C4 = ("-T1", "-T1c", "-T2", "-FLAIR")
C5 = ("Full", *C4)
REGIONS = ("WT", "TC", "ET")
PROTOCOL_REPLICATES = 10_000
PROTOCOL_SEED = 12_345
SETS = ("validation", "internal_test", "upenn_hoi", "brats_africa")
VOXEL_ML = Fraction(1, 1000)


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _f(x: str) -> float:
    return float(x) if x != "" else math.nan


def _ints(x: str) -> list[int]:
    return [int(v) for v in x.split(";")]


def load_units(units_dir: Path) -> dict[tuple[str, str], list[dict[str, str]]]:
    out = {}
    for ds in SETS:
        for arm in ("A", "B"):
            p = units_dir / f"units_{ds}_arm{arm}_C5.csv"
            if p.is_file():
                out[(ds, arm)] = read_rows(p)
    return out


# ------------------------------------------------------------------ Phase 8: unit metrics
def recompute_unit(row: Mapping[str, str]) -> dict[str, Any]:
    gt, pred, inter = (
        int(row["gt_voxels"]),
        int(row["pred_voxels"]),
        int(row["ensemble_gt_intersection"]),
    )
    vox = _ints(row["member_voxels"])
    d = ind.dice_counts(gt, pred, inter)
    bins = [
        (int(c), float(sp), int(sy))
        for c, sp, sy in (b.split(":") for b in row["calibration_bins"].split(";"))
    ]
    ece, brier, n = ind.ece_brier_bins(bins, float(row["brier_sse"]))
    out: dict[str, Any] = {
        "dice": float(d),
        "risk": float(1 - d),
        "U1": float(ind.u1_counts(vox, _ints(row["member_pair_intersections"]))),
        **{
            f"dice_member_{i}": float(ind.dice_counts(vox[i], gt, g))
            for i, g in enumerate(_ints(row["member_gt_intersections"]))
        },
        "ece": ece,
        "brier": brier,
        "roi_voxels_from_bins": n,
        "gt_ml": float(gt * VOXEL_ML),
        "pred_ml": float(pred * VOXEL_ML),
    }
    if row["region"] == "ET":
        out["abs_vol_err_ml"] = float(abs(pred - gt) * VOXEL_ML)
        for name, rel in (("vol_fail_40", Fraction(2, 5)), ("vol_fail_65", Fraction(13, 20))):
            v = ind.volume_failure(pred, gt, VOXEL_ML, rel)
            out[name] = "" if v is None else ("1" if v else "0")
    return out


def stage_metrics(
    units: Mapping[tuple[str, str], list[dict[str, str]]], frozen: Mapping[str, Any]
) -> Stage:
    st = Stage("METRICS", "Per-unit metrics recomputed from primitive counts")
    exact = {"dice", "U1", "dice_member_0", "dice_member_1", "dice_member_2"}
    for (ds, arm), rows in units.items():
        rec = [recompute_unit(r) for r in rows]
        for field in (
            "dice",
            "risk",
            "U1",
            "dice_member_0",
            "dice_member_1",
            "dice_member_2",
            "ece",
            "brier",
            "gt_ml",
            "pred_ml",
        ):
            c = compare_series(
                f"{ds}/arm {arm}: {field}", [_f(r[field]) for r in rows], [x[field] for x in rec]
            )
            if field in exact and c.status != PASS and c.status != FAIL:
                c.status, c.detail = FAIL, "deterministic quantity must match exactly"
            st.add(c)
        st.add(
            expect(
                f"{ds}/arm {arm}: calibration bins sum to the ROI size",
                all(
                    int(r["roi_voxels"]) == x["roi_voxels_from_bins"]
                    for r, x in zip(rows, rec, strict=True)
                ),
            )
        )
        et = [(r, x) for r, x in zip(rows, rec, strict=True) if r["region"] == "ET"]
        st.add(
            compare_series(
                f"{ds}/arm {arm}: ET absolute volume error",
                [_f(r["abs_vol_err_ml"]) for r, _ in et],
                [x["abs_vol_err_ml"] for _, x in et],
            )
        )
        for name in ("vol_fail_40", "vol_fail_65"):
            st.add(
                expect(f"{ds}/arm {arm}: {name} (exact)", all(r[name] == x[name] for r, x in et))
            )
        if ds != "validation":
            ind_map = frozen["indicator"][arm]
            st.add(
                expect(
                    f"{ds}/arm {arm}: I equals the validation-frozen value",
                    all(
                        r["I"] == ""
                        if r["condition"] not in ind_map[r["region"]]
                        else math.isclose(
                            float(r["I"]),
                            -float(ind_map[r["region"]][r["condition"]]["mean_risk"]),
                            rel_tol=0,
                            abs_tol=1e-15,
                        )
                        for r in rows
                    ),
                )
            )
        keys = [(r["case_id"], r["condition"], r["region"]) for r in rows]
        st.add(
            expect(
                f"{ds}/arm {arm}: one unit per case-condition-region", len(keys) == len(set(keys))
            )
        )
    return st.finish()


# ------------------------------------------------------------------ Phases 9-11
def _cond_table(
    rows: Sequence[Mapping[str, str]], region: str
) -> dict[str, list[tuple[str, float, float]]]:
    """condition -> [(group, U1, risk)] recomputed from primitives."""
    out: dict[str, list[tuple[str, float, float]]] = {}
    for r in rows:
        if r["region"] == region:
            x = recompute_unit(r)
            out.setdefault(r["condition"], []).append((r["group_id"], x["U1"], x["risk"]))
    return out


def _delta(units: Sequence[tuple[str, float, float]]) -> float:
    if not units:
        return math.nan
    return ind.delta_aurc([u for _, u, _ in units], [r for _, _, r in units])


def declared_draws(n_groups: int, n_replicates: int, seed: int) -> np.ndarray:
    return (
        np.random.default_rng(seed)
        .integers(0, n_groups, size=(n_replicates, n_groups))
        .astype("<i8")
    )


def declared_transfer_draws(gv: int, gt: int, n: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    v = np.empty((n, gv), dtype="<i8")
    t = np.empty((n, gt), dtype="<i8")
    for b in range(n):
        v[b] = rng.integers(0, gv, size=gv)
        t[b] = rng.integers(0, gt, size=gt)
    return v, t


def _digest(*arrays: np.ndarray) -> str:
    h = hashlib.sha256()
    for a in arrays:
        h.update(np.ascontiguousarray(a, dtype="<i8").tobytes())
    return h.hexdigest()


def replicate_deltas(
    table: Mapping[str, list[tuple[str, float, float]]],
    groups: Sequence[str],
    draws: np.ndarray,
    conditions: Sequence[str],
) -> dict[str, list[float]]:
    """Statistic per declared resample: ΔAURC per condition and the equal-weight C4 mean."""
    by_group: dict[str, dict[str, list[tuple[str, float, float]]]] = {}
    for c, units in table.items():
        for u in units:
            by_group.setdefault(u[0], {}).setdefault(c, []).append(u)
    out: dict[str, list[float]] = {c: [] for c in (*conditions, "mean_c4")}
    for row in draws:
        sample: dict[str, list[tuple[str, float, float]]] = {c: [] for c in conditions}
        for gi in row:
            for c in conditions:
                sample[c] += by_group.get(groups[int(gi)], {}).get(c, [])
        vals = {c: _delta(sample[c]) for c in conditions}
        for c in conditions:
            out[c].append(vals[c])
        c4 = [vals[c] for c in C4]
        out["mean_c4"].append(math.fsum(c4) / 4 if all(math.isfinite(v) for v in c4) else math.nan)
    return out


def stage_primary(
    units: Mapping[tuple[str, str], list[dict[str, str]]], internal: Mapping[str, Any]
) -> tuple[Stage, dict[str, Any]]:
    from brats_uncertainty.metrics.selective import aurc as production_aurc

    st = Stage("PRIMARY_AURC", "Primary H-W: independent AURC and ΔAURC (arm B, ET, C4)")
    rows = units.get(("internal_test", "B"))
    if rows is None:
        st.add(Check("internal-test arm-B units", FAIL, detail="missing"))
        return st.finish(), {}
    table = _cond_table(rows, "ET")
    n_cases = len({r["case_id"] for r in rows})
    st.add(expect("C5 conditions present, nothing else", set(table) == set(C5), str(sorted(table))))
    st.add(expect("published components are exactly C4", set(internal["S1_F1"]) == set(C4)))
    values: dict[str, Any] = {}
    for c in C5:
        units_c = table.get(c, [])
        st.add(expect(f"{c}: one unit per case ({n_cases})", len(units_c) == n_cases))
        u1 = [u for _, u, _ in units_c]
        risk = [r for _, _, r in units_c]
        a_u1, a_i = ind.aurc(u1, risk), math.fsum(risk) / len(risk)
        st.add(
            compare_number(
                f"{c}: AURC(U1) production vs independent",
                production_aurc(np.array(u1), np.array(risk)),
                a_u1,
            )
        )
        st.add(
            compare_number(
                f"{c}: AURC(I) (constant score) = mean risk",
                production_aurc(np.zeros(len(risk)), np.array(risk)),
                a_i,
            )
        )
        prod = internal["S1_F1"][c]["estimate"] if c in C4 else internal["full_control"]["estimate"]
        st.add(compare_number(f"{c}: ΔAURC", prod, a_u1 - a_i))
        values[c] = {"aurc_u1": a_u1, "aurc_i": a_i, "delta": a_u1 - a_i}
    mean_c4 = math.fsum(values[c]["delta"] for c in C4) / 4
    st.add(
        compare_number(
            "primary: equal-weight mean over C4 (Full excluded)",
            internal["primary_HW"]["estimate"],
            mean_c4,
        )
    )
    with_full = math.fsum(values[c]["delta"] for c in C5) / 5
    st.add(
        expect(
            "primary estimate is not the C5 (Full-including) mean",
            not math.isclose(internal["primary_HW"]["estimate"], with_full, abs_tol=1e-15)
            or math.isclose(values["Full"]["delta"], mean_c4, abs_tol=1e-15),
        )
    )
    st.add(expect("rows are arm B", all(r["arm"] == "B" for r in rows)))
    values["mean_c4"] = mean_c4
    return st.finish(), values


def _replicates_csv(path: Path) -> dict[str, list[float]]:
    rows = read_rows(path)
    return {k: [float(r[k]) for r in rows] for k in rows[0] if k != "replicate"} if rows else {}


def stage_bootstrap(
    units: Mapping[tuple[str, str], list[dict[str, str]]],
    internal: Mapping[str, Any],
    bootstrap_dir: Path,
    expected_replicates: int = PROTOCOL_REPLICATES,
) -> tuple[Stage, dict[str, Any]]:
    st = Stage("BOOTSTRAP", "Patient-group bootstrap on the identical declared resamples")
    manifest_path = bootstrap_dir / "bootstrap_resamples_seed12345.json"
    if not manifest_path.is_file():
        st.add(Check("declared resample manifest", FAIL, detail="missing"))
        return st.finish(), {}
    man = json.loads(manifest_path.read_text(encoding="utf-8"))
    n, seed = int(man["n_replicates"]), int(man["seed"])
    st.add(expect(f"{expected_replicates:,} replicates", n == expected_replicates, str(n)))
    st.add(expect("bootstrap seed 12345", seed == PROTOCOL_SEED, str(seed)))
    rows = units[("internal_test", "B")]
    groups = sorted({r["group_id"] for r in rows if r["region"] == "ET"})
    st.add(
        expect(
            "unit = patient group (declared order = sorted group IDs)",
            groups == man["primary"]["group_order"],
        )
    )
    draws = declared_draws(len(groups), n, seed)
    digest = _digest(draws)
    st.add(
        expect(
            "regenerated resamples reproduce the declared digest",
            digest == man["primary"]["draws_sha256"],
        )
    )
    st.add(
        expect(
            "production primary bootstrap used the declared resamples",
            digest == internal["primary_HW"].get("draws_sha256"),
        )
    )
    reps = replicate_deltas(_cond_table(rows, "ET"), groups, draws, C5)
    prod = _replicates_csv(bootstrap_dir / "bootstrap_replicates_primary.csv")
    results: dict[str, Any] = {"draws_sha256": digest}
    for key, label in (("mean_c4", "ET:mean_c4"), *((c, f"ET:{c}") for c in C5)):
        st.add(compare_series(f"replicates {key} (all {n})", prod.get(label, []), reps[key]))
        lo, hi = ind.percentile(reps[key], 0.025), ind.percentile(reps[key], 0.975)
        p = ind.p_two_sided(reps[key])
        src = (
            internal["primary_HW"]
            if key == "mean_c4"
            else (internal["S1_F1"].get(key) or internal["full_control"])
        )
        st.add(compare_number(f"{key}: CI low", src["ci_low"], lo))
        st.add(compare_number(f"{key}: CI high", src["ci_high"], hi))
        if "p_value_two_sided_approx" in src:
            st.add(
                compare_number(f"{key}: two-sided bootstrap p", src["p_value_two_sided_approx"], p)
            )
        results[key] = {
            "ci_low": lo,
            "ci_high": hi,
            "p": p,
            "n_undefined": sum(1 for v in reps[key] if not math.isfinite(v)),
        }
    st.add(
        expect(
            "H-W decision = CI entirely below 0",
            bool(internal["primary_HW"]["supported"]) == (results["mean_c4"]["ci_high"] < 0),
        )
    )
    for region in ("TC", "WT"):  # S2 / F4, recomputed on the same resamples
        r2 = replicate_deltas(_cond_table(rows, region), groups, draws, C4)["mean_c4"]
        s2 = internal["S2_F4"][region]
        st.add(compare_number(f"S2 {region}: CI low", s2["ci_low"], ind.percentile(r2, 0.025)))
        st.add(compare_number(f"S2 {region}: CI high", s2["ci_high"], ind.percentile(r2, 0.975)))
        st.add(
            compare_number(f"S2 {region}: p", s2["p_value_two_sided_approx"], ind.p_two_sided(r2))
        )
        results[f"S2_{region}"] = {"p": ind.p_two_sided(r2)}
    return st.finish(), results


def stage_thresholds(
    units: Mapping[tuple[str, str], list[dict[str, str]]],
    frozen: Mapping[str, Any],
    transfers: Mapping[str, Any],
    bootstrap_dir: Path,
) -> tuple[Stage, dict[str, Any]]:
    st = Stage("THRESHOLDS", "τ_q and I from validation only; threshold transfer")
    val = units.get(("validation", "B"))
    if val is None:
        st.add(Check("validation arm-B units", FAIL, detail="missing"))
        return st.finish(), {}
    v = [
        (r["condition"], recompute_unit(r))
        for r in val
        if r["region"] == "ET" and r["condition"] in C4
    ]
    vu1, vrisk, vcond = [x["U1"] for _, x in v], [x["risk"] for _, x in v], [c for c, _ in v]
    taus: dict[str, Any] = {}
    for q in ("0.80", "0.70", "0.90", "0.20"):
        t, cov = ind.tau_q(vu1, vcond, float(q), C4)
        st.add(
            compare_number(
                f"τ_{q} (validation arm-B ET C4)", frozen["tau_q"][q]["tau"], t, exact=True
            )
        )
        st.add(
            compare_number(
                f"τ_{q} realized validation coverage",
                frozen["tau_q"][q]["realized_validation_coverage"],
                float(cov),
            )
        )
        taus[q] = t
    for arm in ("A", "B"):
        rows = units.get(("validation", arm), [])
        for region in REGIONS:
            for c in C5:
                risks = [
                    recompute_unit(r)["risk"]
                    for r in rows
                    if r["region"] == region and r["condition"] == c
                ]
                if risks:
                    st.add(
                        compare_number(
                            f"I arm {arm} {region} {c}",
                            frozen["indicator"][arm][region][c]["I"],
                            -math.fsum(risks) / len(risks),
                        )
                    )
    out: dict[str, Any] = {"tau": taus, "transfer": {}}
    prod_reps = (
        _replicates_csv(bootstrap_dir / "bootstrap_replicates_transfer_q080.csv")
        if (bootstrap_dir / "bootstrap_replicates_transfer_q080.csv").is_file()
        else {}
    )
    man = json.loads(
        (bootstrap_dir / "bootstrap_resamples_seed12345.json").read_text(encoding="utf-8")
    )
    for ds, payload in transfers.items():
        arm_b = units.get((ds, "B"))
        if arm_b is None:
            st.add(Check(f"{ds} arm-B units", FAIL, detail="missing"))
            continue
        tgt = [
            (r["condition"], r["group_id"], recompute_unit(r))
            for r in arm_b
            if r["region"] == "ET" and r["condition"] in C4
        ]
        tu1, trisk, tcond = (
            [x["U1"] for _, _, x in tgt],
            [x["risk"] for _, _, x in tgt],
            [c for c, _, _ in tgt],
        )
        for q in ("0.80", "0.70", "0.90"):
            vc, vr = ind.coverage_risk(vu1, vrisk, vcond, taus[q], C4)
            tc, tr = ind.coverage_risk(tu1, trisk, tcond, taus[q], C4)
            p = payload[q]
            for name, prod, rec in (
                ("validation coverage", p["validation_coverage"], float(vc)),
                ("validation selective risk", p["validation_risk"], vr),
                ("target coverage", p["target_coverage"], float(tc)),
                ("target selective risk", p["target_risk"], tr),
                ("Δrisk", p["delta_risk"]["estimate"], tr - vr),
                ("Δcoverage", p["delta_coverage"]["estimate"], float(tc - vc)),
            ):
                st.add(compare_number(f"{ds} q={q}: {name}", prod, rec))
        # replicate-level Δrisk / Δcoverage at q = 0.80 on the declared transfer resamples
        vg = sorted({r["group_id"] for r in val if r["region"] == "ET"})
        tg = sorted({g for _, g, _ in tgt})
        dv, dt = declared_transfer_draws(
            len(vg), len(tg), int(man["n_replicates"]), int(man["seed"])
        )
        digest = _digest(dv, dt)
        st.add(
            expect(
                f"{ds}: transfer resamples reproduce the declared digest",
                digest
                == man["transfer_q080"][ds]["draws_sha256"]
                == payload["0.80"]["delta_risk"].get("draws_sha256"),
            )
        )
        vgroups = [r["group_id"] for r in val if r["region"] == "ET" and r["condition"] in C4]
        vidx = {g: [i for i, gg in enumerate(vgroups) if gg == g] for g in vg}
        tidx = {g: [i for i, (_, gg, _) in enumerate(tgt) if gg == g] for g in tg}
        d_risk, d_cov = [], []
        for b in range(dv.shape[0]):
            vi = [i for gi in dv[b] for i in vidx[vg[int(gi)]]]
            ti = [i for gi in dt[b] for i in tidx[tg[int(gi)]]]
            c1, r1 = _cov_risk_idx(vu1, vrisk, vcond, vi, taus["0.80"])
            c2, r2 = _cov_risk_idx(tu1, trisk, tcond, ti, taus["0.80"])
            d_risk.append(r2 - r1)
            d_cov.append(c2 - c1)
        if prod_reps:
            st.add(
                compare_series(
                    f"{ds}: Δrisk replicates", prod_reps.get(f"{ds}:delta_risk", []), d_risk
                )
            )
            st.add(
                compare_series(
                    f"{ds}: Δcoverage replicates", prod_reps.get(f"{ds}:delta_coverage", []), d_cov
                )
            )
        for key, reps in (("delta_risk", d_risk), ("delta_coverage", d_cov)):
            prod = payload["0.80"][key]
            st.add(
                compare_number(f"{ds}: {key} CI low", prod["ci_low"], ind.percentile(reps, 0.025))
            )
            st.add(
                compare_number(f"{ds}: {key} CI high", prod["ci_high"], ind.percentile(reps, 0.975))
            )
            st.add(
                compare_number(
                    f"{ds}: {key} p", prod["p_value_two_sided_approx"], ind.p_two_sided(reps)
                )
            )
        out["transfer"][ds] = {
            "p_risk": ind.p_two_sided(d_risk),
            "p_cov": ind.p_two_sided(d_cov),
            "delta_risk": payload["0.80"]["delta_risk"]["estimate"],
            "delta_coverage": payload["0.80"]["delta_coverage"]["estimate"],
        }
    return st.finish(), out


def _cov_risk_idx(
    u1: Sequence[float], risk: Sequence[float], cond: Sequence[str], idx: Sequence[int], tau: float
) -> tuple[float, float]:
    """Equal-condition-weighted coverage (exact rational) and selective risk over a resample."""
    cov = Fraction(0)
    num = den = 0.0
    for c in C4:
        sel = [i for i in idx if cond[i] == c]
        if not sel:
            return math.nan, math.nan
        acc = [i for i in sel if u1[i] >= tau]
        cov += Fraction(len(acc), len(sel)) / 4
        w = 1.0 / (4 * len(sel))
        num += w * math.fsum(risk[i] for i in acc)
        den += w * len(acc)
    return float(cov), (num / den if den > 0 else math.nan)


# ------------------------------------------------------------------ Phase 12: statistics
def _has_p(obj: Any) -> bool:
    if isinstance(obj, dict):
        return any(k.startswith("p_value") or k == "holm_p" or _has_p(v) for k, v in obj.items())
    if isinstance(obj, list):
        return any(_has_p(x) for x in obj)
    return False


def stage_statistics(
    internal: Mapping[str, Any],
    boot: Mapping[str, Any],
    families: Mapping[str, Any] | None,
    thresholds: Mapping[str, Any],
    externals: Mapping[str, Any],
) -> Stage:
    st = Stage("STATISTICS", "Holm families, claim rules, descriptive labels")
    f1_p = {c: boot[c]["p"] for c in C4}
    f1 = ind.holm(f1_p)
    for c in C4:
        d = internal["S1_F1"][c]
        st.add(compare_number(f"F1 {c} Holm p", d["holm_p"], f1[c]))
        st.add(
            expect(
                f"F1 {c} claim rule",
                d["claim_delta_below_zero"] == (f1[c] < 0.05 and d["estimate"] < 0),
            )
        )
    f4 = ind.holm({r: boot[f"S2_{r}"]["p"] for r in ("TC", "WT")})
    for r in ("TC", "WT"):
        st.add(compare_number(f"F4 {r} Holm p", internal["S2_F4"][r]["holm_p"], f4[r]))
    st.add(
        expect("F5 (arm A, H4) carries no p-value", not _has_p(internal["S9_F5_armA_descriptive"]))
    )
    st.add(
        expect("Full control carries no p-value", not _has_p(internal.get("full_control") or {}))
    )
    for blk in (
        "descriptive_armA",
        "descriptive_armB",
        "S12_S13_pooled_armB",
        "supporting_B_minus_A_ET_dice",
    ):
        st.add(expect(f"{blk} is descriptive (no p-values)", not _has_p(internal.get(blk, {}))))
    if families is None:
        st.add(
            Check(
                "F2/F3/F3b (external families)",
                NOT_APPLICABLE,
                detail="external sets not evaluated",
            )
        )
        return st.finish()
    tested = {k: v for k, v in externals.items() if not v.get("descriptive_only_SR3")}
    f2 = ind.holm({k: v["S8_mean_c4"]["p_value_two_sided_approx"] for k, v in tested.items()})
    for k in tested:
        st.add(compare_number(f"F2 {k} Holm p", families["F2"][k]["holm_p"], f2[k]))
    tr = thresholds["transfer"]
    f3 = ind.holm({k: v["p_risk"] for k, v in tr.items() if k in families["F3_F3b"]})
    f3b = ind.holm({k: v["p_cov"] for k, v in tr.items() if k in families["F3_F3b"]})
    for k, d in families["F3_F3b"].items():
        st.add(compare_number(f"F3 {k} Holm p", d["holm_p_risk"], f3[k]))
        st.add(compare_number(f"F3b {k} Holm p", d["holm_p_coverage"], f3b[k]))
        st.add(
            expect(
                f"{k} unsafe-transfer rule",
                d["unsafe_transfer"] == (f3[k] < 0.05 and d["delta_risk"] > 0),
            )
        )
        st.add(
            expect(
                f"{k} inefficient-transfer rule",
                d["inefficient_transfer"] == (f3b[k] < 0.05 and d["delta_coverage"] < 0),
            )
        )
    return st.finish()


# ------------------------------------------------------------------ Phase 14-15
def stage_calibration(
    units: Mapping[tuple[str, str], list[dict[str, str]]], internal: Mapping[str, Any]
) -> Stage:
    st = Stage("CALIBRATION", "ECE / Brier aggregates (descriptive S4)")
    rows = units[("internal_test", "B")]
    for c in C5:
        for region in REGIONS:
            vals = [
                recompute_unit(r) for r in rows if r["condition"] == c and r["region"] == region
            ]
            block = internal["descriptive_armB"].get(c, {}).get(region, {})
            for metric in ("ece", "brier"):
                xs = [v[metric] for v in vals if math.isfinite(v[metric])]
                if metric in block and xs:
                    st.add(
                        compare_number(
                            f"{c} {region} mean {metric}",
                            block[metric]["estimate"],
                            math.fsum(xs) / len(xs),
                        )
                    )
    return st.finish()


def recompute_failures(
    rows: Sequence[Mapping[str, str]], tau020: float
) -> dict[str, dict[str, list[str]]]:
    out: dict[str, dict[str, list[str]]] = {}
    for r in rows:
        x = recompute_unit(r)
        gt, pred = int(r["gt_voxels"]), int(r["pred_voxels"])
        cats = out.setdefault(
            r["condition"],
            {
                k: []
                for k in (
                    "confident_failure",
                    "hallucinated_ET",
                    "missed_ET",
                    "false_negative_WT",
                    "false_positive_WT",
                    "false_negative_TC",
                    "false_positive_TC",
                )
            },
        )
        if r["region"] == "ET":
            if x["U1"] >= tau020 and x["dice"] < 0.5:
                cats["confident_failure"].append(r["case_id"])
            if gt == 0 and pred > 0:
                cats["hallucinated_ET"].append(r["case_id"])
            if gt > 0 and pred == 0:
                cats["missed_ET"].append(r["case_id"])
        else:
            if gt > 0 and pred == 0:
                cats[f"false_negative_{r['region']}"].append(r["case_id"])
            if gt == 0 and pred > 0:
                cats[f"false_positive_{r['region']}"].append(r["case_id"])
    return {c: {k: sorted(v) for k, v in d.items()} for c, d in out.items()}


def stage_failures(
    units: Mapping[tuple[str, str], list[dict[str, str]]],
    failure_payload: Mapping[str, Any],
    tau020: float,
) -> Stage:
    st = Stage("FAILURES", "Failure categories rebuilt from primitive values")
    for ds, cats in failure_payload["categories"].items():
        rec = recompute_failures(units[(ds, "B")], tau020)
        for cond, block in cats.items():
            for k, ids in block["cases"].items():
                st.add(
                    expect(f"{ds} {cond} {k}: {len(ids)} cases", rec.get(cond, {}).get(k) == ids)
                )
    return st.finish()


# ------------------------------------------------------------------ Phase 17-18
def stage_tables(
    table_csv: Path,
    internal: Mapping[str, Any],
    boot: Mapping[str, Any],
    primary: Mapping[str, Any],
    out_csv: Path,
) -> Stage:
    st = Stage("TABLES", "Main results table rebuilt cell by cell")
    rows = read_rows(table_csv) if table_csv.is_file() else []
    if not rows:
        st.add(Check("main results table", FAIL, detail="missing"))
        return st.finish()
    expected: dict[tuple[str, str], dict[str, float]] = {
        ("primary H-W (internal, arm B, ET)", "mean over C4"): {
            "estimate": primary["mean_c4"],
            "ci_low": boot["mean_c4"]["ci_low"],
            "ci_high": boot["mean_c4"]["ci_high"],
            "p_two_sided": boot["mean_c4"]["p"],
        },
        **{
            ("S1/F1", c): {
                "estimate": primary[c]["delta"],
                "ci_low": boot[c]["ci_low"],
                "ci_high": boot[c]["ci_high"],
                "p_two_sided": boot[c]["p"],
            }
            for c in C4
        },
        ("Full control (descriptive)", "Full"): {
            "estimate": primary["Full"]["delta"],
            "ci_low": boot["Full"]["ci_low"],
            "ci_high": boot["Full"]["ci_high"],
        },
    }
    lines = []
    for (analysis, item), cells in expected.items():
        prod = next((r for r in rows if r["analysis"] == analysis and r["item"] == item), None)
        if prod is None:
            st.add(Check(f"row {analysis} / {item}", FAIL, detail="missing in production table"))
            continue
        for col, val in cells.items():
            c = compare_number(f"{analysis} / {item} / {col}", prod[col], val)
            st.add(c)
            lines.append(
                {
                    "table_id": "main_results",
                    "cell_id": f"{analysis}|{item}|{col}",
                    "production_value": prod[col],
                    "recomputed_value": repr(val),
                    "absolute_difference": repr(c.max_abs_diff),
                    "status": c.status,
                }
            )
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=[
                "table_id",
                "cell_id",
                "production_value",
                "recomputed_value",
                "absolute_difference",
                "status",
            ],
            lineterminator="\n",
        )
        w.writeheader()
        w.writerows(lines)
    return st.finish()


def independent_curve(
    units: Sequence[tuple[str, float, float]],
) -> list[tuple[float, float, float]]:
    """(coverage, selective risk, confidence) at k/n with expected tie handling."""
    order = sorted(units, key=lambda u: -u[1])
    n = len(order)
    risks: list[float] = []
    i = 0
    while i < n:
        j = i
        while j + 1 < n and order[j + 1][1] == order[i][1]:
            j += 1
        block = [order[k][2] for k in range(i, j + 1)]
        risks += [math.fsum(block) / len(block)] * len(block)
        i = j + 1
    out, cum = [], 0.0
    for k in range(n):
        cum = math.fsum(risks[: k + 1])
        out.append(((k + 1) / n, cum / (k + 1), order[k][1]))
    return out


def stage_figures(
    fig_dir: Path,
    units: Mapping[tuple[str, str], list[dict[str, str]]],
    internal: Mapping[str, Any],
    boot: Mapping[str, Any],
    primary: Mapping[str, Any],
) -> Stage:
    st = Stage("FIGURES", "Figure source data reconciled with recomputation")
    for path in sorted(fig_dir.glob("risk_coverage_*.csv")):
        ds = path.stem.replace("risk_coverage_", "")
        prod = read_rows(path)
        table = _cond_table(units[(ds, "B")], "ET")
        for c in C4:
            pts = [r for r in prod if r["condition"] == c]
            rec = independent_curve(table[c])
            st.add(expect(f"{ds} {c}: number of points = units", len(pts) == len(rec)))
            for j, name in enumerate(("coverage", "selective_risk", "confidence")):
                st.add(
                    compare_series(
                        f"{ds} {c}: {name}", [float(p[name]) for p in pts], [x[j] for x in rec]
                    )
                )
        st.add(
            expect(
                f"{ds}: conditions are exactly C4 in order",
                list(dict.fromkeys(r["condition"] for r in prod)) == list(C4),
            )
        )
    forest = fig_dir / "primary_delta_aurc_forest.csv"
    if forest.is_file():
        fp = {r["label"]: r for r in read_rows(forest)}
        for c in C4:
            st.add(compare_number(f"forest {c} estimate", fp[c]["estimate"], primary[c]["delta"]))
            st.add(compare_number(f"forest {c} CI low", fp[c]["ci_low"], boot[c]["ci_low"]))
            st.add(compare_number(f"forest {c} CI high", fp[c]["ci_high"], boot[c]["ci_high"]))
        st.add(
            compare_number(
                "forest H-W mean", fp["Mean over C4 (H-W)"]["estimate"], primary["mean_c4"]
            )
        )
    else:
        st.add(Check("primary forest source data", FAIL, detail="missing"))
    for img in sorted(list(fig_dir.glob("*.svg")) + list(fig_dir.glob("*.png"))):
        side = img.with_name(img.name + ".provenance.json")
        ok = side.is_file()
        if ok:
            meta = json.loads(side.read_text(encoding="utf-8"))
            src = fig_dir / meta.get("source_data", "")
            ok = src.is_file() and hashlib.sha256(src.read_bytes()).hexdigest() == meta.get(
                "source_data_sha256"
            )
        st.add(expect(f"{img.name}: generated from its hashed source data", ok))
    return st.finish()


# ------------------------------------------------------------------ Phase 21
def _strip(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _strip(v) for k, v in obj.items() if k not in ("generated_at", "content_sha256")}
    if isinstance(obj, list):
        return [_strip(x) for x in obj]
    return obj


def tree_digests(out: Path) -> dict[str, str]:
    d = {}
    for p in sorted(out.rglob("*")):
        if p.is_file() and p.suffix in (".json", ".csv"):
            if p.suffix == ".json":
                body = _strip(json.loads(p.read_text(encoding="utf-8")))
                data = json.dumps(body, sort_keys=True).encode()
            else:
                data = p.read_bytes()
            d[p.relative_to(out).as_posix()] = hashlib.sha256(data).hexdigest()
    return d


def stage_rerun(
    first: Path, rerun: Callable[[Path], None] | None, second: Path
) -> tuple[Stage, dict[str, Any]]:
    st = Stage("REPRODUCIBILITY", "Second complete analysis from the canonical inputs")
    if rerun is None:
        st.add(Check("second analysis run", NOT_PERFORMED, detail="no rerun configured"))
        return st.finish(), {}
    rerun(second)
    a, b = tree_digests(first), tree_digests(second)
    st.add(expect("same set of analysis outputs", set(a) == set(b)))
    for k in sorted(set(a) & set(b)):
        st.add(expect(f"{k} reproduced", a[k] == b[k]))
    first_hash = hashlib.sha256(json.dumps(a, sort_keys=True).encode()).hexdigest()
    second_hash = hashlib.sha256(json.dumps(b, sort_keys=True).encode()).hexdigest()
    return st.finish(), {
        "first_run_hash": first_hash,
        "second_run_hash": second_hash,
        "comparison_status": PASS if first_hash == second_hash else FAIL,
    }


__all__ = [
    "FAIL",
    "load_units",
    "recompute_unit",
    "stage_bootstrap",
    "stage_calibration",
    "stage_failures",
    "stage_figures",
    "stage_metrics",
    "stage_primary",
    "stage_rerun",
    "stage_statistics",
    "stage_tables",
    "stage_thresholds",
]
