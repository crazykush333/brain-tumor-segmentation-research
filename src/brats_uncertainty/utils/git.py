"""Git helpers used to stamp every artifact with the exact code commit."""

from __future__ import annotations

import subprocess
from pathlib import Path


def _git(args: list[str], cwd: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, check=True, timeout=30
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip()


def git_commit(repo_root: str | Path) -> str | None:
    """Full SHA of HEAD, or None if not a git checkout."""
    return _git(["rev-parse", "HEAD"], Path(repo_root))


def git_is_dirty(repo_root: str | Path) -> bool | None:
    """True if tracked files have uncommitted changes; None if unknown."""
    out = _git(["status", "--porcelain", "--untracked-files=no"], Path(repo_root))
    if out is None:
        return None
    return bool(out)


def git_tag_commit(repo_root: str | Path, tag: str) -> str | None:
    """Commit SHA a tag points to, or None if the tag does not exist."""
    return _git(["rev-parse", f"{tag}^{{commit}}"], Path(repo_root))


def git_tracked_files(repo_root: str | Path) -> list[str]:
    """Tracked files plus untracked-but-not-ignored files (relative paths)."""
    root = Path(repo_root)
    tracked = _git(["ls-files"], root) or ""
    untracked = _git(["ls-files", "--others", "--exclude-standard"], root) or ""
    files = {f for f in (tracked + "\n" + untracked).splitlines() if f.strip()}
    return sorted(files)


def is_git_repo(repo_root: str | Path) -> bool:
    return _git(["rev-parse", "--is-inside-work-tree"], Path(repo_root)) == "true"


def git_is_tracked(repo_root: str | Path, relpath: str) -> bool:
    """True if ``relpath`` is in the git index (committed or staged)."""
    return _git(["ls-files", "--error-unmatch", "--", relpath], Path(repo_root)) is not None


def git_is_ignored(repo_root: str | Path, relpath: str) -> bool:
    return _git(["check-ignore", "-q", "--no-index", "--", relpath], Path(repo_root)) is not None


def git_commit_exists(repo_root: str | Path, commit: str) -> bool:
    return _git(["cat-file", "-e", f"{commit}^{{commit}}"], Path(repo_root)) is not None


class GitView:
    """Batched, cached git queries for one validation pass (few subprocess calls)."""

    def __init__(self, repo_root: str | Path) -> None:
        self.root = Path(repo_root)
        self.is_repo = is_git_repo(self.root)
        self._tracked: set[str] | None = None
        self._commits: dict[str, bool] = {}

    def tracked(self) -> set[str]:
        if self._tracked is None:
            out = _git(["ls-files", "-z"], self.root) or ""
            self._tracked = {p for p in out.split("\0") if p}
        return self._tracked

    def ignored(self, relpaths: list[str]) -> set[str]:
        if not relpaths:
            return set()
        try:
            # NUL-separated binary I/O. Text mode turns "\n" into "\r\n" on Windows, so git
            # would test (and quote) a different path and the check would never match.
            proc = subprocess.run(
                ["git", "check-ignore", "--no-index", "-z", "--stdin"],
                cwd=self.root,
                input=b"\0".join(r.encode("utf-8") for r in relpaths) + b"\0",
                capture_output=True,
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired):
            return set(relpaths)  # fail closed: treat as ignored
        if proc.returncode not in (0, 1):
            return set(relpaths)  # fail closed
        return {p.decode("utf-8") for p in proc.stdout.split(b"\0") if p}

    def is_ancestor(self, commit: str) -> bool:
        """True if ``commit`` is HEAD or one of its ancestors (not from another history)."""
        if not self.is_repo:
            return True
        try:
            proc = subprocess.run(
                ["git", "merge-base", "--is-ancestor", commit, "HEAD"],
                cwd=self.root,
                capture_output=True,
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False  # fail closed
        return proc.returncode == 0

    def commit_exists(self, commit: str) -> bool:
        if commit not in self._commits:
            self._commits[commit] = git_commit_exists(self.root, commit)
        return self._commits[commit]
