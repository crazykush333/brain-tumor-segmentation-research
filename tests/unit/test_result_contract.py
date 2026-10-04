"""Result-artifact contract (metric records) and public-safe export. SYNTHETIC values only:
these records exist only inside pytest temporary directories and are never results."""

from __future__ import annotations

import gzip
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import pytest

from brats_uncertainty.errors import ProvenanceError
from brats_uncertainty.results.export import export_public_artifacts
from brats_uncertainty.results.metric_records import (
    DATASET_ROLES,
    METRICS,
    OPTIONAL,
    REQUIRED,
    validate_metric_file,
    validate_metric_record,
)
from tests.conftest import REPO_ROOT

SCHEMA = json.loads(
    (REPO_ROOT / "configs/schemas/result_metric.schema.json").read_text(encoding="utf-8")
)


def _rec(**over: Any) -> dict[str, Any]:
    r: dict[str, Any] = {
        "experiment_id": "MAIN",
        "condition": "-T1c",
        "metric": "delta_aurc",
        "value": -0.01,  # SYNTHETIC test value, not a result
        "unit": "proportion",
        "population": "SYNTHETIC test population",
        "dataset_role": "internal_test",
        "seed_or_ensemble": "ensemble",
        "arm": "B",
        "protocol_version": "v1.0",
        "git_commit": "f" * 40,
        "dataset_hash": "a" * 64,
        "split_hash": "b" * 64,
        "config_hash": "c" * 64,
        "synthetic": True,
    }
    r.update(over)
    return r


def _file(tmp: Path, records: list[dict[str, Any]], name: str = "x.metrics.json") -> Path:
    p = tmp / name
    p.write_text(json.dumps({"schema_version": 1, "records": records}), encoding="utf-8")
    return p


def test_schema_and_validator_agree() -> None:
    rec = SCHEMA["$defs"]["record"]
    assert tuple(rec["required"]) == REQUIRED
    assert set(rec["properties"]) == set(REQUIRED) | set(OPTIONAL)
    assert rec["properties"]["metric"]["enum"] == list(METRICS)
    assert rec["properties"]["dataset_role"]["enum"] == list(DATASET_ROLES)
    pattern = re.compile(rec["properties"]["condition"]["pattern"])
    for ok in ("Full", "-T1", "-T1c", "-T2", "-FLAIR", "C4_mean", "subset:T1+T2"):
        assert pattern.match(ok) and validate_metric_record(_rec(condition=ok)) is None
    for bad in ("T1c", "-T3", "subset:", "subset:T1+X", "C5"):
        assert not pattern.match(bad)
        with pytest.raises(ProvenanceError):
            validate_metric_record(_rec(condition=bad))


@pytest.mark.parametrize(
    ("over", "msg"),
    [
        ({"metric": "accuracy"}, "not in the result contract"),
        ({"unit": "count"}, "unit must be"),
        ({"value": 1.5}, "outside"),
        ({"value": float("nan")}, "finite"),
        ({"value": True}, "finite"),
        ({"metric": "n_cases", "unit": "count", "value": 3.5}, "integers"),
        ({"dataset_role": "test"}, "dataset_role"),
        ({"seed_or_ensemble": "seed:3"}, "seed_or_ensemble"),
        ({"arm": "C"}, "arm"),
        ({"protocol_version": "v0.9"}, "protocol_version"),
        ({"git_commit": "abc"}, "git_commit"),
        ({"split_hash": "x"}, "split_hash"),
        ({"synthetic": "no"}, "boolean"),
        ({"uncertainty": "U9"}, "uncertainty"),
        ({"ci_lower": -0.02}, "go together"),
        ({"ci_lower": 0.1, "ci_upper": -0.1, "ci_method": "percentile"}, "ci_lower >"),
        ({"ci_lower": -0.1, "ci_upper": 0.1}, "ci_method"),
        ({"p_value": 1.2}, "p_value"),
        ({"population": " "}, "population"),
        ({"surprise": 1}, "unknown"),
        ({"experiment_id": "main"}, "experiment_id"),
    ],
)
def test_invalid_records_fail_closed(over: dict[str, Any], msg: str) -> None:
    with pytest.raises(ProvenanceError, match=msg):
        validate_metric_record(_rec(**over))


