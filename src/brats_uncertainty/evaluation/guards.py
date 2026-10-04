"""Research-gate safeguards. Every guarded action fails loudly unless its gates allow it.

Gate requirements follow the protocol lifecycle (gates B1-B12, C1-C6, D1-D6).
An action needs (a) every prerequisite gate closed (CLOSED/PASSED) and, for the
B-gate actions, (b) its own gate AUTHORIZED or RUNNING in the lifecycle state
machine. Nothing is inferred from files, URLs or documentation existing.
Test-set and external evaluations additionally require running from the exact
commit tagged ``eval-v1`` with a clean working tree (gate C6, SR4).
"""

from __future__ import annotations

from pathlib import Path

from brats_uncertainty.errors import ResearchGateError
from brats_uncertainty.evaluation.status import load_status
from brats_uncertainty.utils.git import git_commit, git_is_dirty, git_tag_commit
from brats_uncertainty.utils.paths import find_repo_root

EVAL_TAG = "eval-v1"


def _b(n: int) -> list[str]:
    return [f"B{i}" for i in range(1, n + 1)]


_D_ALL = [f"D{i}" for i in range(1, 7)]

ACTION_REQUIREMENTS: dict[str, list[str]] = {
    "acquire_data": ["B1"],  # B2: real-data acquisition via the approved route
    "record_crosswalk_hash": _b(2),  # B3
    "record_ucsf_metadata_hash": _b(2),  # B4 (available after B2, like B3)
    "build_manifest": _b(4),  # B5
    "validate_data": _b(2),  # integrity checks on acquired files (supports B5)
    "derive_counts": _b(5),  # B6
    "compute_t_screen": _b(6),
    "pairwise_screen": _b(6),
    "freeze_patient_groups": _b(8),
    "create_split": _b(9),
    "hoi_grouping": _b(9),  # C4: same frozen §6.2 screen/review within the HOI set
    "run_exp001": ["B1", "B2", "D1", "D2"],
    "train_main": [*_b(12), *_D_ALL],
    "infer_validation": [*_b(12), *_D_ALL],
    "freeze_thresholds": [*_b(12), *_D_ALL],
    "evaluate_internal_test": [*_b(12), *_D_ALL, "C5", "C6"],
    "evaluate_upenn_hoi": [*_b(12), *_D_ALL, "C4", "C5", "C6"],
    "evaluate_brats_africa": [*_b(12), *_D_ALL, "C1", "C2", "C3", "C5", "C6"],
}

_RUNNABLE = frozenset({"AUTHORIZED", "RUNNING"})
# action -> (own gate, statuses of that gate in which the action may run)
OWN_GATE: dict[str, tuple[str, frozenset[str]]] = {
    "acquire_data": ("B2", _RUNNABLE),
    "record_crosswalk_hash": ("B3", _RUNNABLE),
    "record_ucsf_metadata_hash": ("B4", _RUNNABLE),
    "validate_data": ("B2", _RUNNABLE | {"PASSED"}),
    "build_manifest": ("B5", _RUNNABLE),
    "derive_counts": ("B6", _RUNNABLE),
    "compute_t_screen": ("B7", _RUNNABLE),
    "pairwise_screen": ("B7", _RUNNABLE),
    "freeze_patient_groups": ("B9", _RUNNABLE),
    "create_split": ("B10", _RUNNABLE),
}

ACQUISITION_LOCKED_MESSAGE = (
    "Real-data acquisition is locked because B1 data-route authorization has not been recorded."
)

TAGGED_ACTIONS = frozenset(
    {"evaluate_internal_test", "evaluate_upenn_hoi", "evaluate_brats_africa"}
)


def check_action(
    action: str, repo_root: str | Path | None = None, *, status_root: str | Path | None = None
) -> list[str]:
    """Return the list of unmet requirements (empty if the action is permitted).

    ``status_root``: read the gate records from this checkout (the live main checkout)
    while the code checks (eval-v1 tag, clean tree) apply to ``repo_root`` (the tagged
    worktree that runs the evaluation). Defaults to ``repo_root``.
    """
    if action not in ACTION_REQUIREMENTS:
        raise ResearchGateError(f"unknown guarded action {action!r}")
    root = Path(repo_root) if repo_root is not None else find_repo_root()
    status = load_status(Path(status_root) if status_root is not None else root)
    unmet = [
        f"{g} ({status.gate(g).status})"
        for g in ACTION_REQUIREMENTS[action]
        if not status.gate(g).is_closed
    ]
    if action in OWN_GATE:
        gid, allowed = OWN_GATE[action]
        own = status.gate(gid).status
        if own not in allowed:
            unmet.append(f"{gid} is {own} (must be {' or '.join(sorted(allowed))})")
    if action == "acquire_data" and status.raw["data"].get("authorization") != "APPROVED":
        unmet.append("data.authorization is not APPROVED")
    if action in TAGGED_ACTIONS:
        tag = git_tag_commit(root, EVAL_TAG)
        if tag is None:
            unmet.append(f"git tag {EVAL_TAG} does not exist")
        elif git_commit(root) != tag:
            unmet.append(f"HEAD is not the {EVAL_TAG} commit")
        if git_is_dirty(root) is not False:
            unmet.append("working tree is not clean")
    return unmet


def require_action(
    action: str, repo_root: str | Path | None = None, *, status_root: str | Path | None = None
) -> None:
    """Raise ResearchGateError unless every protocol gate for ``action`` is closed."""
    unmet = check_action(action, repo_root, status_root=status_root)
    if unmet:
        prefix = f"{ACQUISITION_LOCKED_MESSAGE} " if action == "acquire_data" else ""
        raise ResearchGateError(
            f"{prefix}action {action!r} is not authorized by the frozen protocol lifecycle. "
            f"Unmet requirements: {', '.join(unmet)}. "
            "Close the gates legitimately (with evidence in docs/project_status.yaml) first."
        )
