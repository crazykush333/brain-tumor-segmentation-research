"""[GATED: B1-B12, D1-D6, C5, C6 + eval-v1] Primary H-W analysis on the internal test set.

Reads the per-unit metric CSV (protocol §24), runs the patient-group bootstrap
(10,000 replicates, seed 12345) and writes a provenance-stamped artifact. The
evaluation is recorded in the single-evaluation ledger (SR4).
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

from brats_uncertainty.evaluation.guards import EVAL_TAG, require_action
from brats_uncertainty.evaluation.ledger import LEDGER_RELPATH, record_evaluation
from brats_uncertainty.protocol import load_protocol
from brats_uncertainty.results.artifacts import ArtifactProvenance, ResultArtifact, write_artifact
from brats_uncertainty.statistics.primary import run_primary
from brats_uncertainty.statistics.units import read_units_csv
from brats_uncertainty.utils.git import git_commit
from brats_uncertainty.utils.hashing import sha256_file
from brats_uncertainty.utils.paths import find_repo_root


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--units", required=True, type=Path, help="per-unit metric CSV, arm B")
    p.add_argument("--config", default=Path("configs/evaluation/evaluation.yaml"), type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--reevaluation-reason", default=None)
    a = p.parse_args()
    root = find_repo_root()
    require_action("evaluate_internal_test", root)
    spec = load_protocol(root)
    commit = git_commit(root) or ""
    record_evaluation(
        root / LEDGER_RELPATH, "internal_test", "B", commit, EVAL_TAG, a.reevaluation_reason
    )
    units = read_units_csv(a.units, region="ET")
    res = run_primary(units)
    payload = {
        "mean_c4": res.mean_c4.as_dict(),
        "per_condition": {c: r.as_dict() for c, r in res.per_condition.items()},
        "ci_entirely_below_zero": res.ci_entirely_below_zero(),
    }
    art = ResultArtifact(
        kind="bootstrap_result",
        name="H-W primary (internal test, arm B, ET)",
        payload=payload,
        provenance=ArtifactProvenance(
            experiment_id="MAIN",
            git_commit=commit,
            config_sha256=sha256_file(a.config),
            protocol_sha256=spec.raw["protocol"]["sha256"],
            input_sha256={a.units.name: sha256_file(a.units)},
            generated_at=datetime.now(UTC).isoformat(),
            synthetic=False,
        ),
    )
    write_artifact(a.out, art, repo_root=root)
    print(f"artifact written: {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
