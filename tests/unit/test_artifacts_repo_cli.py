from __future__ import annotations

from pathlib import Path

import pytest

from brats_uncertainty.cli import main
from brats_uncertainty.errors import ProvenanceError
from brats_uncertainty.repo_checks import check_paths
from brats_uncertainty.results.artifacts import (
    ArtifactProvenance,
    ResultArtifact,
    read_artifact,
    write_artifact,
)


def _prov(synthetic: bool = True, commit: str = "a" * 40) -> ArtifactProvenance:
    return ArtifactProvenance(
        experiment_id="EXP-999",
        git_commit=commit,
        config_sha256="b" * 64,
        protocol_sha256="c" * 64,
        input_sha256={"units.csv": "d" * 64},
        generated_at="2000-01-01T00:00:00Z",
        synthetic=synthetic,
    )


def test_artifact_roundtrip_and_tamper_detection(tmp_path: Path) -> None:
    art = ResultArtifact("metric_table", "synthetic", {"x": 1}, _prov())
    p = write_artifact(tmp_path / "a.json", art)
    assert read_artifact(p)["payload"] == {"x": 1}
    p.write_text(p.read_text().replace('"x": 1', '"x": 2'), encoding="utf-8")
    with pytest.raises(ProvenanceError, match="hash mismatch"):
        read_artifact(p)


def test_artifact_requires_provenance(tmp_path: Path) -> None:
    with pytest.raises(ProvenanceError):
        write_artifact(
            tmp_path / "a.json", ResultArtifact("metric_table", "x", {}, _prov(commit="abc"))
        )
    with pytest.raises(ProvenanceError):
        write_artifact(tmp_path / "b.json", ResultArtifact("nonsense", "x", {}, _prov()))


def test_synthetic_artifact_refused_in_results_tree(tmp_path: Path) -> None:
    (tmp_path / "results").mkdir()
    with pytest.raises(ProvenanceError, match="synthetic"):
        write_artifact(
            tmp_path / "results" / "a.json",
            ResultArtifact("metric_table", "x", {}, _prov(synthetic=True)),
            repo_root=tmp_path,
        )


def test_artifact_never_overwrites(tmp_path: Path) -> None:
    art = ResultArtifact("report", "x", {}, _prov())
    write_artifact(tmp_path / "a.json", art)
    with pytest.raises(FileExistsError):
        write_artifact(tmp_path / "a.json", art)


def test_repo_check_flags_prohibited_files(tmp_path: Path) -> None:
    names = [
        "data/case.nii.gz",
        "x/model.pth",
        "kaggle.json",
        ".env",
        ".env.local",
        "meta/BraTS2021_MappingToTCIA.xlsx",
        "meta/UCSF-PDGM-metadata_v5.csv",
        "docs/FINAL_RESEARCH_PROTOCOL_v2.md",
        "ok/.env.example",
        "ok/readme.md",
    ]
    for n in names:
        (tmp_path / n).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / n).write_text("placeholder\n", encoding="utf-8")
    token = "gh" + "p_" + "A" * 36  # assembled at runtime; never stored in the repository
    (tmp_path / "ok/config.yaml").write_text(f"token: {token}\n", encoding="utf-8")
    found = {f.path for f in check_paths([*names, "ok/config.yaml"], tmp_path)}
    assert found == set(names[:8]) | {"ok/config.yaml"}


def test_repository_itself_is_clean(repo_root: Path) -> None:
    assert main(["--repo-root", str(repo_root), "check-repo"]) == 0


def test_cli_verify_status_and_blocked_action(
    repo_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--repo-root", str(repo_root), "verify-protocol"]) == 0
    assert main(["--repo-root", str(repo_root), "status"]) == 0
    out = capsys.readouterr().out
    assert "Protocol v1.0 frozen. Experimental execution pending." in out
    assert main(["--repo-root", str(repo_root), "check-action", "create_split"]) == 2
    rc = main(
        [
            "--repo-root",
            str(repo_root),
            "build-manifest",
            "--dataset-config",
            "x",
            "--data-root",
            "y",
            "--acquisition-record",
            "w",
            "--out",
            "z",
        ]
    )
    assert rc == 3
    assert "ResearchGateError" in capsys.readouterr().err


def test_plots_watermark_synthetic(tmp_path: Path) -> None:
    pytest.importorskip("matplotlib")
    from brats_uncertainty.metrics.selective import risk_coverage_curve
    from brats_uncertainty.visualization.plots import (
        SYNTHETIC_WATERMARK,
        plot_delta_aurc_forest,
        plot_risk_coverage,
    )

    c = risk_coverage_curve([0.9, 0.5, 0.1], [0.0, 0.5, 1.0])
    p = plot_risk_coverage({"U1": c}, tmp_path / "rc.png", synthetic=True)
    assert p.stat().st_size > 0
    assert SYNTHETIC_WATERMARK.encode() in p.read_bytes()
    q = plot_delta_aurc_forest({"-T1c": (-0.01, -0.02, 0.0)}, tmp_path / "f.png", synthetic=True)
    assert q.exists()
