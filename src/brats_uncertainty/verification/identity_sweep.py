"""Final v1.0-A5 metadata identity-recovery sweep (``brats-uncertainty a5-identity-sweep``).

Every development case without an authoritative identity (B3 crosswalk, B4 UCSF-PDGM v5
metadata, official follow-up rename list) is checked against every further official
TCIA identity resource of the BraTS 2021 analysis result:
- ``NotPreviouslyInTCIA.csv``: NIfTI series with no TCIA DICOM equivalent;
- ``GC_manifest_RSNA-ASNR-MICCAI-BRATS-2021_sources.csv``: file IDs to TCIA series UIDs.

A case gains an identity only if one of these resources ties it to a TCIA patient,
study or series. Only IDs, hashes and counts are written. No gate changes.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from brats_uncertainty.data.crosswalk import read_table_records
from brats_uncertainty.data.records import read_metadata_record
from brats_uncertainty.errors import ProvenanceError
from brats_uncertainty.utils.io import read_yaml
from brats_uncertainty.verification import identity_audit as ia

A5_CONFIG = Path("configs/grouping/b8_identity_clean_v1.0-A5.yaml")
TCIA_UPLOADS = "https://www.cancerimagingarchive.net/wp-content/uploads/"
_CASE = re.compile(r"BraTS2021_\d{5}")


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _sha_ids(ids: list[str]) -> str:
    return hashlib.sha256(("\n".join(sorted(ids)) + "\n").encode()).hexdigest()


def run(
    repo: Path, crosswalk: Path, ucsf: Path, not_previously: Path, gc_manifest: Path
) -> dict[str, Any]:
    rec = repo / "docs/data/records"
    for path, gate in ((crosswalk, "B3"), (ucsf, "B4")):
        if _sha(path) != read_metadata_record(rec / f"{gate}.json").file.sha256:
            raise ProvenanceError(f"{path.name} differs from the {gate} record")
    cfg = read_yaml(repo / A5_CONFIG)
    renamed = {int(k): int(v) for k, v in cfg["ucsf_renamed_follow_ups"].items()}
    cw = read_table_records(crosswalk)
    uc = read_table_records(ucsf)
    ids = ia.identity_keys(cw, uc, renamed, list(cfg["tcga_namespace_collections"]))
    dev = sorted(c for c, (site, _coll, _key) in ids.items() if site != "1")
    b6 = json.loads((rec / "B6.json").read_text("utf-8"))
    if _sha_ids(dev) != b6["development_ids_sha256"]:
        raise ProvenanceError("development set differs from the B6 record")
    unresolved = [c for c in dev if ids[c][2] is None]

    npt_lines = not_previously.read_text(encoding="utf-8").splitlines()
    npt_cases = {m for line in npt_lines for m in _CASE.findall(line)}
    # a line ties a case to a TCIA identity only if it names something beyond the
    # 'new-not-previously-in-TCIA' folder and the case's own NIfTI files
    npt_identity = {
        m
        for line in npt_lines
        for m in _CASE.findall(line)
        if "new-not-previously-in-TCIA" not in line
    }
    gc_text = gc_manifest.read_text(encoding="utf-8")
    gc_header = gc_text.splitlines()[0] if gc_text else ""
    gc_cases = set(_CASE.findall(gc_text))
    resolved = sorted((npt_identity | gc_cases) & set(unresolved))
    return {
        "procedure": "A5 final metadata identity-recovery sweep",
        "config": A5_CONFIG.as_posix(),
        "config_sha256": _sha(repo / A5_CONFIG),
        "sources": {
            "crosswalk": {"file": crosswalk.name, "sha256": _sha(crosswalk), "record": "B3"},
            "ucsf_metadata": {"file": ucsf.name, "sha256": _sha(ucsf), "record": "B4"},
            "not_previously_in_tcia": {
                "file": not_previously.name,
                "url": TCIA_UPLOADS + not_previously.name,
                "sha256": _sha(not_previously),
                "lines": len(npt_lines),
            },
            "gc_sources_manifest": {
                "file": gc_manifest.name,
                "url": TCIA_UPLOADS + gc_manifest.name,
                "sha256": _sha(gc_manifest),
                "columns": gc_header,
                "mentions_any_brats_case_id": bool(gc_cases),
            },
            "ucsf_follow_up_notice": cfg["sources"]["ucsf_follow_up_notice"],
        },
        "n_development_pool": len(dev),
        "n_checked_without_identity": len(unresolved),
        "checked_by_collection": dict(sorted(Counter(ids[c][1] for c in unresolved).items())),
        "unresolved_listed_as_not_previously_in_tcia": len(set(unresolved) & npt_cases),
        "n_newly_resolved": len(resolved),
        "newly_resolved": resolved,
        "n_remaining_unresolved": len(unresolved) - len(resolved),
        "remaining_unresolved_ids_sha256": _sha_ids(sorted(set(unresolved) - set(resolved))),
        "reproducible_with": "brats-uncertainty a5-identity-sweep (inputs verified by hash)",
    }