def test_every_required_field_is_required() -> None:
    for field in REQUIRED:
        r = _rec()
        r.pop(field)
        with pytest.raises(ProvenanceError, match="missing"):
            validate_metric_record(r)


def test_metric_files(tmp_path: Path) -> None:
    good = _rec(ci_lower=-0.03, ci_upper=0.01, ci_method="percentile", p_value=0.2, n=10)
    assert len(validate_metric_file(_file(tmp_path, [good]), allow_synthetic=True)) == 1
    with pytest.raises(ProvenanceError, match="synthetic records can never be published"):
        validate_metric_file(_file(tmp_path, [good], "s.metrics.json"))
    with pytest.raises(ProvenanceError, match="duplicate"):
        validate_metric_file(_file(tmp_path, [good, good], "d.metrics.json"), allow_synthetic=True)
    (tmp_path / "v.metrics.json").write_text('{"schema_version": 2, "records": []}', "utf-8")
    with pytest.raises(ProvenanceError, match="schema_version"):
        validate_metric_file(tmp_path / "v.metrics.json")


# ================================================================ public-safe export
def _source(tmp: Path) -> Path:
    src = tmp / "remote_export"
    (src / "MAIN" / "arm_a_seed_0" / "fold_0").mkdir(parents=True)
    (src / "MAIN" / "arm_a_seed_0" / "run_manifest.json").write_text(
        json.dumps({"status": "FAILED"}), encoding="utf-8"
    )
    (src / "MAIN" / "arm_a_seed_0" / "fold_0" / "checkpoint_latest.pth").write_bytes(b"ckpt")
    (src / "MAIN" / "arm_a_seed_0" / "fold_0" / "training_log.txt").write_text("log", "utf-8")
    (src / "case.nii.gz").write_bytes(gzip.compress(b"\x00" * 64))
    (src / "UCSF-PDGM-metadata_v5.csv").write_text("ID\n", encoding="utf-8")
    (src / "table.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    return src


def test_export_copies_only_public_safe_files(tmp_path: Path) -> None:
    rep = export_public_artifacts(_source(tmp_path), tmp_path / "dest")
    assert rep.copied == [
        "MAIN/arm_a_seed_0/fold_0/training_log.txt",
        "MAIN/arm_a_seed_0/run_manifest.json",
        "table.csv",
    ]
    assert sorted(rep.skipped) == [
        "MAIN/arm_a_seed_0/fold_0/checkpoint_latest.pth",
        "UCSF-PDGM-metadata_v5.csv",
        "case.nii.gz",
    ]
    assert not list((tmp_path / "dest").rglob("*.pth"))
    with pytest.raises(FileExistsError):  # never overwrites
        export_public_artifacts(_source(tmp_path / "again"), tmp_path / "dest")


@pytest.mark.parametrize(
    ("make", "msg"),
    [
        (lambda s: (s / "disguised.json").write_bytes(gzip.compress(b"x" * 64)), "content under"),
        (
            lambda s: _file(s, [_rec()], "synthetic.metrics.json"),
            "synthetic records can never be published",
        ),
        (
            lambda s: (s / "run_manifest.json").write_text('{"status": "DONE"}', "utf-8"),
            "invalid run status",
        ),
    ],
)
def test_export_fails_closed_and_copies_nothing(tmp_path: Path, make, msg: str) -> None:  # type: ignore[no-untyped-def]
    src = _source(tmp_path)
    make(src)
    with pytest.raises(ProvenanceError, match=msg):
        export_public_artifacts(src, tmp_path / "dest")
    assert not (tmp_path / "dest").exists()


def test_export_refuses_links(tmp_path: Path) -> None:
    src = _source(tmp_path)
    target = tmp_path / "elsewhere"
    target.mkdir()
    try:
        os.symlink(target, src / "link", target_is_directory=True)
    except (OSError, NotImplementedError):
        if sys.platform != "win32":
            pytest.skip("cannot create directory links")
        import _winapi

        _winapi.CreateJunction(str(target), str(src / "link"))
    with pytest.raises(ProvenanceError, match="symbolic link"):
        export_public_artifacts(src, tmp_path / "dest")
