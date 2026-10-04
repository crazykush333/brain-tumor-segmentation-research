"""The website's committed data must equal a fresh export from the sources of truth."""

from __future__ import annotations

import json
from pathlib import Path

from brats_uncertainty.results.site_export import NO_RESULTS_STATEMENT, export_site_data


def test_website_data_in_sync(repo_root: Path) -> None:
    assert export_site_data(repo_root, check=True) == [], (
        "website/data is stale; run `brats-uncertainty export-site-data`"
    )


def test_website_reports_no_results(repo_root: Path) -> None:
    results = json.loads((repo_root / "website/data/results.json").read_text(encoding="utf-8"))
    assert results["available"] is False
    assert results["artifacts"] == []
    assert results["statement"] == NO_RESULTS_STATEMENT
    status = json.loads((repo_root / "website/data/status.json").read_text(encoding="utf-8"))
    assert status["headline"] == "Protocol v1.0 frozen. Experimental execution pending."


def test_website_source_has_no_hardcoded_numbers_claiming_results(repo_root: Path) -> None:
    """Heuristic guard: website pages must not contain result-like claims."""
    forbidden = ("p < 0.05", "p<0.05", "Dice of 0.", "AURC of 0.", "significantly")
    for f in (repo_root / "website").rglob("*.tsx"):
        if "node_modules" in f.parts or ".next" in f.parts:
            continue
        text = f.read_text(encoding="utf-8")
        for s in forbidden:
            assert s not in text, f"{f}: contains {s!r}"
