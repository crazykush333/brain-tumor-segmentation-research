"""Apply a gate transition to docs/project_status.yaml (owner action; dry run by default).

Steps (all fail closed):

1. validate the CURRENT status file (``status.validate_status``);
2. compute the change with ``lifecycle.apply_transition`` (transition table,
   prerequisites, required evidence, automatic unlocking of eligible gates);
3. re-validate the complete resulting status, including evidence content
   (B1 decision document; committed, REAL_RESEARCH_DATA B2-B6 records linked
   to earlier gates);
4. without ``apply=True``: return the change list only (dry run);
5. with ``apply=True``: edit only the affected lines (comments and layout are
   preserved), re-parse the edited text, require it to equal the validated
   mapping exactly (so no unrelated field can change), then write atomically.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import yaml

from brats_uncertainty.errors import ConfigError
from brats_uncertainty.evaluation.lifecycle import apply_transition
from brats_uncertainty.evaluation.status import STATUS_RELPATH, validate_status
from brats_uncertainty.utils.io import read_yaml

_DATA_KEYS = ("authorization", "approved_route", "acquired")


def _yaml_scalar(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str) and re.fullmatch(r"[A-Z_]+", v):
        return v
    return json.dumps(v)


def plan_transition(
    repo_root: Path,
    gid: str,
    new_status: str,
    *,
    evidence: str | None = None,
    on: str | None = None,
    approved_route: str | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Return the validated new status mapping and a human-readable change list."""
    raw = read_yaml(repo_root / STATUS_RELPATH)
    validate_status(raw, repo_root)  # never transition from an inconsistent state
    new = apply_transition(
        raw, gid, new_status, evidence=evidence, on=on, approved_route=approved_route
    )
    validate_status(new, repo_root)
    changes: list[str] = []
    old_g = {g["id"]: g for g in raw["gates"]}
    for g in new["gates"]:
        o = old_g[g["id"]]
        for k in ("status", "evidence", "closed_on"):
            if o.get(k) != g.get(k):
                changes.append(f"{g['id']}.{k}: {o.get(k)} -> {g.get(k)}")
    for k in _DATA_KEYS:
        if raw["data"].get(k) != new["data"].get(k):
            changes.append(f"data.{k}: {raw['data'].get(k)} -> {new['data'].get(k)}")
    return new, changes


def write_transition(
    repo_root: Path,
    gid: str,
    new_status: str,
    *,
    evidence: str | None = None,
    on: str | None = None,
    approved_route: str | None = None,
    apply: bool = False,
) -> list[str]:
    new, changes = plan_transition(
        repo_root, gid, new_status, evidence=evidence, on=on, approved_route=approved_route
    )
    if not apply:
        return changes
    path = repo_root / STATUS_RELPATH
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    changed_ids = {c.split(".", 1)[0] for c in changes if not c.startswith("data.")}
    gates = {g["id"]: g for g in new["gates"] if g["id"] in changed_ids}  # edit changed lines only
    in_data = False
    for i, line in enumerate(lines):
        m = re.match(r"^(\s*- \{id: )([A-D]\d{0,2})(,.*)$", line.rstrip("\r\n"))
        if m and m.group(2) in gates:
            g = gates[m.group(2)]
            body = m.group(3)
            body = re.sub(r"status: [A-Z_]+", f"status: {g['status']}", body)
            body = re.sub(r"evidence: [^,}]+", f"evidence: {_yaml_scalar(g.get('evidence'))}", body)
            body = re.sub(
                r"closed_on: [^,}]+", f"closed_on: {_yaml_scalar(g.get('closed_on'))}", body
            )
            lines[i] = f"{m.group(1)}{m.group(2)}{body}\n"
            continue
        if re.match(r"^data:\s*$", line):
            in_data = True
            continue
        if in_data and re.match(r"^\S", line):
            in_data = False
        if in_data:
            for k in _DATA_KEYS:
                km = re.match(rf"^(  {k}: )([^#\n]*?)(\s*#.*)?$", line.rstrip("\r\n"))
                if km:
                    lines[i] = f"{km.group(1)}{_yaml_scalar(new['data'][k])}{km.group(3) or ''}\n"
    text = "".join(lines)
    reparsed = yaml.safe_load(text)
    if reparsed != new:
        raise ConfigError(
            "status file edit did not reproduce exactly the validated transition; not written"
        )
    validate_status(reparsed, repo_root)
    tmp = path.with_name(path.name + ".part")
    try:
        tmp.write_text(text, encoding="utf-8", newline="\n")
        os.replace(tmp, path)  # atomic: the old file stays intact until this succeeds
    finally:
        if tmp.exists():
            tmp.unlink()  # never leave a partial file behind
    return changes
