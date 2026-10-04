"""Run summary (``docs/research/execution/run_summary.json``) and the final research audit.

Both are generated only from recorded state: docs/project_status.yaml, the master
state journal and committed records. No value is typed by hand, and nothing is
reported as a result unless a result artifact exists.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from brats_uncertainty.evaluation.status import load_status
from brats_uncertainty.orchestration.state import MasterState
from brats_uncertainty.utils.git import git_commit, git_is_dirty
from brats_uncertainty.utils.io import read_json, write_json


def _maybe(path: Path) -> Any:
    return read_json(path) if path.is_file() else None


def build_run_summary(repo_root: Path, state: MasterState, cfg: dict[str, Any]) -> dict[str, Any]:
    st = load_status(repo_root)
    records = repo_root / cfg["paths"]["records_dir"]
    splits = repo_root / cfg["paths"]["splits_dir"]
    b5 = _maybe(records / "B5_manifest.json")
    return {
        "schema_version": 1,
        "generated_from": "master runner state + docs/project_status.yaml (no hand-typed values)",
        "git_commit": git_commit(repo_root),
        "git_dirty": git_is_dirty(repo_root),
        "protocol": {
            "version": st.raw["protocol"]["version"],
            "sha256": st.raw["protocol"]["sha256"],
            "tag": st.raw["protocol"]["git_tag"],
        },
        "gates": {gid: g.status for gid, g in st.gates.items() if gid[0] in "BCD"},
        "steps": {
            sid: {"status": r.status, "summary": r.summary, "attempts": r.attempts}
            for sid, r in state.steps.items()
        },
        "sessions": len(state.sessions),
        "resumes": sum(1 for s in state.sessions if s.get("resumed")),
        "dataset": {
            "acquired": bool(st.raw["data"]["acquired"]),
            "manifest_sha256": b5.get("manifest_sha256") if b5 else None,
        },
        "split_hashes": _maybe(splits / "split_hashes.json"),
        "results_available": bool(st.raw["results"]["available"]),
        "results": st.raw["results"].get("evidence"),
    }


def write_run_summary(repo_root: Path, state: MasterState, cfg: dict[str, Any]) -> Path:
    path = repo_root / cfg["paths"]["run_summary"]
    write_json(path, build_run_summary(repo_root, state, cfg), overwrite=True)
    return path


def write_final_audit(ctx: Any) -> Path:
    """FINAL_RESEARCH_AUDIT.md: only reached after every scientific step has PASSED."""
    from brats_uncertainty.orchestration.state import load_state

    state = load_state(ctx.state_dir)
    summary = build_run_summary(ctx.repo_root, state, ctx.cfg)
    lines = [
        "# Final research audit",
        "",
        f"- Final commit: `{summary['git_commit']}` (dirty: {summary['git_dirty']})",
        f"- Protocol {summary['protocol']['version']} sha256 `{summary['protocol']['sha256']}` "
        f"(tag `{summary['protocol']['tag']}`)",
        f"- Dataset manifest sha256: `{summary['dataset']['manifest_sha256']}`",
        f"- Split hashes: `{summary['split_hashes']}`",
        f"- Sessions: {summary['sessions']} (resumes: {summary['resumes']})",
        "",
        "## Gates",
        "",
        *(f"- {g}: {s}" for g, s in summary["gates"].items()),
        "",
        "## Steps",
        "",
        *(
            f"- {sid}: {r['status']} ({r['attempts']} attempt(s)) - {r['summary']}"
            for sid, r in summary["steps"].items()
        ),
        "",
        "## Results",
        "",
        f"Result evidence: `{summary['results']}`"
        if summary["results_available"]
        else "No result artifacts are recorded.",
        "",
    ]
    path = ctx.repo_root / ctx.cfg["paths"]["final_audit"]
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return path
