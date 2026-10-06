"""Regression guards on the frozen protocol v1.0 and its machine-readable mirror."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest
import yaml

from brats_uncertainty.protocol import load_protocol
from brats_uncertainty.utils.git import git_tag_commit
from brats_uncertainty.utils.hashing import sha256_bytes, sha256_text_lf

FROZEN = "docs/research/FINAL_RESEARCH_PROTOCOL_v1.0.md"
FROZEN_SHA256 = "704c0b495917344f44b93e7548ade0e32a71220265419516a2c83d626fcd9811"
TAG_COMMIT = "4ef7ef707abafce4314884c6f271969b5bfbec32"


def test_frozen_protocol_hash(repo_root: Path) -> None:
    assert sha256_text_lf(repo_root / FROZEN) == FROZEN_SHA256


def test_frozen_protocol_equals_tagged_blob(repo_root: Path) -> None:
    """The working copy (LF-normalized) is byte-identical to the file at tag protocol-v1.0."""
    try:
        blob = subprocess.run(
            ["git", "show", f"protocol-v1.0:{FROZEN}"],
            cwd=repo_root,
            capture_output=True,
            check=True,
            timeout=30,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("git metadata or tag not available (e.g. source archive)")
    assert sha256_bytes(blob) == FROZEN_SHA256
    assert (repo_root / FROZEN).read_bytes().replace(b"\r\n", b"\n") == blob


def test_protocol_tag_untouched(repo_root: Path) -> None:
    commit = git_tag_commit(repo_root, "protocol-v1.0")
    if commit is None:
        pytest.skip("git metadata or tag not available (e.g. source archive)")
    assert commit == TAG_COMMIT


def test_only_one_active_protocol_file(repo_root: Path) -> None:
    candidates = [
        p.relative_to(repo_root).as_posix()
        for p in (repo_root / "docs").rglob("*")
        if p.is_file() and "FINAL_RESEARCH_PROTOCOL" in p.name.upper()
    ]
    active = [c for c in candidates if not c.startswith("docs/research/archive/")]
    assert active == [FROZEN]


def test_yaml_mirror_matches_protocol_values(repo_root: Path) -> None:
    spec = load_protocol(repo_root)
    text = (repo_root / FROZEN).read_text(encoding="utf-8")
    assert spec.version == "v1.0"
    assert spec.channel_order == ("T1", "T1c", "T2", "FLAIR")
    assert "`[T1, T1c, T2, FLAIR]`" in text
    assert spec.split_seed == 20260927 and "`20260927`" in text
    assert spec.bootstrap_seed == 12345 and "`12345`" in text
    assert spec.bootstrap_replicates == 10000 and "10,000" in text
    assert spec.training_seeds == (0, 1, 2)
    assert spec.split_proportions == {"train": 0.7, "validation": 0.1, "internal_test": 0.2}
    assert "70 / 10 / 20" in text
    assert spec.q_primary == 0.80 and spec.q_sensitivity == (0.70, 0.90)
    assert spec.failure_analysis_q == 0.20 and "τ_0.20" in text
    assert spec.dropout_p_full == 0.5 and "with probability 0.5 the input is full" in text
    assert spec.roi_dilation_voxels == 3 and "dilated by 3 voxels" in text
    assert spec.ece_bins == 15 and "15 equal-width bins" in text
    assert spec.c4 == ("-T1", "-T1c", "-T2", "-FLAIR")
    assert spec.c5 == ("Full", "-T1", "-T1c", "-T2", "-FLAIR")
    assert spec.reviewers == ("Ayush Kushwaha", "Dr. Sreenivasa Chakravarthi")
    for name, ids in spec.verified_groups.items():
        assert f"**{name}** | {ids[0]}, {ids[1]}" in text
    inf = spec.inference
    assert inf == {"sliding_window_step": 0.5, "mirroring": False, "threshold": 0.5}
    assert "step 0.5, **mirroring off**, threshold 0.5" in text
    raw = spec.raw
    assert raw["grouping"]["t_screen_value"] is None  # never set by hand
    assert raw["cohorts"]["hoi_count"] == 511 and "**511**" in text
    assert raw["cohorts"]["development_count_before_grouping"] == 740 and "**740 cases**" in text
    assert raw["compute"]["cap_gpu_hours"] == 220 and "220 GPU-h" in text
    assert raw["metrics"]["volume_failure"]["relative_error_threshold"] == 0.40 and "40%" in text


def test_package_constants_match_protocol(repo_root: Path) -> None:
    from brats_uncertainty.metrics.calibration import PROTOCOL_ECE_BINS
    from brats_uncertainty.models.dropout import PROTOCOL_P_FULL
    from brats_uncertainty.models.nnunet import PROTOCOL_EPOCHS, PROTOCOL_SEEDS
    from brats_uncertainty.splitting.split import PROTOCOL_PROPORTIONS, PROTOCOL_SPLIT_SEED
    from brats_uncertainty.statistics.bootstrap import PROTOCOL_REPLICATES, PROTOCOL_SEED
    from brats_uncertainty.statistics.thresholds import FAILURE_ANALYSIS_Q, PROTOCOL_Q

    spec = load_protocol(repo_root)
    assert spec.ece_bins == PROTOCOL_ECE_BINS
    assert spec.dropout_p_full == PROTOCOL_P_FULL
    assert spec.raw["model"]["epochs"] == PROTOCOL_EPOCHS
    assert spec.training_seeds == PROTOCOL_SEEDS
    assert spec.split_seed == PROTOCOL_SPLIT_SEED
    assert tuple(spec.split_proportions.values()) == PROTOCOL_PROPORTIONS
    assert spec.bootstrap_replicates == PROTOCOL_REPLICATES
    assert spec.bootstrap_seed == PROTOCOL_SEED
    assert (spec.q_primary, *spec.q_sensitivity) == PROTOCOL_Q
    assert spec.failure_analysis_q == FAILURE_ANALYSIS_Q


def test_readme_status_line_matches_status_file(repo_root: Path) -> None:
    status = yaml.safe_load((repo_root / "docs/project_status.yaml").read_text(encoding="utf-8"))
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    assert status["headline"] in readme.split("\n\n")[1]


def test_no_numeric_results_in_results_tree(repo_root: Path) -> None:
    """Until results.available, results/ holds only README.md, the generated status.json
    (which declares that no results exist), the flagged synthetic demonstration and the
    pending (NOT_RUN, value-free) verification evidence."""
    import json

    from brats_uncertainty.demo import is_demo_artifact

    status = yaml.safe_load((repo_root / "docs/project_status.yaml").read_text(encoding="utf-8"))
    if status["results"]["available"]:
        return  # results exist: they are checked through results/index.json (site export)
    for p in (repo_root / "results").rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(repo_root).as_posix()
        if rel == "results/README.md":
            assert "No real scientific results are available" in p.read_text(encoding="utf-8")
        elif rel == "results/verification/verification_manifest.json":
            body = json.loads(p.read_text(encoding="utf-8"))
            assert body["scientific_status"] != "VERIFIED" and body["result_index"] == {}
        elif rel.startswith("results/verification/A5_IDENTITY_VERIFICATION.") or rel in (
            "results/verification/split_audit.json",
            "results/verification/SPLIT_VERIFICATION_REPORT.md",
        ):
            # B8 identity and B8-B12 split verification: IDs, counts, hashes; no result values
            text = p.read_text(encoding="utf-8")
            assert "AURC" not in text and "Dice" not in text, rel
        elif rel.startswith("results/MAIN/runs/") and rel.endswith(
            ("/run_manifest.json", "/failure_log.json")
        ):
            # training provenance (identity, attempts, checkpoint hashes): no metric values
            text = p.read_text(encoding="utf-8").lower()
            assert "dice" not in text and "aurc" not in text, rel
        elif rel.startswith("results/EXP-001/"):
            # EXP-001 compute measurements (D4): no label-based metric may appear
            text = p.read_text(encoding="utf-8").lower()
            assert "dice" not in text and "aurc" not in text, rel
        elif rel.startswith("results/verification/"):
            text = p.read_text(encoding="utf-8")
            assert "VERIFIED" not in text.replace("NOT VERIFIED", ""), rel
        elif rel == "results/status.json":
            body = json.loads(p.read_text(encoding="utf-8"))
            assert body["scientific_results_available"] is False
            assert body["real_experiment_executed"] is False
            assert body["synthetic_results_in_scientific_namespace"] is False
        else:
            assert rel.startswith("results/demo/") and is_demo_artifact(p), rel


def test_protocol_mirror_integrity_check_fails_on_tamper(tmp_path: Path, repo_root: Path) -> None:
    import shutil

    from brats_uncertainty.errors import ProtocolIntegrityError

    (tmp_path / "configs/protocol").mkdir(parents=True)
    (tmp_path / "docs/research").mkdir(parents=True)
    shutil.copy(repo_root / "configs/protocol/protocol_v1.0.yaml", tmp_path / "configs/protocol/")
    text = (repo_root / FROZEN).read_text(encoding="utf-8")
    (tmp_path / FROZEN).write_text(re.sub("0.80", "0.85", text, count=1), encoding="utf-8")
    with pytest.raises(ProtocolIntegrityError, match="SHA-256 mismatch"):
        load_protocol(tmp_path)
