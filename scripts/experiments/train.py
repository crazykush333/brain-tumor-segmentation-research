"""[GATED: B1-B12, D1-D6] Launch one protocol training run (arm A/B, seed 0/1/2).

Default is a dry run that prints the exact command and environment. ``--execute``
runs nnU-Net only after the gate check passes. The trainer module must first be
verified against the pinned nnU-Net version (docs/reproducibility/COMPUTE.md).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

from brats_uncertainty.evaluation.guards import require_action
from brats_uncertainty.models.nnunet import (
    MAIN_EXPERIMENT_ID,
    RunSpec,
    run_namespace,
    train_command,
    train_environment,
)
from brats_uncertainty.utils.paths import find_repo_root


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dataset-id", required=True, type=int)
    p.add_argument("--arm", required=True, choices=["A", "B"])
    p.add_argument("--seed", required=True, type=int, choices=[0, 1, 2])
    p.add_argument(
        "--results-root", required=True, help="parent of the per-run nnUNet_results folders"
    )
    p.add_argument("--execute", action="store_true")
    a = p.parse_args()
    require_action("train_main", find_repo_root())
    run = RunSpec(a.arm, a.seed)
    # per-run results root: the three seeds of an arm must not share one nnUNet_results
    run_dir = run_namespace(a.results_root, MAIN_EXPERIMENT_ID, run)
    cmd, env = train_command(a.dataset_id, run), train_environment(run, run_dir)
    # resumable, recorded execution: `brats-uncertainty job-run JOB-0x ...` (compute.jobs)
    print(" ".join(cmd), env)
    if not a.execute:
        return 0
    return subprocess.run(cmd, env={**os.environ, **env}, check=False).returncode


if __name__ == "__main__":
    sys.exit(main())
