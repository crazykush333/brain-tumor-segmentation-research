"""Gates C1-C3: BraTS-Africa file-level verification, without any model output (§5, §7, §8).

- C1: every eligible case's label file holds only the expected values {0, 1, 2, 3}
  (1 = NETC, 2 = SNFH, 3 = ET); sub-region presence per case is recorded.
- C2: the four sequences (T1, T1c, T2, FLAIR) exist and share the label's shape.
- C3: eligible = cases of the "95 Glioma" sheet with four sequences and a label; the
  count (<= 95) is frozen. SR3: fewer than 30 eligible -> analyses descriptive only.
- §7 safeguard: identical-image-hash check against the BraTS 2021 B5 manifest.

Preconditions (fail closed): an owner-approved data route for BraTS-Africa (the B1
route covers the BraTS 2021 package only; SR7) and the case-ID column of the
"95 Glioma" sheet confirmed on the file. The naming layout in
configs/dataset/brats_africa.yaml is expected, not verified; a mismatch stops C1.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from brats_uncertainty.errors import ConfigError, DataValidationError
from brats_uncertainty.preprocessing.modalities import MODALITIES
from brats_uncertainty.utils.hashing import sha256_file

SR3_MIN = 30
SUBREGIONS = {"NETC": 1, "SNFH": 2, "ET": 3}


def require_route(cfg: Mapping[str, Any]) -> str:
    route = cfg["source"].get("route")
    if not route:
        raise ConfigError(
            "no approved data route for BraTS-Africa (configs/dataset/brats_africa.yaml "
            "source.route is null; B1 covers the BraTS 2021 package only; SR7)"
        )
    return str(route)


def case_files(root: Path, case_id: str, cfg: Mapping[str, Any]) -> dict[str, Path]:
    lay = cfg["layout"]
    base = root / case_id
    files = {
        m: base / f"{case_id}{lay['modality_suffixes'][m]}{lay['file_ending']}" for m in MODALITIES
    }
    files["label"] = base / f"{case_id}{lay['label_suffix']}{lay['file_ending']}"
    return files


def discover_cases(root: Path, cfg: Mapping[str, Any]) -> list[str]:
    pat = re.compile(f"^{cfg['layout']['case_id_pattern']}$")
    found = sorted(p.name for p in root.iterdir() if p.is_dir() and pat.match(p.name))
    if not found:
        raise DataValidationError(
            f"no case folders matching {cfg['layout']['case_id_pattern']!r}: the expected "
            "layout does not match the files (confirm it at C1)"
        )
    return found


def verify_africa(
    root: Path,
    glioma_ids: Sequence[str],
    cfg: Mapping[str, Any],
    *,
    load_label: Callable[[Path], NDArray[np.integer]],
    image_shape: Callable[[Path], tuple[int, ...]],
    brats2021_image_sha256: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    expected = set(int(v) for v in cfg["labels"]["expected_values"])
    present = set(discover_cases(root, cfg))
    c1: dict[str, Any] = {}
    c2: dict[str, Any] = {}
    eligible: list[str] = []
    problems: list[str] = []
    overlaps: list[str] = []
    for cid in sorted(glioma_ids):
        if cid not in present:
            c2[cid] = {"complete": False, "reason": "case folder missing"}
            continue
        files = case_files(root, cid, cfg)
        missing = [k for k, p in files.items() if not p.is_file()]
        if "label" in missing:
            c1[cid] = {"label": False}
        else:
            lab = load_label(files["label"])
            values = set(np.unique(lab).tolist())
            unexpected = sorted(values - expected)
            if unexpected:
                problems.append(f"{cid}: unexpected label values {unexpected}")
            c1[cid] = {
                "label": True,
                "values": sorted(values),
                "subregions_present": {k: v in values for k, v in SUBREGIONS.items()},
            }
        shapes = {k: image_shape(p) for k, p in files.items() if k not in missing}
        same = len(set(shapes.values())) <= 1
        complete = not missing and same
        c2[cid] = {"complete": complete, "missing": missing, "shapes_equal": same}
        for m in MODALITIES:
            if m not in missing and sha256_file(files[m]) in brats2021_image_sha256:
                overlaps.append(cid)
                break
        if complete and c1[cid].get("label"):
            eligible.append(cid)
    if problems:
        raise DataValidationError("C1 label verification failed: " + "; ".join(problems[:5]))
    max_n = int(cfg["inclusion"]["max_eligible"])
    if len(eligible) > max_n:
        raise DataValidationError(
            f"C3: {len(eligible)} eligible cases exceed the protocol maximum {max_n}"
        )
    return {
        "C1_labels": c1,
        "C2_sequences": c2,
        "C3_eligible": eligible,
        "C3_eligible_count": len(eligible),
        "descriptive_only_SR3": len(eligible) < SR3_MIN,
        "identical_image_hash_overlap_with_brats2021": sorted(set(overlaps)),
        "n_glioma_listed": len(glioma_ids),
    }
