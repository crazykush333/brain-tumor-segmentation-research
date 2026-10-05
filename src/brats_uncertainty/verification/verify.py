"""Result verification: run all stages, decide VERIFIED / BLOCKED, write the evidence.

Outputs (``results/verification/``): ``verification_manifest.json`` (stages, the verified
result index the website may display), ``result_records.json`` (lineage of every
published number), ``table_verification.csv``, ``public_artifact_hashes.json``,
``consistency_audit.json``, ``RESULT_VERIFICATION_CERTIFICATE.md`` and the quality-control
dashboard ``index.html``; plus ``docs/research/execution/RESULT_VERIFICATION_REPORT.md``.

A result is VERIFIED only if every required stage passes. Before real results exist the
state is NOT_RUN and the certificate says BLOCKED; nothing is ever marked PASS without a
check that actually ran.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from brats_uncertainty.verification import scientific as sci
from brats_uncertainty.verification.model import (
    FAIL,
    NOT_APPLICABLE,
    NOT_PERFORMED,
    OK,
    PASS,
    Check,
    Stage,
    compare_number,
    expect,
)

MANIFEST = "verification_manifest.json"
SCIENTIFIC_STAGES = (
    "DATA",
    "SPLIT",
    "RUNS",
    "CHECKPOINTS",
    "METRICS",
    "PRIMARY_AURC",
    "BOOTSTRAP",
    "THRESHOLDS",
    "STATISTICS",
    "CALIBRATION",
    "FAILURES",
    "EXTERNAL",
    "TABLES",
    "FIGURES",
    "LINEAGE",
    "REPRODUCIBILITY",
)
PUBLICATION_STAGES = ("WEBSITE", "PUBLIC_EXPORT")
OPTIONAL_STAGES = ("CLEAN_ENV",)  # recorded honestly; NOT_PERFORMED does not block
MAY_BE_NOT_APPLICABLE = ("EXTERNAL",)
DASHBOARD_ROWS = (
    ("DATA", "Data"),
    ("SPLIT", "Split"),
    ("RUNS", "Runs"),
    ("CHECKPOINTS", "Checkpoints"),
    ("METRICS", "Metrics"),
    ("PRIMARY_AURC", "Primary AURC"),
    ("BOOTSTRAP", "Bootstrap"),
    ("THRESHOLDS", "Thresholds"),
    ("STATISTICS", "Statistics"),
    ("CALIBRATION", "Calibration"),
    ("FAILURES", "Failure analysis"),
    ("EXTERNAL", "External sets"),
    ("TABLES", "Tables"),
    ("FIGURES", "Figures"),
    ("LINEAGE", "Lineage"),
    ("REPRODUCIBILITY", "Reproducibility rerun"),
    ("CLEAN_ENV", "Clean environment"),
    ("WEBSITE", "Website"),
    ("PUBLIC_EXPORT", "Public export"),
)


def _cid(cond: str) -> str:
    return "FULL" if cond == "Full" else "MINUS-" + cond[1:].upper()


@dataclass
class Lineage:
    """Upstream hashes and identities a published number must trace back to."""

    dataset_manifest_hash: str | None = None
    crosswalk_hash: str | None = None
    metadata_hash: str | None = None
    split_hash: str | None = None
    grouping_hash: str | None = None
    hoi_grouping_hash: str | None = None
    run_ids: dict[str, list[str]] = field(default_factory=dict)  # arm -> run ids
    environment_hashes: list[str] = field(default_factory=list)
    protocol_sha256: str | None = None


@dataclass
class VerificationResult:
    stages: dict[str, Stage]
    result_index: dict[str, dict[str, Any]]
    records: list[dict[str, Any]]
    rerun: dict[str, Any]
    analysis_commit: str

    @property
    def scientific_status(self) -> str:
        for sid in SCIENTIFIC_STAGES:
            st = self.stages.get(sid)
            if st is None:
                return "BLOCKED"
            if st.status in OK or (sid in MAY_BE_NOT_APPLICABLE and st.status == NOT_APPLICABLE):
                continue
            return "BLOCKED"
        return "VERIFIED"

    @property
    def overall(self) -> str:
        if self.scientific_status != "VERIFIED":
            return "BLOCKED"
        for sid in PUBLICATION_STAGES:
            st = self.stages.get(sid)
            if st is None or st.status not in OK:
                return "BLOCKED"
        return "VERIFIED"


# ------------------------------------------------------------------ scientific verification
def verify_scientific(
    *,
    units_dir: Path,
    frozen_path: Path,
    analysis_out: Path,
    out_dir: Path,
    provenance_stages: Sequence[Stage],
    lineage: Lineage,
    rerun: Callable[[Path], None] | None,
    rerun_dir: Path,
    clean_env: Stage | None = None,
    expected_replicates: int = sci.PROTOCOL_REPLICATES,
) -> VerificationResult:
    frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
    units = sci.load_units(units_dir)
    art = {
        p.stem: json.loads(p.read_text(encoding="utf-8"))
        for p in (analysis_out / "analysis").glob("*.json")
    }
    internal = art["internal_test_analysis"]["payload"]
    commit = art["internal_test_analysis"]["provenance"]["git_commit"]
    externals = {
        k.replace("_analysis", ""): v["payload"]
        for k, v in art.items()
        if k in ("upenn_hoi_analysis", "brats_africa_analysis")
    }
    families = art.get("families_F2_F3_F3b", {}).get("payload")
    transfers = art["threshold_transfer"]["payload"]
    stages: dict[str, Stage] = {s.id: s for s in provenance_stages}
    stages["METRICS"] = sci.stage_metrics(units, frozen)
    stages["PRIMARY_AURC"], primary = sci.stage_primary(units, internal)
    stages["BOOTSTRAP"], boot = sci.stage_bootstrap(
        units, internal, analysis_out / "bootstrap", expected_replicates
    )
    stages["THRESHOLDS"], thr = sci.stage_thresholds(
        units, frozen, transfers, analysis_out / "bootstrap"
    )
    stages["STATISTICS"] = (
        sci.stage_statistics(internal, boot, families, thr, externals)
        if boot
        else Stage("STATISTICS", "Holm families", [Check("bootstrap available", FAIL)]).finish()
    )
    stages["CALIBRATION"] = sci.stage_calibration(units, internal)
    stages["FAILURES"] = sci.stage_failures(
        units, art["failure_analysis"]["payload"], float(frozen["tau_q"]["0.20"]["tau"])
    )
    if primary and boot:
        stages["TABLES"] = sci.stage_tables(
            analysis_out / "tables/main_results.csv",
            internal,
            boot,
            primary,
            out_dir / "table_verification.csv",
        )
        stages["FIGURES"] = sci.stage_figures(
            analysis_out / "figures", units, internal, boot, primary
        )
    else:
        for sid in ("TABLES", "FIGURES"):
            stages[sid] = Stage(
                sid, sid.title(), [Check("primary and bootstrap available", FAIL)]
            ).finish()
    stages["REPRODUCIBILITY"], rer = sci.stage_rerun(analysis_out, rerun, rerun_dir)
    stages["CLEAN_ENV"] = clean_env or Stage(
        "CLEAN_ENV",
        "Clean-environment rerun",
        status=NOT_PERFORMED,
        detail="not performed in this run: a separate clean environment (pinned dependencies, "
        "frozen commit) was not available to the verifier",
    )
    index = build_result_index(internal, primary, boot, families, thr, externals)
    records, lineage_stage = build_lineage(index, lineage, art, commit)
    stages["LINEAGE"] = lineage_stage
    status = (
        "VERIFIED"
        if all(
            stages.get(s) is not None
            and (
                stages[s].status in OK
                or (s in MAY_BE_NOT_APPLICABLE and stages[s].status == NOT_APPLICABLE)
            )
            for s in SCIENTIFIC_STAGES
        )
        else "FAILED"
    )
    for r in records:
        r["verification_status"] = status
    return VerificationResult(stages, index, records, rer, commit)


def build_result_index(
    internal: Mapping[str, Any],
    primary: Mapping[str, Any],
    boot: Mapping[str, Any],
    families: Mapping[str, Any] | None,
    thr: Mapping[str, Any],
    externals: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    """Verified values the website may display (independent recomputation)."""
    if not primary or not boot:
        return {}
    idx: dict[str, dict[str, Any]] = {
        "PRIMARY-HW-C4-ET-DELTA-AURC": {
            "title": "Mean within-condition ET ΔAURC over C4 (U1 − I), internal test, arm B",
            "dataset": "internal_test",
            "arm": "B",
            "region": "ET",
            "condition": "C4 (equal weight)",
            "metric": "delta_aurc",
            "estimate": primary["mean_c4"],
            "ci_low": boot["mean_c4"]["ci_low"],
            "ci_high": boot["mean_c4"]["ci_high"],
            "p_value": boot["mean_c4"]["p"],
            "status": "supported" if boot["mean_c4"]["ci_high"] < 0 else "not supported",
            "analysis_id": "primary_HW",
        },
    }
    for c in sci.C4:
        idx[f"F1-{_cid(c)}-ET-DELTA-AURC"] = {
            "title": f"ET ΔAURC, condition {c}, internal test, arm B",
            "dataset": "internal_test",
            "arm": "B",
            "region": "ET",
            "condition": c,
            "metric": "delta_aurc",
            "estimate": primary[c]["delta"],
            "ci_low": boot[c]["ci_low"],
            "ci_high": boot[c]["ci_high"],
            "holm_p": internal["S1_F1"][c]["holm_p"],
            "analysis_id": "S1_F1",
        }
    idx["FULL-CONTROL-ET-DELTA-AURC"] = {
        "title": "ET ΔAURC, Full (descriptive control), internal test, arm B",
        "dataset": "internal_test",
        "arm": "B",
        "region": "ET",
        "condition": "Full",
        "metric": "delta_aurc",
        "estimate": primary["Full"]["delta"],
        "ci_low": boot["Full"]["ci_low"],
        "ci_high": boot["Full"]["ci_high"],
        "analysis_id": "full_control",
    }
    if families:
        for ds, v in families["F2"].items():
            idx[f"F2-{ds.upper()}-C4-ET-DELTA-AURC"] = {
                "title": f"Mean over C4 ET ΔAURC, {ds}, arm B",
                "dataset": ds,
                "arm": "B",
                "region": "ET",
                "condition": "C4 (equal weight)",
                "metric": "delta_aurc",
                "estimate": v["estimate"],
                "ci_low": externals[ds]["S8_mean_c4"]["ci_low"],
                "ci_high": externals[ds]["S8_mean_c4"]["ci_high"],
                "holm_p": v["holm_p"],
                "analysis_id": "F2",
            }
        for ds, v in families["F3_F3b"].items():
            idx[f"F3-{ds.upper()}-DELTA-RISK-Q080"] = {
                "title": f"Threshold transfer Δrisk at τ0.80, {ds}",
                "dataset": ds,
                "arm": "B",
                "region": "ET",
                "condition": "C4",
                "metric": "delta_risk",
                "estimate": v["delta_risk"],
                "holm_p": v["holm_p_risk"],
                "label": "unsafe transfer"
                if v["unsafe_transfer"]
                else "no evidence of unsafe transfer",
                "analysis_id": "F3",
            }
    return idx


def build_lineage(
    index: Mapping[str, Mapping[str, Any]], lin: Lineage, art: Mapping[str, Any], commit: str
) -> tuple[list[dict[str, Any]], Stage]:
    st = Stage("LINEAGE", "Every published number traces back to the frozen protocol")
    prov = art["internal_test_analysis"]["provenance"]
    records = []
    for rid, v in index.items():
        grouping = lin.hoi_grouping_hash if v["dataset"] == "upenn_hoi" else lin.grouping_hash
        rec = {
            "result_id": rid,
            "analysis_id": v["analysis_id"],
            "dataset_role": v["dataset"],
            "dataset_manifest_hash": lin.dataset_manifest_hash,
            "crosswalk_hash": lin.crosswalk_hash,
            "metadata_hash": lin.metadata_hash,
            "split_hash": lin.split_hash,
            "grouping_hash": grouping,
            "run_ids": lin.run_ids.get(v["arm"], []),
            "model_arm": v["arm"],
            "seeds": [0, 1, 2],
            "condition": v["condition"],
            "region": v["region"],
            "metric": v["metric"],
            "analysis_version": art["internal_test_analysis"]["content_sha256"],
            "git_commit": commit,
            "config_hash": prov.get("config_sha256"),
            "environment_hash": sorted(set(lin.environment_hashes)),
            "protocol_sha256": prov.get("protocol_sha256"),
            "created_at": prov.get("generated_at"),
        }
        missing = [k for k, val in rec.items() if val in (None, "", [])]
        if v["dataset"] == "brats_africa" and missing == ["grouping_hash"]:
            missing = []  # BraTS-Africa subjects are distinct patients (§6.2)
        st.add(expect(f"{rid}: complete lineage", not missing, f"missing: {missing}"))
        records.append(rec)
    st.add(
        expect(
            "protocol hash equals the frozen protocol",
            prov.get("protocol_sha256") == lin.protocol_sha256,
        )
    )
    if not index:
        st.add(Check("published numbers", FAIL, detail="no verified result index"))
    return records, st.finish()


# ------------------------------------------------------------------ publication checks
NUM = re.compile(
    r'data-result-id="([^"]+)"[^>]*data-field="([^"]+)"[^>]*data-value="([^"]+)"[^>]*>([^<]*)<'
)


def check_website(results_html: str, result: VerificationResult, *, decimals: int = 3) -> Stage:
    st = Stage("WEBSITE", "Rendered Results page reconciled with the verified index")
    shown = NUM.findall(results_html)
    text = re.sub(r"<[^>]+>", " ", results_html)
    st.add(
        expect(
            "no synthetic/demo content on the Results page",
            "SYNTHETIC" not in text.upper() and "NOT SCIENTIFIC RESULT" not in text.upper(),
        )
    )
    if result.scientific_status != "VERIFIED":
        st.add(expect("no scientific number shown before verification", not shown))
        return st.finish()
    st.add(
        expect(
            "every verified primary/F1 result is displayed",
            {rid for rid, *_ in shown}
            >= {k for k in result.result_index if k.startswith(("PRIMARY", "F1"))},
        )
    )
    for rid, fld, value, display in shown:
        ref = result.result_index.get(rid)
        if ref is None or fld not in ref:
            st.add(
                Check(
                    f"{rid}.{fld}",
                    FAIL,
                    value,
                    None,
                    detail="not in the verified index (stale or placeholder)",
                )
            )
            continue
        st.add(compare_number(f"{rid}.{fld} value", ref[fld], value))
        st.add(
            expect(
                f"{rid}.{fld} display rounding",
                display.strip() == f"{float(ref[fld]):.{decimals}f}",
                f"shown {display.strip()!r}",
            )
        )
    return st.finish()


def check_public_export(files: Sequence[Path], repo_root: Path) -> tuple[Stage, dict[str, str]]:
    from brats_uncertainty.demo import is_demo_artifact
    from brats_uncertainty.repo_checks import (
        PROHIBITED_NAME_PATTERNS,
        PROHIBITED_NAMES,
        PROHIBITED_SUFFIXES,
    )
    from brats_uncertainty.results.export import ALLOWED_SUFFIXES

    st = Stage("PUBLIC_EXPORT", "Published scientific artifacts: type, content and SHA-256")
    hashes = {}
    for p in sorted(files):
        rel = p.relative_to(repo_root).as_posix()
        ok = (
            (p.suffix in ALLOWED_SUFFIXES or rel.endswith(".html"))
            and not p.name.endswith(PROHIBITED_SUFFIXES)
            and p.name not in PROHIBITED_NAMES
            and not any(pat.match(p.name) for pat in PROHIBITED_NAME_PATTERNS)
        )
        st.add(expect(f"{rel}: public-safe type", ok))
        st.add(expect(f"{rel}: not a synthetic demo file", not is_demo_artifact(p)))
        hashes[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    if not files:
        st.add(Check("published files", FAIL, detail="nothing to publish"))
    return st.finish(), hashes


# ------------------------------------------------------------------ consistency audit
AUDIT = (
    ("Did the actual data match the declared dataset?", "DATA", None),
    ("Did the final split match the frozen protocol?", "SPLIT", None),
    ("Did every model use the correct seed?", "RUNS", "identity"),
    ("Did every ensemble contain exactly the intended members?", "RUNS", None),
    ("Were the correct four C4 conditions used?", "PRIMARY_AURC", "exactly C4"),
    ("Was Full excluded from the primary C4 estimand?", "PRIMARY_AURC", "Full excluded"),
    ("Was ET used rather than TC/WT for the primary result?", "PRIMARY_AURC", None),
    ("Was I computed correctly?", "THRESHOLDS", "I arm"),
    ("Was U1 computed correctly?", "METRICS", ": U1"),
    ("Was AURC computed correctly?", "PRIMARY_AURC", "AURC("),
    ("Was Delta-AURC computed correctly?", "PRIMARY_AURC", "ΔAURC"),
    ("Was C4 equally weighted?", "PRIMARY_AURC", "equal-weight"),
    ("Were bootstrap units patient groups?", "BOOTSTRAP", "patient group"),
    ("Was bootstrap seed 12345 used?", "BOOTSTRAP", "seed 12345"),
    ("Were 10,000 replicates used?", "BOOTSTRAP", "10,000"),
    ("Were validation-derived thresholds estimated only on validation?", "THRESHOLDS", "τ_"),
    ("Was internal test excluded from tuning?", "THRESHOLDS", None),
    ("Was external data excluded from training/tuning?", "EXTERNAL", None),
    ("Were Holm corrections applied only to their declared families?", "STATISTICS", "Holm"),
    ("Were descriptive analyses kept descriptive?", "STATISTICS", "descriptive"),
    ("Did figures match tables?", "FIGURES", None),
    ("Did website numbers match verified artifacts?", "WEBSITE", None),
    ("Did GitHub artifacts match the verified result set?", "PUBLIC_EXPORT", None),
)


def consistency_audit(stages: Mapping[str, Stage]) -> list[dict[str, str]]:
    out = []
    for q, sid, needle in AUDIT:
        st = stages.get(sid)
        if st is None or st.status == NOT_PERFORMED:
            ans = FAIL
        elif st.status == NOT_APPLICABLE:
            ans = NOT_APPLICABLE
        else:
            checks = [c for c in st.checks if needle is None or needle in c.name]
            ans = (
                PASS
                if checks and all(c.status in OK or c.status == NOT_APPLICABLE for c in checks)
                else FAIL
            )
        out.append({"question": q, "answer": ans, "stage": sid})
    return out


# ------------------------------------------------------------------ writers
def _stage_dicts(stages: Mapping[str, Stage]) -> list[dict[str, Any]]:
    return [stages[s].to_dict() for s, _ in DASHBOARD_ROWS if s in stages]


def write_outputs(
    result: VerificationResult, out_dir: Path, report_path: Path, public_hashes: Mapping[str, str]
) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC).replace(microsecond=0).isoformat()
    audit = consistency_audit(result.stages)
    manifest = {
        "overall": result.overall,
        "scientific_status": result.scientific_status,
        "generated_at": now,
        "analysis_git_commit": result.analysis_commit,
        "stages": _stage_dicts(result.stages),
        "result_index": result.result_index if result.scientific_status == "VERIFIED" else {},
        "reproducibility": result.rerun,
        "consistency_audit": audit,
    }
    paths = {
        "manifest": out_dir / MANIFEST,
        "records": out_dir / "result_records.json",
        "hashes": out_dir / "public_artifact_hashes.json",
        "audit": out_dir / "consistency_audit.json",
        "certificate": out_dir / "RESULT_VERIFICATION_CERTIFICATE.md",
        "dashboard": out_dir / "index.html",
    }
    _dump(paths["manifest"], manifest)
    _dump(paths["records"], {"records": result.records})
    _dump(paths["hashes"], dict(public_hashes))
    _dump(paths["audit"], {"questions": audit})
    paths["certificate"].write_text(certificate(result), encoding="utf-8", newline="\n")
    paths["dashboard"].write_text(
        dashboard(result.stages, result.overall, now), encoding="utf-8", newline="\n"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report(result, audit, now), encoding="utf-8", newline="\n")
    return paths


def _dump(path: Path, obj: Any) -> None:
    path.write_text(
        json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _word(st: Stage | None, ok_word: str = "verified") -> str:
    if st is None:
        return "not run"
    return ok_word if st.status in OK else st.status


def certificate(result: VerificationResult) -> str:
    s = result.stages
    rer = s.get("REPRODUCIBILITY")
    rerun_word = "PASS" if rer and rer.status in OK else (rer.status if rer else NOT_PERFORMED)
    clean_word = s["CLEAN_ENV"].status if "CLEAN_ENV" in s else NOT_PERFORMED
    lines = [
        "# Result verification certificate",
        "",
        "| Item | Status |",
        "|---|---|",
        "| Protocol | protocol-v1.0 (SHA-256 "
        "704c0b495917344f44b93e7548ade0e32a71220265419516a2c83d626fcd9811) |",
        f"| Data | {_word(s.get('DATA'))} |",
        f"| Split | {_word(s.get('SPLIT'))} |",
        f"| Training runs | {_word(s.get('RUNS'))} |",
        f"| Inference / checkpoints | {_word(s.get('CHECKPOINTS'))} |",
        f"| Primary metric | {_word(s.get('PRIMARY_AURC'), 'independently recomputed')} |",
        f"| Bootstrap | {_word(s.get('BOOTSTRAP'), 'independently recomputed')} |",
        f"| Tables | {_word(s.get('TABLES'), 'cross-checked')} |",
        f"| Figures | {_word(s.get('FIGURES'), 'cross-checked')} |",
        f"| Website | {_word(s.get('WEBSITE'), 'cross-checked')} |",
        f"| Public artifacts | {_word(s.get('PUBLIC_EXPORT'), 'hash-verified')} |",
        f"| Reproducibility rerun | {rerun_word} |",
        f"| Clean-environment rerun | {clean_word} |",
        "",
        f"**Overall verification: {result.overall}**",
        "",
    ]
    failed = [
        (st.id, c) for st in s.values() for c in st.checks if c.status in (FAIL, NOT_PERFORMED)
    ]
    if failed:
        lines += ["## Blocking checks", ""]
        lines += [f"- {sid}: {c.name} — {c.status} {c.detail}".rstrip() for sid, c in failed[:50]]
    return "\n".join(lines) + "\n"


def dashboard(stages: Mapping[str, Stage], overall: str, now: str) -> str:
    color = {
        PASS: "#15803d",
        "PASS_WITH_FLOAT_TOLERANCE": "#15803d",
        FAIL: "#b91c1c",
        NOT_PERFORMED: "#a16207",
        NOT_APPLICABLE: "#475569",
        "NOT_RUN": "#475569",
    }
    rows = []
    for sid, label in DASHBOARD_ROWS:
        st = stages.get(sid)
        status = st.status if st else "NOT_RUN"
        detail = html.escape(st.detail) if st else ""
        n = f"{len(st.checks)} checks" if st and st.checks else ""
        rows.append(
            f"<tr><th>{html.escape(label)}</th>"
            f'<td style="color:{color.get(status, "#475569")};font-weight:600">'
            f"{html.escape(status)}</td><td>{n}</td><td>{detail}</td></tr>"
        )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" '
        'content="width=device-width,initial-scale=1"><title>Result verification dashboard</title>'
        "<style>body{font-family:system-ui,sans-serif;max-width:900px;margin:2rem auto;"
        "padding:0 1rem;color:#0f172a}table{border-collapse:collapse;width:100%}"
        "th,td{text-align:left;padding:.4rem .6rem;border-bottom:1px solid #e2e8f0;"
        "font-size:.9rem}th{width:12rem}</style></head><body>"
        "<h1>Result verification dashboard</h1><p>Reproducibility / quality-control status of "
        "the result pipeline. <strong>This is not a scientific result page.</strong></p>"
        f"<p>Overall: <strong>{html.escape(overall)}</strong> · generated {html.escape(now)}</p>"
        f"<table>{''.join(rows)}</table></body></html>\n"
    )


def report(result: VerificationResult, audit: Sequence[Mapping[str, str]], now: str) -> str:
    lines = [
        "# Result verification report",
        "",
        f"Generated {now}. Overall: **{result.overall}** "
        f"(scientific stages: {result.scientific_status}).",
        "",
        "Verification protocol: "
        "[RESULT_VERIFICATION_PROTOCOL.md](RESULT_VERIFICATION_PROTOCOL.md).",
        "",
        "## Stages",
        "",
        "| Stage | Status | Checks | Failed | Detail |",
        "|---|---|---|---|---|",
    ]
    for sid, label in DASHBOARD_ROWS:
        st = result.stages.get(sid)
        if st is None:
            lines.append(f"| {label} | NOT_RUN | 0 | 0 | |")
        else:
            nf = sum(c.status in (FAIL, NOT_PERFORMED) for c in st.checks)
            lines.append(f"| {label} | {st.status} | {len(st.checks)} | {nf} | {st.detail} |")
    lines += ["", "## Discrepancies", ""]
    disc = [
        (st.id, c)
        for st in result.stages.values()
        for c in st.checks
        if c.status in (FAIL, NOT_PERFORMED)
    ]
    if not disc:
        lines.append("None.")
    for sid, c in disc:
        lines.append(
            f"- **{sid} / {c.name}**: {c.status}; production `{c.production}` vs recomputed "
            f"`{c.recomputed}`; max |Δ| {c.max_abs_diff:.3g}. {c.detail} Required action: "
            "correct the cause, re-run the affected analysis stage and re-verify; the result is "
            "not published."
        )
    tol = [
        (st.id, c)
        for st in result.stages.values()
        for c in st.checks
        if c.status == "PASS_WITH_FLOAT_TOLERANCE"
    ]
    lines += ["", "## Floating-point tolerances used", ""]
    lines += [
        f"- {sid} / {c.name}: max |Δ| {c.max_abs_diff:.3g}, max rel {c.max_rel_diff:.3g}"
        for sid, c in tol
    ] or ["None."]
    lines += [
        "",
        "## Scientific consistency audit",
        "",
        "| # | Question | Answer |",
        "|---|---|---|",
    ]
    lines += [f"| {i} | {a['question']} | {a['answer']} |" for i, a in enumerate(audit, 1)]
    if result.rerun:
        lines += [
            "",
            "## Reproducibility rerun",
            "",
            f"- first_run_hash: `{result.rerun.get('first_run_hash')}`",
            f"- second_run_hash: `{result.rerun.get('second_run_hash')}`",
            f"- comparison_status: {result.rerun.get('comparison_status')}",
        ]
    lines += development_discrepancies_md()
    return "\n".join(lines) + "\n"


# Discrepancies the verifier found in the production code during development (before any
# real result existed). Kept permanently in every report.
DEVELOPMENT_DISCREPANCIES = (
    {
        "found_on": "2026-10-05",
        "stage": "THRESHOLDS",
        "what": "transfer bootstrap p-value for delta-coverage at tau_0.80 (synthetic test "
        "study): production 0.30 vs independent recomputation 0.32",
        "cause": "production computed the condition-weighted coverage in floating point, so an "
        "exactly zero delta-coverage became +/- 1e-17 and was counted on the wrong side of "
        "zero in the bootstrap p-value",
        "correction": "production weighted_coverage_risk (statistics/thresholds.py) now "
        "computes the equal-weight coverage exactly with rational arithmetic; the verifier "
        "does the same independently",
        "reruns": "no real analysis had been run, so no real result was affected; the "
        "synthetic test study was re-run and every stage then passed",
    },
)


def development_discrepancies_md() -> list[str]:
    lines = ["", "## Discrepancies found and corrected during development", ""]
    for d in DEVELOPMENT_DISCREPANCIES:
        lines.append(
            f"- **{d['stage']}** ({d['found_on']}): {d['what']}. Cause: {d['cause']}. "
            f"Correction: {d['correction']}. Reruns: {d['reruns']}."
        )
    return lines


def write_pending(out_dir: Path, report_path: Path, reason: str) -> None:
    """State before any real result exists: NOT_RUN everywhere, certificate BLOCKED."""
    stages = {
        sid: Stage(sid, label, status="NOT_RUN", detail=reason) for sid, label in DASHBOARD_ROWS
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    now = "pending"
    _dump(
        out_dir / MANIFEST,
        {
            "overall": "NOT_RUN",
            "scientific_status": "NOT_RUN",
            "reason": reason,
            "result_index": {},
            "stages": [
                {"id": sid, "title": label, "status": "NOT_RUN", "detail": reason}
                for sid, label in DASHBOARD_ROWS
            ],
        },
    )
    (out_dir / "table_verification.csv").write_text(
        "table_id,cell_id,production_value,recomputed_value,absolute_difference,status\n",
        encoding="utf-8",
        newline="\n",
    )
    _dump(out_dir / "public_artifact_hashes.json", {})
    _dump(out_dir / "result_records.json", {"records": []})
    _dump(
        out_dir / "consistency_audit.json",
        {"questions": [{"question": q, "answer": "NOT_RUN", "stage": sid} for q, sid, _ in AUDIT]},
    )
    (out_dir / "RESULT_VERIFICATION_CERTIFICATE.md").write_text(
        "# Result verification certificate\n\n"
        "**Overall verification: BLOCKED — no real scientific result exists yet.**\n\n"
        f"{reason}\n\nNo stage has run; nothing is marked PASS. This certificate is regenerated by "
        "the verifier after the real analysis.\n",
        encoding="utf-8",
        newline="\n",
    )
    (out_dir / "index.html").write_text(
        dashboard(stages, "NOT_RUN", now), encoding="utf-8", newline="\n"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        "# Result verification report\n\n**Status: NOT_RUN.** "
        + reason
        + "\n\nThe verification system "
        "([RESULT_VERIFICATION_PROTOCOL.md](RESULT_VERIFICATION_PROTOCOL.md)) runs automatically "
        "after the real analysis (master-run step VERIFY). Until then no result is verified or "
        "published.\n" + "\n".join(development_discrepancies_md()) + "\n",
        encoding="utf-8",
        newline="\n",
    )


__all__ = [
    "Lineage",
    "VerificationResult",
    "check_public_export",
    "check_website",
    "consistency_audit",
    "verify_scientific",
    "write_outputs",
    "write_pending",
]
