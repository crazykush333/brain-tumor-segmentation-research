"""End-to-end run of the analysis code on SYNTHETIC inputs (software test only).

Synthetic member probabilities -> scores -> units -> primary statistic ->
threshold transfer -> provenance-stamped artifact in a temporary directory.
Nothing here is a result; nothing is written inside the repository.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from brats_uncertainty.inference.ensemble import binarize, ensemble_mean
from brats_uncertainty.metrics.dice import dice
from brats_uncertainty.preprocessing.modalities import C5_NAMES
from brats_uncertainty.results.artifacts import (
    ArtifactProvenance,
    ResultArtifact,
    read_artifact,
    write_artifact,
)
from brats_uncertainty.statistics.primary import run_primary
from brats_uncertainty.statistics.thresholds import select_tau, threshold_transfer
from brats_uncertainty.statistics.units import UnitTable
from brats_uncertainty.uncertainty.scores import case_scores
from brats_uncertainty.utils.hashing import sha256_json
from tests.fixtures.synthetic import sphere, synthetic_member_probs


def _units(seed: int, n_cases: int) -> UnitTable:
    rng = np.random.default_rng(seed)
    rows: dict[str, list] = {"case": [], "group": [], "cond": [], "risk": [], "U1": []}
    for i in range(n_cases):
        for c in C5_NAMES:
            probs = synthetic_member_probs(
                rng, shape=(14, 14, 14), noise=float(rng.uniform(0.05, 0.4))
            )
            gt = sphere((14, 14, 14), (7, 7, 7), 3)
            pred = binarize(ensemble_mean(probs))
            rows["case"].append(f"SYN-{seed}-{i:03d}")
            rows["group"].append(f"SYN-G{seed}-{i // 2:03d}")
            rows["cond"].append(c)
            rows["risk"].append(1.0 - dice(pred, gt))
            rows["U1"].append(case_scores(probs)["U1"])
    return UnitTable.from_columns(
        rows["case"], rows["group"], rows["cond"], rows["risk"], {"U1": rows["U1"]}
    )


def test_synthetic_end_to_end(tmp_path: Path) -> None:
    test_units = _units(seed=1, n_cases=12)
    val_units = _units(seed=2, n_cases=10)
    primary = run_primary(test_units, n_replicates=100)
    assert np.isfinite(primary.mean_c4.estimate)
    tau = select_tau(val_units.score("U1"), val_units.condition, 0.80)
    transfer = threshold_transfer(val_units, test_units, tau, n_replicates=100)
    assert 0.0 <= transfer.target_coverage <= 1.0
    payload = {"synthetic_primary": primary.mean_c4.as_dict(), "tau": tau.tau}
    art = ResultArtifact(
        kind="bootstrap_result",
        name="synthetic-smoke",
        payload=payload,
        provenance=ArtifactProvenance(
            experiment_id="SYNTHETIC-TEST",
            git_commit="0" * 40,
            config_sha256=sha256_json({"synthetic": True}),
            protocol_sha256="704c0b495917344f44b93e7548ade0e32a71220265419516a2c83d626fcd9811",
            input_sha256={"synthetic_units": sha256_json(test_units.risk.tolist())},
            generated_at="2000-01-01T00:00:00Z",
            synthetic=True,
        ),
    )
    p = write_artifact(tmp_path / "synthetic.json", art, repo_root=tmp_path)
    body = read_artifact(p)
    assert body["provenance"]["synthetic"] is True
