"""``brats-uncertainty master-run``: build the context, run one session, wrap it up."""

from __future__ import annotations

import os
import platform
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from brats_uncertainty.errors import ConfigError
from brats_uncertainty.orchestration.audit import write_final_audit_for, write_run_summary
from brats_uncertainty.orchestration.runner import RunReport, plan, run
from brats_uncertainty.orchestration.state import STATE_FILENAME, load_state, save_state
from brats_uncertainty.orchestration.steps import Context, RealOps, build_steps, load_master_config
from brats_uncertainty.utils.git import git_commit, git_is_dirty
from brats_uncertainty.utils.paths import is_within


def resolve_dirs(
    repo_root: Path,
    cfg: Mapping[str, Any],
    environ: Mapping[str, str],
    work_dir: str | None,
    state_dir: str | None,
) -> tuple[Path, Path]:
    work = work_dir or environ.get(cfg["paths"]["work_env"], "")
    if not work:
        raise ConfigError(
            f"no persistent work directory: pass --work-dir or set {cfg['paths']['work_env']} "
            "to private persistent storage outside the repository"
        )
    w = Path(work).expanduser().resolve()
    if is_within(w, repo_root):
        raise ConfigError("the work directory (raw data, runs) must be outside the repository")
    s = Path(state_dir or environ.get(cfg["paths"]["state_env"], "") or (w / "state")).resolve()
    return w, s


def master_run(
    repo_root: Path,
    *,
    work_dir: str | None = None,
    state_dir: str | None = None,
    resume: bool = False,
    commit: bool = False,
    push: bool = False,
    offline: bool = False,
    retry: Sequence[str] = (),
    approve_restart: Sequence[str] = (),
    until: str | None = None,
    plan_only: bool = False,
    environ: Mapping[str, str] | None = None,
) -> tuple[RunReport, Context]:
    env = dict(os.environ if environ is None else environ)
    cfg = load_master_config(repo_root)
    work, state_path = resolve_dirs(repo_root, cfg, env, work_dir, state_dir)
    if push and not commit:
        raise ConfigError("--push requires --commit")
    ops = RealOps(
        repo_root, cfg, commit=commit, push=push, environ=env, work_dir=work, offline=offline
    )
    ctx = Context(
        repo_root=repo_root,
        work_dir=work,
        state_dir=state_path,
        cfg=cfg,
        environ=env,
        ops=ops,
        offline=offline,
        approvals=frozenset(f"restart:{j}" for j in approve_restart),
    )
    steps = build_steps()
    state = load_state(state_path)
    if plan_only:
        return RunReport(statuses=plan(ctx, steps, state), planned=True), ctx
    if state.sessions and not resume:
        raise ConfigError(
            f"a master state exists at {state_path / STATE_FILENAME}; pass --resume to continue "
            "from it (completed work is never restarted)"
        )
    work.mkdir(parents=True, exist_ok=True)
    report = run(
        ctx,
        steps,
        retry=retry,
        until=until,
        session_info={
            "git_commit": git_commit(repo_root),
            "git_dirty": git_is_dirty(repo_root),
            "host": platform.node(),
            "platform": platform.platform(),
            "commit": commit,
            "push": push,
        },
    )
    write_run_summary(repo_root, load_state(state_path), cfg)
    write_final_audit_for(repo_root, load_state(state_path), cfg)
    sha = ops.milestone("chore(run): master-run session summary and website data")
    report.commits = list(ops.commits) if sha or ops.commits else []
    state = load_state(state_path)
    state.event("session_wrapup", commits=report.commits)
    save_state(state_path, state)
    return report, ctx
