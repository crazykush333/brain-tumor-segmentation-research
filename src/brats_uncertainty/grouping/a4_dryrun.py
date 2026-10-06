"""Pre-split dry run of the v1.0-A4 metadata linkage (``brats-uncertainty b8-a4-dryrun``).

Inputs:
- the official crosswalk and UCSF-PDGM metadata, verified against the B3/B4 hashes;
- the committed B7 flagged pairs;
- the protocol's verified groups;
- the committed B6 development-set hash.

The production procedure and the independent re-implementation
(``verification.linkage_audit``) are run side by side. Only IDs, decisions and
aggregate counts are written. No split is created and no gate changes.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from brats_uncertainty.data.crosswalk import read_table_records
from brats_uncertainty.data.records import read_metadata_record
from brats_uncertainty.errors import ProvenanceError
from brats_uncertainty.grouping import metadata_linkage as ml
from brats_uncertainty.utils.io import read_yaml
from brats_uncertainty.verification import linkage_audit as la

CONFIG = Path("configs/grouping/b8_metadata_linkage_v1.0-A4.yaml")


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run(repo: Path, crosswalk: Path, ucsf: Path, out_dir: Path) -> dict[str, Any]:
    rec = repo / "docs/data/records"
    for path, gate in ((crosswalk, "B3"), (ucsf, "B4")):
        if _sha(path) != read_metadata_record(rec / f"{gate}.json").file.sha256:
            raise ProvenanceError(f"{path.name} differs from the {gate} record")
    cw = [
        r
        for r in read_table_records(crosswalk)
        if str(r.get("Segmentation (Task 1) Cohort") or "") == "Training"
    ]
    uc = read_table_records(ucsf)
    ids = ml.build_identities(cw, uc)
    dev = sorted(c for c, i in ids.items() if i.site != "1")
    b6 = json.loads((rec / "B6.json").read_text("utf-8"))
    dev_sha = hashlib.sha256(("\n".join(dev) + "\n").encode()).hexdigest()
    if dev_sha != b6["development_ids_sha256"]:
        raise ProvenanceError("development set differs from the B6 record")
    with (rec / "B7/flagged_pairs.csv").open(encoding="utf-8", newline="") as fh:
        flagged = [(r["case_a"], r["case_b"]) for r in csv.DictReader(fh)]
    verified = read_yaml(repo / "configs/protocol/protocol_v1.0.yaml")["grouping"][
        "verified_groups"
    ]
    res = ml.adjudicate(dev, flagged, ids, verified)
    idec = la.decide(dev, flagged, la.identities(cw, uc), verified)
    reconciliation = la.reconcile(res.decisions, res.groups, idec, la.components(dev, idec))
    has_id = {c: ids[c].tcia_id is not None or ids[c].ucsf_base is not None for c in dev}
    unres = [k for k, (d, _r) in res.decisions.items() if d == ml.UNRESOLVED]
    big = res.groups[0]
    sensitivity = {
        "dev_cases_with_authoritative_identity": sum(has_id.values()),
        "dev_cases_without_authoritative_identity": sum(not v for v in has_id.values()),
        "without_identity_by_collection": dict(
            sorted(Counter(ids[c].collection for c in dev if not has_id[c]).items())
        ),
        "unresolved_pairs": len(unres),
        "unresolved_pairs_by_site": dict(sorted(Counter(ids[a].site for a, _ in unres).items())),
        "cases_in_unresolved_pairs": len({c for p in unres for c in p}),
        "largest_group_by_collection": dict(
            sorted(Counter(ids[c].collection for c in big).items())
        ),
        "largest_group_sites": dict(sorted(Counter(ids[c].site for c in big).items())),
        "metadata_same_pairs_beyond_verified_groups": sorted(
            [a, b]
            for (a, b), (_d, r) in res.decisions.items()
            if r in ("M2", "M3") and not any({a, b} <= set(g) for g in verified.values())
        ),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "decisions.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(ml.DECISION_FIELDS)
        for (a, b), (d, r) in sorted(res.decisions.items()):
            w.writerow([a, b, d, r])
    report = {
        "procedure": "v1.0-A4 metadata linkage (pre-split dry run)",
        "config_sha256": _sha(repo / CONFIG),
        "inputs_sha256": {"crosswalk": _sha(crosswalk), "ucsf_metadata": _sha(ucsf)},
        "n_flagged": len({tuple(sorted(p)) for p in flagged}),
        **ml.summary(res, len(dev)),
        "independent_reconciliation": reconciliation,
        "sensitivity": sensitivity,
        "not_used": [
            "image similarity",
            "WT-Dice values",
            "model predictions",
            "split",
            "validation/test results",
        ],
    }
    (out_dir / "summary.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report
