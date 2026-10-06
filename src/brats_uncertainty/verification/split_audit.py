"""Independent B8-B12 leakage and provenance audit (committed ID-level files only).

The audit deliberately re-implements the checks with the standard library and its
own union-find and hashing. It does not import the production grouping, split or
adjudication code, so a bug shared with the production code would not
automatically reproduce the same answer.

Inputs, all committed and ID-only:
- B7 flagged pairs;
- the B8 automated decisions and audit;
- the B6 counts record;
- the B9 patient groups;
- the B10-B12 split files and hashes;
- the protocol mirror (verified groups);
- the amendment's configuration file.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

SPLIT_SEED = 20260927
A3_CONFIG_SHA256 = "33c2410809b21ddde8a4a074dd886a61378624836a0d5c28356f33c1fea28428"
MAX_GROUP_SIZE = 8
LINKED = {"SAME_PATIENT", "UNRESOLVED"}
PARTITIONS = ("train", "validation", "internal_test")


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha_ids(ids: list[str]) -> str:
    return hashlib.sha256(("\n".join(sorted(ids)) + "\n").encode("utf-8")).hexdigest()


def _key(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a <= b else (b, a)


def _verified_groups(repo: Path) -> dict[str, list[str]]:
    import yaml

    raw = yaml.safe_load((repo / "configs/protocol/protocol_v1.0.yaml").read_text("utf-8"))
    groups: dict[str, list[str]] = raw["grouping"]["verified_groups"]
    return groups


def audit(repo: Path) -> dict[str, Any]:
    """Every check returns True/False; ``passed`` is the conjunction."""
    rec = repo / "docs/data/records"
    splits = repo / "splits"
    checks: dict[str, bool] = {}
    a5 = rec / "B8_A5" / "cohort.csv"
    if a5.is_file():
        return _audit_with_groups(repo, *_a5_b8_checks(repo, a5, checks))
    flagged = {_key(r["case_a"], r["case_b"]) for r in _rows(rec / "B7/flagged_pairs.csv")}
    decisions = {
        _key(r["case_a"], r["case_b"]): r for r in _rows(rec / "B8_automated_decisions.csv")
    }
    b8 = json.loads((rec / "B8_automated_audit.json").read_text("utf-8"))
    dec_counts = Counter(r["decision"] for r in decisions.values())
    rule_counts = Counter(r["rule"] for r in decisions.values())
    checks["b8_decisions_cover_exactly_the_flagged_pairs"] = set(decisions) == flagged
    checks["b8_counts_match_audit_record"] = (
        dict(dec_counts) == b8["decisions"] and dict(rule_counts) == b8["rules"]
    )
    checks["b8_acceptance_passed"] = bool(b8.get("accepted")) and all(b8["acceptance"].values())
    checks["a3_config_hash"] = (
        b8.get("config_sha256")
        == A3_CONFIG_SHA256
        == _sha_file(repo / "configs/grouping/b8_automated_v1.0-A3.yaml")
    )
    # B9 groups, recomputed independently: verified groups + linked decisions, transitively
    groups_rows = _rows(splits / "patient_groups_dev.csv")
    case_group = {r["case_id"]: r["group_id"] for r in groups_rows}
    dev = sorted(case_group)
    parent = {c: c for c in dev}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    verified = _verified_groups(repo)
    for members in verified.values():
        for m in members[1:]:
            union(members[0], m)
    for (a, b), r in decisions.items():
        if r["decision"] in LINKED:
            union(a, b)
    recomputed: dict[str, set[str]] = {}
    for c in dev:
        recomputed.setdefault(find(c), set()).add(c)
    produced: dict[str, set[str]] = {}
    for c, g in case_group.items():
        produced.setdefault(g, set()).add(c)
    checks["b9_groups_equal_independent_recomputation"] = sorted(
        map(sorted, recomputed.values())
    ) == sorted(map(sorted, produced.values()))
    sizes = sorted((len(v) for v in produced.values()), reverse=True)
    checks["b9_max_group_size_within_8"] = sizes[0] <= MAX_GROUP_SIZE if sizes else False
    # B6: the development set is exactly the site != 1 cohort recorded at B6
    b6 = json.loads((rec / "B6.json").read_text("utf-8"))
    checks["development_equals_b6_site_not_1_cohort"] = (
        _sha_ids(dev) == b6["development_ids_sha256"] and len(dev) == b6["counts"]["development"]
    )
    b8_summary = {
        "accepted": b8.get("accepted"),
        "n_flagged": len(flagged),
        "decisions": dict(sorted(dec_counts.items())),
        "rules": dict(sorted(rule_counts.items())),
        "tau_neg": b8.get("tau_neg"),
        "tau_ctrl": b8.get("tau_ctrl"),
        "controls": b8.get("controls"),
        "acceptance": b8.get("acceptance"),
        "config_sha256": b8.get("config_sha256"),
    }
    return _audit_with_groups(repo, checks, case_group, produced, b8_summary)


A5_CONFIG = "configs/grouping/b8_identity_clean_v1.0-A5.yaml"


def _a5_b8_checks(
    repo: Path, cohort_csv: Path, checks: dict[str, bool]
) -> tuple[dict[str, bool], dict[str, str], dict[str, set[str]], dict[str, Any]]:
    """Amendment v1.0-A5: cohorts and identity groups, recomputed independently."""
    rec = repo / "docs/data/records"
    rows = _rows(cohort_csv)
    summary = json.loads((rec / "B8_A5" / "summary.json").read_text("utf-8"))
    primary = sorted(r["case_id"] for r in rows if r["cohort"] == "primary")
    quarantine = sorted(r["case_id"] for r in rows if r["cohort"] == "quarantine")
    b6 = json.loads((rec / "B6.json").read_text("utf-8"))
    checks["a5_config_hash"] = summary.get("config_sha256") == _sha_file(repo / A5_CONFIG)
    checks["a5_acceptance_passed"] = bool(summary.get("accepted")) and all(
        summary["acceptance"].values()
    )
    checks["a5_independent_identity_verification"] = (
        summary["independent_verification"]["status"] == "VERIFIED"
    )
    checks["a5_primary_plus_quarantine_equals_b6_development"] = _sha_ids(
        primary + quarantine
    ) == b6["development_ids_sha256"] and not set(primary) & set(quarantine)
    checks["a5_quarantine_has_no_identity_key"] = all(
        not r["identity_key"] for r in rows if r["cohort"] == "quarantine"
    )
    # groups: same identity hash, plus verified groups (all members must be primary)
    parent = {c: c for c in primary}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    by_key: dict[str, list[str]] = {}
    for r in rows:
        if r["cohort"] == "primary":
            by_key.setdefault(r["identity_key"], []).append(r["case_id"])
    verified = _verified_groups(repo)
    for members in [*by_key.values(), *verified.values()]:
        ms = [m for m in members if m in parent]
        for m in ms[1:]:
            ra, rb = find(ms[0]), find(m)
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)
    recomputed: dict[str, set[str]] = {}
    for c in primary:
        recomputed.setdefault(find(c), set()).add(c)
    case_group = {
        r["case_id"]: r["group_id"] for r in _rows(repo / "splits/patient_groups_dev.csv")
    }
    produced: dict[str, set[str]] = {}
    for c, g in case_group.items():
        produced.setdefault(g, set()).add(c)
    checks["b9_groups_equal_independent_recomputation"] = sorted(
        map(sorted, recomputed.values())
    ) == sorted(map(sorted, produced.values()))
    checks["b9_covers_exactly_the_primary_cohort"] = sorted(case_group) == primary
    b8_summary = {
        "procedure": summary.get("procedure"),
        "accepted": summary.get("accepted"),
        "n_development_pool": summary.get("n_development_pool"),
        "n_primary": summary.get("n_primary"),
        "n_quarantine": summary.get("n_quarantine"),
        "config_sha256": summary.get("config_sha256"),
        "independent_identity_verification": summary["independent_verification"]["status"],
    }
    return checks, case_group, produced, b8_summary


def _audit_with_groups(
    repo: Path,
    checks: dict[str, bool],
    case_group: dict[str, str],
    produced: dict[str, set[str]],
    b8_summary: dict[str, Any],
) -> dict[str, Any]:
    """B10-B12 checks shared by every B8 procedure."""
    splits = repo / "splits"
    dev = sorted(case_group)
    sizes = sorted((len(v) for v in produced.values()), reverse=True)
    verified = _verified_groups(repo)
    # B10-B12 split
    split_rows = _rows(splits / "split_all.csv")
    part = {r["case_id"]: r["partition"] for r in split_rows}
    split_group = {r["case_id"]: r["group_id"] for r in split_rows}
    checks["split_covers_exactly_development"] = sorted(part) == dev
    checks["split_groups_equal_b9_groups"] = split_group == case_group
    checks["split_partitions_are_train_validation_test"] = set(part.values()) <= set(PARTITIONS)
    # a case absent from the split counts as its own partition (None): a failure, not a crash
    crossing = [g for g, ms in produced.items() if len({part.get(m) for m in ms}) != 1]
    checks["no_patient_group_crosses_partitions"] = not crossing
    checks["verified_groups_A_B_intact"] = all(
        len({case_group.get(m) for m in ms}) == 1
        and None not in {case_group.get(m) for m in ms}
        and len({part.get(m) for m in ms}) == 1
        for ms in verified.values()
    )
    summary = json.loads((splits / "split_summary.json").read_text("utf-8"))
    checks["split_seed_20260927"] = summary.get("seed") == SPLIT_SEED
    hashes = json.loads((splits / "split_hashes.json").read_text("utf-8"))
    checks["b12_split_hash_matches_file"] = hashes["split_all_csv_sha256"] == _sha_file(
        splits / "split_all.csv"
    )
    checks["b12_groups_hash_matches_file"] = hashes["patient_groups_dev_csv_sha256"] == _sha_file(
        splits / "patient_groups_dev.csv"
    )
    by_part: dict[str, list[str]] = {}
    for c, p in part.items():
        by_part.setdefault(p, []).append(c)
    checks["b12_partition_id_hashes_match"] = all(
        hashes["partition_id_list_sha256"].get(p) == _sha_ids(ids) for p, ids in by_part.items()
    )
    groups_per_part = {
        p: len({case_group.get(c) for c in ids}) for p, ids in sorted(by_part.items())
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "b8": b8_summary,
        "patient_groups": {
            "n_cases": len(dev),
            "n_groups": len(produced),
            "largest_group": sizes[0] if sizes else 0,
            "group_size_counts": {str(k): v for k, v in sorted(Counter(sizes).items())},
        },
        "split": {
            "seed": summary.get("seed"),
            "case_counts": {p: len(ids) for p, ids in sorted(by_part.items())},
            "group_counts": groups_per_part,
            "split_all_csv_sha256": hashes["split_all_csv_sha256"],
        },
        "crossing_groups": crossing,
    }


def render_report(result: dict[str, Any]) -> str:
    """Human-readable verdict of :func:`audit` (IDs, counts and hashes only)."""
    verdict = "VERIFIED" if result["passed"] else "FAILED"
    b8, pg, sp = result["b8"], result["patient_groups"], result["split"]
    lines = [
        "# Independent split verification (gates B8-B12)",
        "",
        f"OVERALL_SPLIT_VERIFICATION = {verdict}",
        "",
        "Produced by `brats-uncertainty audit-split` "
        "(`brats_uncertainty.verification.split_audit`), which re-derives the patient groups "
        "from committed records without importing the production grouping or split code.",
        "",
        f"- B8 procedure: {b8.get('procedure', 'automated_v1.0-A3')}",
    ]
    if "n_primary" in b8:
        lines.append(
            f"- development pool {b8.get('n_development_pool')}: primary (identity-clean) "
            f"{b8.get('n_primary')}, quarantine {b8.get('n_quarantine')} (never split)"
        )
    lines += [
        f"- patient groups: {pg['n_groups']} over {pg['n_cases']} cases; largest "
        f"{pg['largest_group']}; size counts {pg['group_size_counts']}",
        f"- split seed: {sp['seed']}",
        f"- cases per partition: {sp['case_counts']}",
        f"- groups per partition: {sp['group_counts']}",
        f"- split_all.csv SHA-256: `{sp['split_all_csv_sha256']}`",
        f"- groups crossing partitions: {len(result['crossing_groups'])}",
        "",
        "| Check | Result |",
        "|---|---|",
        *(f"| {k} | {'PASS' if ok else 'FAIL'} |" for k, ok in result["checks"].items()),
        "",
    ]
    return "\n".join(lines)
