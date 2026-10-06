"""Independent B8-B12 split audit on a SYNTHETIC, ID-only fixture."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from pathlib import Path

from brats_uncertainty.verification import split_audit as sa
from tests.conftest import REPO_ROOT

A = ("BraTS2021_00626", "BraTS2021_00758")
B = ("BraTS2021_00557", "BraTS2021_00639")
X = ("BraTS2021_99991", "BraTS2021_99992")


def _write(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def _ids(ids: list[str]) -> str:
    return hashlib.sha256(("\n".join(sorted(ids)) + "\n").encode()).hexdigest()


def _fixture(root: Path, *, partition_of: dict[str, str] | None = None) -> Path:
    for rel in (
        "configs/protocol/protocol_v1.0.yaml",
        "configs/grouping/b8_automated_v1.0-A3.yaml",
    ):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO_ROOT / rel, root / rel)
    rec, sp = root / "docs/data/records", root / "splits"
    _write(rec / "B7/flagged_pairs.csv", ["case_a", "case_b"], [list(A), list(B), list(X)])
    _write(
        rec / "B8_automated_decisions.csv",
        ["case_a", "case_b", "decision", "rule", "similarity", "coverage"],
        [
            [*A, "SAME_PATIENT", "R1", "", ""],
            [*B, "SAME_PATIENT", "R1", "", ""],
            [*X, "DIFFERENT_PATIENT", "R8", "0.1", "0.9"],
        ],
    )
    (rec / "B8_automated_audit.json").write_text(
        json.dumps(
            {
                "accepted": True,
                "acceptance": {"max_group_size": True},
                "decisions": {"DIFFERENT_PATIENT": 1, "SAME_PATIENT": 2},
                "rules": {"R1": 2, "R8": 1},
                "config_sha256": sa.A3_CONFIG_SHA256,
            }
        ),
        encoding="utf-8",
    )
    dev = sorted([*A, *B, *X])
    (rec / "B6.json").write_text(
        json.dumps({"counts": {"development": 6}, "development_ids_sha256": _ids(dev)}),
        encoding="utf-8",
    )
    group = {A[0]: "G1", A[1]: "G1", B[0]: "G2", B[1]: "G2", X[0]: "G3", X[1]: "G4"}
    part = partition_of or {
        A[0]: "train",
        A[1]: "train",
        B[0]: "internal_test",
        B[1]: "internal_test",
        X[0]: "validation",
        X[1]: "train",
    }
    _write(sp / "patient_groups_dev.csv", ["case_id", "group_id"], [[c, group[c]] for c in dev])
    _write(
        sp / "split_all.csv",
        ["case_id", "group_id", "partition"],
        [[c, group[c], part[c]] for c in dev],
    )
    (sp / "split_summary.json").write_text(json.dumps({"seed": 20260927}), encoding="utf-8")
    by: dict[str, list[str]] = {}
    for c, p in part.items():
        by.setdefault(p, []).append(c)
    (sp / "split_hashes.json").write_text(
        json.dumps(
            {
                "split_all_csv_sha256": hashlib.sha256(
                    (sp / "split_all.csv").read_bytes()
                ).hexdigest(),
                "patient_groups_dev_csv_sha256": hashlib.sha256(
                    (sp / "patient_groups_dev.csv").read_bytes()
                ).hexdigest(),
                "partition_id_list_sha256": {p: _ids(v) for p, v in by.items()},
            }
        ),
        encoding="utf-8",
    )
    return root


def test_consistent_split_passes(tmp_path: Path) -> None:
    r = sa.audit(_fixture(tmp_path))
    assert r["passed"], r["checks"]
    assert r["patient_groups"]["n_groups"] == 4 and r["split"]["seed"] == 20260927
    assert r["split"]["group_counts"] == {"internal_test": 1, "train": 2, "validation": 1}


def test_group_crossing_partitions_fails(tmp_path: Path) -> None:
    part = {A[0]: "train", A[1]: "internal_test", B[0]: "train", B[1]: "train"}
    part.update({X[0]: "validation", X[1]: "train"})
    r = sa.audit(_fixture(tmp_path, partition_of=part))
    assert not r["passed"]
    assert not r["checks"]["no_patient_group_crosses_partitions"]
    assert not r["checks"]["verified_groups_A_B_intact"]
    assert r["crossing_groups"] == ["G1"]


def test_tampered_split_file_breaks_the_b12_hash(tmp_path: Path) -> None:
    root = _fixture(tmp_path)
    p = root / "splits/split_all.csv"
    p.write_text(p.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    r = sa.audit(root)
    assert not r["checks"]["b12_split_hash_matches_file"] and not r["passed"]


Q = "BraTS2021_99993"  # no authoritative identity: quarantine


def _a5_fixture(root: Path, *, quarantine_in_split: bool = False) -> Path:
    """Amendment v1.0-A5 layout: B8_A5 cohort file; the split covers the primary cohort."""
    _fixture(root)
    rel = sa.A5_CONFIG
    shutil.copy(REPO_ROOT / rel, root / rel)
    rec = root / "docs/data/records"
    key = {A[0]: "k1", A[1]: "k1", B[0]: "k2", B[1]: "k3", X[0]: "k4", X[1]: "k5"}
    group = {A[0]: "G1", A[1]: "G1", B[0]: "G2", B[1]: "G2", X[0]: "G3", X[1]: "G4"}
    rows = [[c, "primary", key[c], group[c], "18", "UCSF-PDGM"] for c in sorted(key)]
    rows.append([Q, "quarantine", "", "", "18", "UCSF-PDGM_Additional"])
    _write(
        rec / "B8_A5/cohort.csv",
        ["case_id", "cohort", "identity_key", "group_id", "site", "collection"],
        rows,
    )
    (rec / "B8_A5/summary.json").write_text(
        json.dumps(
            {
                "procedure": "identity_clean_v1.0-A5",
                "accepted": True,
                "acceptance": {"verified_groups_intact": True},
                "config_sha256": hashlib.sha256((root / rel).read_bytes()).hexdigest(),
                "independent_verification": {"status": "VERIFIED"},
                "n_primary": 6,
                "n_quarantine": 1,
            }
        ),
        encoding="utf-8",
    )
    (rec / "B6.json").write_text(
        json.dumps({"development_ids_sha256": _ids([*key, Q]), "site_counts": {"1": 3, "18": 7}}),
        encoding="utf-8",
    )
    if quarantine_in_split:
        with (root / "splits/patient_groups_dev.csv").open("a", encoding="utf-8") as fh:
            fh.write(f"{Q},G5\n")
    return root


def test_a5_consistent_split_passes(tmp_path: Path) -> None:
    r = sa.audit(_a5_fixture(tmp_path))
    assert r["passed"], r["checks"]
    assert r["checks"]["a5_primary_plus_quarantine_equals_b6_development"]
    assert r["checks"]["b9_groups_equal_independent_recomputation"]
    assert r["b8"]["n_quarantine"] == 1 and r["patient_groups"]["n_groups"] == 4
    assert r["checks"]["a5_cohort_sites_match_b6_site_counts"] and r["checks"]["no_site1_in_split"]
    assert sum(r["split"]["site_counts"]["train"].values()) == 3


def test_a5_quarantined_case_in_groups_fails(tmp_path: Path) -> None:
    r = sa.audit(_a5_fixture(tmp_path, quarantine_in_split=True))
    assert not r["passed"]
    assert not r["checks"]["b9_covers_exactly_the_primary_cohort"]


def test_report_states_the_overall_verdict(tmp_path: Path) -> None:
    ok = sa.render_report(sa.audit(_a5_fixture(tmp_path / "ok")))
    assert "OVERALL_SPLIT_VERIFICATION = VERIFIED" in ok and "quarantine 1" in ok
    bad = sa.render_report(sa.audit(_a5_fixture(tmp_path / "bad", quarantine_in_split=True)))
    assert "OVERALL_SPLIT_VERIFICATION = FAILED" in bad
