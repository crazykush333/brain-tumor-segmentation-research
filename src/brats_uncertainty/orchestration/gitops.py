"""Milestone commits and pushes for the master runner (fail closed).

- Identity: the repository-local identity from configs/compute/master_run.yaml is set
  if absent and must match exactly; a different local identity stops the runner.
- Only allow-listed paths are staged (never ``git add -A``); anything else staged
  aborts the commit. The repository scan (prohibited files, secrets, protocol
  hash) must pass before every commit.
- Messages never carry attribution trailers.
- Push: fast-forward only (never ``--force``). A token, if needed, is read from an
  environment variable by a one-shot credential helper at push time; it is never
  written to disk, to the command line or to a log.
"""

from __future__ import annotations

import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from brats_uncertainty.errors import ProvenanceError
from brats_uncertainty.repo_checks import check_repository

_FORBIDDEN_MESSAGE_MARKERS = ("co-authored-by", "generated with")


def _git(root: Path, *args: str, check: bool = True, env: Mapping[str, str] | None = None) -> str:
    res = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        env=None if env is None else dict(env),
    )
    if check and res.returncode != 0:
        raise ProvenanceError(f"git {args[0]} failed: {res.stderr.strip() or res.stdout.strip()}")
    return res.stdout.strip()


def ensure_identity(root: Path, identity: Mapping[str, str]) -> None:
    for key, want in (("user.name", identity["name"]), ("user.email", identity["email"])):
        have = _git(root, "config", "--local", "--get", key, check=False)
        if not have:
            _git(root, "config", "--local", key, want)
        elif have != want:
            raise ProvenanceError(
                f"repository-local {key} is {have!r}, expected {want!r}; refusing to commit"
            )


def is_allowed(path: str, allow: Sequence[str]) -> bool:
    p = path.replace("\\", "/")
    return any(p == a or (a.endswith("/") and p.startswith(a)) for a in allow)


def commit_milestone(root: Path, message: str, cfg: Mapping[str, Any]) -> str | None:
    """Stage the allow-listed paths, verify, commit. Returns the new commit or None."""
    if any(m in message.lower() for m in _FORBIDDEN_MESSAGE_MARKERS):
        raise ProvenanceError("commit messages must not carry attribution trailers")
    allow = list(cfg["commit_paths"])
    ensure_identity(root, cfg["identity"])
    findings = check_repository(root)
    if findings:
        raise ProvenanceError(
            "repository scan failed; nothing committed: "
            + "; ".join(f"{f.path}: {f.problem}" for f in findings[:5])
        )
    pre_staged = [p for p in _git(root, "diff", "--cached", "--name-only").splitlines() if p]
    stray = [p for p in pre_staged if not is_allowed(p, allow)]
    if stray:
        raise ProvenanceError(f"paths outside the commit allow-list are staged: {stray[:5]}")
    existing = [a for a in allow if (root / a).exists()]
    if existing:
        _git(root, "add", "--", *existing)
    staged = [p for p in _git(root, "diff", "--cached", "--name-only").splitlines() if p]
    stray = [p for p in staged if not is_allowed(p, allow)]
    if stray:
        _git(root, "reset", "-q", "--", *stray)
        raise ProvenanceError(f"refusing to commit paths outside the allow-list: {stray[:5]}")
    if not staged:
        return None
    _git(root, "commit", "-q", "-m", message)
    return _git(root, "rev-parse", "HEAD")


def push(root: Path, cfg: Mapping[str, Any], environ: Mapping[str, str]) -> str:
    """Fast-forward push of HEAD to the configured branch. Never forces."""
    remote, branch = str(cfg["remote"]), str(cfg["branch"])
    token_env = str(cfg.get("token_env") or "")
    env = dict(environ)
    cred: list[str] = []
    if token_env and environ.get(token_env):
        # helper reads the variable at run time; the value never appears in argv or logs
        helper = f'!f() {{ echo username=x-access-token; echo "password=${{{token_env}}}"; }}; f'
        cred = ["-c", "credential.helper=", "-c", f"credential.helper={helper}"]
    push_args = [*cred, "push", remote, f"HEAD:refs/heads/{branch}"]
    try:
        _git(root, *push_args, env=env)
    except ProvenanceError:
        # the remote moved on while this session ran (e.g. a code fix was pushed): replay
        # the local milestone commits on top of it and push again; never a force-push
        _git(root, *cred, "fetch", remote, branch, env=env)
        try:
            _git(root, "rebase", f"{remote}/{branch}")
        except ProvenanceError:
            _git(root, "rebase", "--abort", check=False)
            raise
        _git(root, *push_args, env=env)
    return _git(root, "rev-parse", "HEAD")
