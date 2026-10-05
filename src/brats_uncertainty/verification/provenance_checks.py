"""Data, split, run and checkpoint verification (Phases 3-6).

The data check re-enumerates the training tree from disk and re-hashes every file with
``hashlib`` (it does not read hashes from the production manifest); the split check
recomputes the label-derived stratification features independently and rebuilds the
assignment; the run check re-hashes checkpoints and cross-checks every manifest.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from brats_uncertainty.verification.model import (
    NOT_APPLICABLE,
    NOT_PERFORMED,
    Check,
    Stage,
    expect,
)

EXPECTED = {"total": 1251, "hoi": 511, "development": 740}
HOI_SITE = "1"
PARTITIONS = ("train", "validation", "internal_test")
EXPECTED_SPLIT_SEED = 20260927


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def enumerate_tree(root: Path) -> dict[str, tuple[int, str]]:
    """Independent inventory: relative path -> (size, SHA-256)."""
    return {
        p.relative_to(root).as_posix(): (p.stat().st_size, _sha256(p))
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def check_data(
    *,
    training_root: Path | None,
    manifest: Mapping[str, Any],
    inventory: Sequence[Any],
    data_root_reference: str,
    metadata_files: Mapping[str, tuple[Path | None, str]],
    crosswalk_case_ids: Sequence[str],
) -> Stage:
    """``metadata_files``: gate -> (local file, SHA-256 recorded at B3/B4)."""
    st = Stage("DATA", "Data verification (independent re-enumeration)")
    if training_root is None or not training_root.is_dir():
        st.add(Check("training tree present", NOT_PERFORMED, detail="training data not available"))
        return st.finish()
    found = enumerate_tree(training_root)
    files = {f["relpath"]: f for f in manifest["files"]}
    st.add(
        expect(
            "file set equals the production manifest",
            set(found) == set(files),
            f"only on disk: {sorted(set(found) - set(files))[:3]}; only in manifest: "
            f"{sorted(set(files) - set(found))[:3]}",
        )
    )
    bad = [
        r
        for r in set(found) & set(files)
        if found[r] != (int(files[r]["size_bytes"]), files[r]["sha256"])
    ]
    st.add(expect("every file hash and size equals the manifest", not bad, f"mismatch: {bad[:3]}"))
    inv = {e.relpath: (e.size_bytes, e.sha256) for e in inventory}
    prefix = data_root_reference.rstrip("/") + "/"
    in_inv = {k[len(prefix) :]: v for k, v in inv.items() if k.startswith(prefix)}
    st.add(
        expect(
            "training tree equals the B2 acquisition inventory",
            in_inv == found,
            f"{len(set(in_inv) ^ set(found))} path differences",
        )
    )
    for gate, (path, recorded) in metadata_files.items():
        if path is None or not path.is_file():
            st.add(Check(f"{gate} metadata file hash", NOT_PERFORMED, detail="file not available"))
        else:
            st.add(expect(f"{gate} metadata file hash", _sha256(path) == recorded))
    cases: dict[str, set[str]] = {}
    for f in manifest["files"]:
        if f["case_id"]:
            cases.setdefault(f["case_id"], set()).add(f["modality"] or f["file_type"])
    dirs = {Path(r).parent.name for r in found}
    st.add(expect("case IDs equal the case folders on disk", set(cases) == dirs))
    st.add(
        expect(
            "every case has T1, T1c, T2, FLAIR and a label",
            all(v >= {"T1", "T1c", "T2", "FLAIR", "label"} for v in cases.values()),
        )
    )
    st.add(
        expect(
            "every case is listed in the hashed crosswalk", set(cases) <= set(crosswalk_case_ids)
        )
    )
    st.add(
        expect(
            f"case count = {EXPECTED['total']}",
            len(cases) == EXPECTED["total"],
            f"found {len(cases)}",
        )
    )
    return st.finish()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def check_split(
    *,
    site_of_case: Mapping[str, str],
    groups_csv: Path,
    split_csv: Path,
    split_hashes: Mapping[str, Any],
    verified_groups: Mapping[str, Sequence[str]],
    label_features: Callable[[str], tuple[bool, float]] | None,
    split_seed: int,
) -> Stage:
    """Rebuild the split from groups + independently computed label features."""
    st = Stage("SPLIT", "Split and patient-group verification")
    dev = sorted(c for c, s in site_of_case.items() if s != HOI_SITE)
    hoi = sorted(c for c, s in site_of_case.items() if s == HOI_SITE)
    st.add(
        expect("total cases = 1251", len(site_of_case) == EXPECTED["total"], str(len(site_of_case)))
    )
    st.add(
        expect("development (site != 1) = 740 before grouping", len(dev) == EXPECTED["development"])
    )
    st.add(expect("held-out institution (site 1) = 511", len(hoi) == EXPECTED["hoi"]))
    st.add(expect("split seed = 20260927", split_seed == EXPECTED_SPLIT_SEED))
    groups = {r["case_id"]: r["group_id"] for r in _read_csv(groups_csv)}
    split = {r["case_id"]: r["partition"] for r in _read_csv(split_csv)}
    st.add(expect("groups cover exactly the development cases", sorted(groups) == dev))
    st.add(expect("split covers exactly the development cases", sorted(split) == dev))
    st.add(
        expect(
            "no site-1 case in the split", not any(site_of_case.get(c) == HOI_SITE for c in split)
        )
    )
    part_of_group: dict[str, set[str]] = {}
    for c, g in groups.items():
        part_of_group.setdefault(g, set()).add(split.get(c, "?"))
    st.add(
        expect(
            "no patient group crosses partitions", all(len(p) == 1 for p in part_of_group.values())
        )
    )
    for name, group_cases in verified_groups.items():
        st.add(
            expect(
                f"verified group {name} in one group and one partition",
                len({groups.get(m) for m in group_cases}) == 1
                and len({split.get(m) for m in group_cases}) == 1,
            )
        )
    st.add(
        expect(
            "partitions are train/validation/internal_test", set(split.values()) <= set(PARTITIONS)
        )
    )
    for key, path in (
        ("split_all_csv_sha256", split_csv),
        ("patient_groups_dev_csv_sha256", groups_csv),
    ):
        st.add(expect(f"{key} matches the B12 record", _sha256(path) == split_hashes.get(key)))
    if label_features is None:
        st.add(
            Check("assignment rebuilt from labels", NOT_PERFORMED, detail="labels not available")
        )
        return st.finish()
    from brats_uncertainty.splitting.split import group_features, stratified_group_split

    feats = {c: label_features(c) for c in dev}
    members: dict[str, list[str]] = {}
    for c, g in groups.items():
        members.setdefault(g, []).append(c)
    rebuilt = stratified_group_split(
        group_features(
            {g: tuple(sorted(m)) for g, m in members.items()},
            {c: f[0] for c, f in feats.items()},
            {c: f[1] for c, f in feats.items()},
        )
    )
    diff = sorted(c for c in dev if rebuilt.assignments.get(c) != split.get(c))
    st.add(
        expect(
            "rebuilt assignment equals the recorded split",
            not diff,
            f"{len(diff)} differ: {diff[:3]}",
        )
    )
    return st.finish()


def check_runs(
    *,
    run_manifests: Mapping[str, Mapping[str, Any] | None],
    run_dirs: Mapping[str, Path],
    expected: Mapping[str, tuple[str, int, str]],
    manifest_sha256: str,
    split_sha256: str,
) -> Stage:
    """``expected``: job -> (arm, seed, trainer)."""
    st = Stage("RUNS", "Training-run provenance")
    ckpt_hashes: dict[str, str] = {}
    for job, (arm, seed, trainer) in expected.items():
        m = run_manifests.get(job)
        if m is None:
            st.add(Check(f"{job} manifest", NOT_PERFORMED, detail="run manifest missing"))
            continue
        st.add(
            expect(
                f"{job} identity (arm {arm}, seed {seed}, {trainer})",
                (m.get("arm"), m.get("seed"), m.get("trainer")) == (arm, seed, trainer),
            )
        )
        st.add(
            expect(f"{job} status COMPLETED (never INVALIDATED)", m.get("status") == "COMPLETED")
        )
        st.add(
            expect(
                f"{job} dataset manifest / split hashes",
                m.get("dataset_manifest_sha256") == manifest_sha256
                and m.get("split_sha256") == split_sha256,
            )
        )
        st.add(expect(f"{job} git commit recorded", bool(m.get("git_commit"))))
        ck = m.get("checkpoint") or {}
        path = run_dirs[job] / str(ck.get("path", ""))
        ok = (
            bool(ck) and str(ck.get("path", "")).endswith("checkpoint_final.pth") and path.is_file()
        )
        st.add(expect(f"{job} final checkpoint inside its own run directory", ok))
        if ok:
            h = _sha256(path)
            st.add(expect(f"{job} checkpoint hash equals the manifest", h == ck.get("sha256")))
            ckpt_hashes[job] = h
        attempts = m.get("attempts") or []
        st.add(
            expect(
                f"{job} attempts recorded with environment",
                bool(attempts)
                and all(a.get("environment_hash") and a.get("git_commit") for a in attempts),
            )
        )
    st.add(
        expect(
            "no checkpoint shared between runs", len(set(ckpt_hashes.values())) == len(ckpt_hashes)
        )
    )
    return st.finish()


def check_checkpoints(
    checkpoints: Mapping[str, tuple[Path, str, int]],
) -> Stage:
    """Load each final checkpoint (CPU) and check trainer name, epochs and 4 input channels.

    ``checkpoints``: job -> (path, expected trainer, expected epochs). Integrity only;
    nothing here is a scientific result.
    """
    st = Stage("CHECKPOINTS", "Checkpoint loading and metadata (integrity smoke test)")
    try:
        import torch
    except ImportError:
        st.add(Check("torch available", NOT_PERFORMED, detail="torch not installed"))
        return st.finish()
    for job, (path, trainer, epochs) in checkpoints.items():
        try:
            ck = torch.load(str(path), map_location="cpu", weights_only=False)
        except Exception as exc:  # report, never crash the verifier
            st.add(Check(f"{job} loads", NOT_PERFORMED, detail=str(exc)))
            continue
        st.add(expect(f"{job} trainer {trainer}", ck.get("trainer_name") == trainer))
        st.add(expect(f"{job} trained {epochs} epochs", int(ck.get("current_epoch", -1)) == epochs))
        weights = ck.get("network_weights", {})
        first = next(
            (v for k, v in weights.items() if k.endswith("weight") and getattr(v, "ndim", 0) == 5),
            None,
        )
        st.add(
            expect(
                f"{job} 4 input channels [T1, T1c, T2, FLAIR]",
                first is not None and int(first.shape[1]) == 4,
            )
        )
    return st.finish()


def not_applicable(stage_id: str, title: str, reason: str) -> Stage:
    return Stage(stage_id, title, status=NOT_APPLICABLE, detail=reason)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def label_features_nibabel(label_paths: Mapping[str, Path]) -> Callable[[str], tuple[bool, float]]:
    """ET presence and WT volume (mL, 1 mm voxels) read independently with nibabel."""

    def features(case: str) -> tuple[bool, float]:
        import nibabel as nib

        lab = np.asarray(nib.load(str(label_paths[case])).dataobj)  # type: ignore[attr-defined]
        zooms = nib.load(str(label_paths[case])).header.get_zooms()[:3]  # type: ignore[attr-defined]
        if not np.allclose(zooms, 1.0):  # BraTS preprocessing: 1 mm isotropic (§8)
            raise ValueError(f"{case}: voxel size {zooms} is not 1 mm isotropic")
        return bool((lab == 4).any()), int(np.isin(lab, (1, 2, 4)).sum()) / 1000.0

    return features
