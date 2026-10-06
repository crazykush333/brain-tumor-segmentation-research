"""Synthetic demonstration safety: flags, namespace isolation, determinism, no data access,
no gate closure, no export as results, website states (real results pending + demo)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from brats_uncertainty.demo import (
    DEMO_FLAGS,
    DEMO_LABEL,
    FILES,
    check_out_dir,
    generate_demo,
    is_demo_artifact,
)
from brats_uncertainty.errors import ConfigError, ProvenanceError
from tests.conftest import REPO_ROOT

FIXED = {"git_commit": "0" * 40, "generated_at": "2026-10-05T00:00:00+00:00", "n_replicates": 60}


@pytest.fixture(scope="module")
def demo_pair(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    a, b = tmp_path_factory.mktemp("demo_a"), tmp_path_factory.mktemp("demo_b")
    generate_demo(a, repo_root=REPO_ROOT, **FIXED)
    generate_demo(b, repo_root=REPO_ROOT, **FIXED)
    return a, b


def test_every_artifact_is_flagged(demo_pair: tuple[Path, Path]) -> None:
    a, _ = demo_pair
    assert sorted(p.name for p in a.iterdir()) == sorted(FILES)
    summary = json.loads((a / "synthetic_summary.json").read_text(encoding="utf-8"))
    assert all(summary[k] == v for k, v in DEMO_FLAGS.items())
    assert summary["demo_seed"] == 20261004 and summary["git_commit"] == "0" * 40
    assert summary["code_sha256"] and "sha256" not in json.dumps(summary["synthetic_study"])
    for name in FILES:
        assert is_demo_artifact(a / name), name
    for svg in a.glob("*.svg"):
        assert "demo=true synthetic=true scientific_result=false" in svg.read_text(encoding="utf-8")
    rows = (a / "synthetic_metrics.csv").read_text(encoding="utf-8").splitlines()
    assert rows[0].endswith("demo,synthetic,scientific_result,disclaimer")
    assert all(r.split(",")[-4:-1] == ["true", "true", "false"] for r in rows[1:])
    assert not any("BraTS2021_" in r for r in rows)  # SYNTH_* cases only
    report = (a / "synthetic_results_report.md").read_text(encoding="utf-8")
    assert DEMO_LABEL in report and "## Real study status" in report


def test_demo_is_deterministic(demo_pair: tuple[Path, Path]) -> None:
    a, b = demo_pair
    for name in FILES:
        assert (a / name).read_bytes() == (b / name).read_bytes(), name


def test_demo_refuses_real_result_namespaces(tmp_path: Path) -> None:
    for rel in (
        "results",
        "results/internal",
        "results/external",
        "results/final",
        "results/MAIN",
        "results/public-safe",
        "docs/data/records",
        "splits",
    ):
        with pytest.raises(ProvenanceError, match="results/demo"):
            check_out_dir(REPO_ROOT / rel, REPO_ROOT)
    check_out_dir(REPO_ROOT / "results/demo", REPO_ROOT)  # the only in-repo location
    check_out_dir(tmp_path, REPO_ROOT)  # outside the repository: allowed


def test_demo_never_touches_real_data_locations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sentinel = tmp_path / "private"
    sentinel.mkdir()
    for var in (
        "BRATS_WORK",
        "BRATS_OFFICIAL_DELIVERY",
        "BRATS2021_DATA_ROOT",
        "BRATS_AFRICA_DATA_ROOT",
    ):
        monkeypatch.setenv(var, str(sentinel))
    opened: list[str] = []
    real_open = Path.open

    def spy(self: Path, *a: object, **k: object):  # type: ignore[no-untyped-def]
        opened.append(str(self))
        return real_open(self, *a, **k)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "open", spy)
    generate_demo(tmp_path / "out", repo_root=REPO_ROOT, **FIXED)
    assert not any(str(sentinel) in p for p in opened)
    assert list(sentinel.iterdir()) == []
    assert not any(os.sep + "raw" + os.sep in p for p in opened)


def test_demo_cannot_close_gates(
    pre_execution_root: Path, demo_pair: tuple[Path, Path], tmp_path: Path
) -> None:
    repo_root = pre_execution_root  # frozen pre-execution snapshot (tests/conftest.py)
    from brats_uncertainty.evaluation.lifecycle import apply_transition
    from brats_uncertainty.evaluation.status import load_status, validate_status

    raw = load_status(repo_root).raw
    b2 = next(g for g in raw["gates"] if g["id"] == "B2")["status"]
    running = raw if b2 == "RUNNING" else apply_transition(raw, "B2", "RUNNING")
    passed = apply_transition(
        running, "B2", "PASSED", evidence="results/demo/synthetic_summary.json", on="2026-10-05"
    )
    with pytest.raises(ConfigError):
        validate_status(passed, repo_root)  # not a committed, real B2 execution record


def test_demo_cannot_be_exported_or_indexed_as_results(
    demo_pair: tuple[Path, Path], tmp_path: Path
) -> None:
    from brats_uncertainty.results.export import export_public_artifacts
    from brats_uncertainty.results.site_export import _results

    a, _ = demo_pair
    with pytest.raises(ProvenanceError, match="synthetic demonstration"):
        export_public_artifacts(a, tmp_path / "dest")
    assert not (tmp_path / "dest").exists()  # nothing copied
    repo = tmp_path / "repo"
    (repo / "results").mkdir(parents=True)
    (repo / "results/index.json").write_text(
        json.dumps({"artifacts": ["results/demo/synthetic_summary.json"]}), encoding="utf-8"
    )
    (repo / "results/demo").mkdir()
    (repo / "results/demo/synthetic_summary.json").write_bytes(
        (a / "synthetic_summary.json").read_bytes()
    )
    with pytest.raises((ProvenanceError, KeyError)):
        _results(repo, {"results": {"available": True}})


def test_site_states_real_pending_and_demo(
    pre_execution_root: Path, demo_pair: tuple[Path, Path], tmp_path: Path
) -> None:
    repo_root = pre_execution_root  # frozen pre-execution snapshot (tests/conftest.py)
    import shutil

    from brats_uncertainty.results.site_export import build_site_data, results_status

    data = build_site_data(repo_root)
    assert data["results.json"]["available"] is False  # real results: none
    raw = json.loads(json.dumps(data["status.json"]))
    assert raw["data"]["acquired"] is False
    status = results_status(
        repo_root,
        __import__("brats_uncertainty.evaluation.status", fromlist=["x"])
        .load_status(repo_root)
        .raw,
    )
    assert (
        status["scientific_results_available"] is False
        and status["real_experiment_executed"] is False
    )
    assert status["status"] == "pending_official_data_and_compute"
    assert status["synthetic_results_in_scientific_namespace"] is False
    demo = data["demo.json"]
    if demo["available"]:  # the committed demo
        assert demo["demo"] and demo["synthetic"] and demo["scientific_result"] is False
        assert all(f.startswith("synthetic_") and f.endswith(".svg") for f in demo["figures"])
    # a demo directory without the flags is refused for the website
    a, _ = demo_pair
    repo = tmp_path / "r"
    shutil.copytree(a, repo / "results/demo")
    body = json.loads((repo / "results/demo/synthetic_summary.json").read_text(encoding="utf-8"))
    body["scientific_result"] = True
    (repo / "results/demo/synthetic_summary.json").write_text(json.dumps(body), encoding="utf-8")
    from brats_uncertainty.results.site_export import demo_site_data

    with pytest.raises(ProvenanceError, match="demo flags"):
        demo_site_data(repo)


def test_website_results_page_renders_both_states() -> None:
    """The Results page never shows synthetic content; the demo has its own page."""
    page = (REPO_ROOT / "website/app/results/page.tsx").read_text(encoding="utf-8")
    assert "Results pending real experimental execution." in page
    assert "Scientific results are being independently verified." in page
    assert "Verified result ID:" in page and "data-result-id" in page
    assert "demo" not in page.lower() and "synthetic" not in page.lower()
    demo_page = (REPO_ROOT / "website/app/demo/page.tsx").read_text(encoding="utf-8")
    assert "Synthetic Results Demonstration" in demo_page
    assert "NOT SCIENTIFIC RESULT" in demo_page and "View demo artifacts" in demo_page
    nav = (REPO_ROOT / "website/components/Nav.tsx").read_text(encoding="utf-8")
    assert "synthetic" not in nav.lower()  # rendered on the Results page too
