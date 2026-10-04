"""Validated updates of the stage fields of docs/project_status.yaml.

Fields: ``training.status``, ``evaluation.internal``, ``evaluation.external``,
``results.{status, available, evidence, statement}`` and ``experiments.<ID>.status``.
Every change is re-validated with ``status.validate_status`` (e.g. training cannot
start before B12; results.available needs evidence); only the affected lines are
edited, the re-parsed file must equal the validated mapping, and the write is atomic.
"""

from __future__ import annotations

import copy
import json
import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from brats_uncertainty.errors import ConfigError
from brats_uncertainty.evaluation.status import STATUS_RELPATH, validate_status
from brats_uncertainty.utils.io import read_yaml

ALLOWED = {
    ("training", "status"),
    ("evaluation", "internal"),
    ("evaluation", "external"),
    ("results", "status"),
    ("results", "available"),
    ("results", "evidence"),
    ("results", "statement"),
}


def _scalar(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str) and re.fullmatch(r"[A-Z_]+", v):
        return v
    return json.dumps(v)


def set_stage_fields(
    repo_root: Path,
    updates: Mapping[tuple[str, str], Any],
    experiments: Mapping[str, str] | None = None,
) -> list[str]:
    path = repo_root / STATUS_RELPATH
    raw = read_yaml(path)
    validate_status(raw, repo_root)
    new = copy.deepcopy(raw)
    changes: list[str] = []
    for (section, key), value in updates.items():
        if (section, key) not in ALLOWED:
            raise ConfigError(f"{section}.{key} cannot be set here")
        if new[section].get(key) != value:
            changes.append(f"{section}.{key}: {new[section].get(key)!r} -> {value!r}")
            new[section][key] = value
    for exp_id, st in (experiments or {}).items():
        if new["experiments"][exp_id]["status"] != st:
            changes.append(
                f"experiments.{exp_id}.status: {new['experiments'][exp_id]['status']} -> {st}"
            )
            new["experiments"][exp_id]["status"] = st
    if not changes:
        return []
    validate_status(new, repo_root)
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    current: str | None = None
    for i, line in enumerate(lines):
        top = re.match(r"^([a-z_]+):\s*(#.*)?$", line.rstrip("\r\n"))
        if top:
            current = top.group(1)
            continue
        if re.match(r"^\S", line):
            current = None
            continue
        m = re.match(r"^(  )([a-z_]+)(: )(.*?)(\s*#.*)?$", line.rstrip("\r\n"))
        if m and current and (current, m.group(2)) in {k for k in updates}:
            lines[i] = (
                f"{m.group(1)}{m.group(2)}{m.group(3)}"
                f"{_scalar(new[current][m.group(2)])}{m.group(5) or ''}\n"
            )
        if current == "experiments" and experiments:
            em = re.match(r"^(  )([A-Z0-9-]+)(: \{status: )([A-Z_]+)(,.*)$", line.rstrip("\r\n"))
            if em and em.group(2) in experiments:
                lines[i] = (
                    f"{em.group(1)}{em.group(2)}{em.group(3)}{experiments[em.group(2)]}{em.group(5)}\n"
                )
    text = "".join(lines)
    if yaml.safe_load(text) != new:
        raise ConfigError("status edit did not reproduce exactly the validated change; not written")
    tmp = path.with_name(path.name + ".part")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)
    return changes
