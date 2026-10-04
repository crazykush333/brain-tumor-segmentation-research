"""Case loop of the evaluation: ensemble probabilities -> unit rows, resumable per case.

``EnsembleSource`` hides the GPU part: ``member_probabilities(case, subset)`` returns,
per region, the three members' probability maps (members ordered by seed 0, 1, 2) for
the case with ``subset``'s missing channels zeroed in the normalized tensor (§10);
``ground_truth(case)`` returns the GT region masks in the same array space. The real
implementation is ``study.nnunet_inference.NnUNetEnsembleSource``.

Progress is journaled per completed case in ``<out>.partial.jsonl`` so an interrupted
session resumes after the last completed case; the final units file is written once.
Probability maps are never stored (§17), only the unit rows.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Protocol

import numpy as np
from numpy.typing import NDArray

from brats_uncertainty.errors import DataValidationError
from brats_uncertainty.preprocessing.modalities import ModalitySubset
from brats_uncertainty.study.units import Hd95Fn, unit_rows, write_units


class EnsembleSource(Protocol):
    def member_probabilities(
        self, case_id: str, subset: ModalitySubset
    ) -> Mapping[str, Sequence[NDArray[np.floating]]]: ...

    def ground_truth(self, case_id: str) -> Mapping[str, NDArray[np.bool_]]: ...


def evaluate_cases(
    *,
    cases: Sequence[str],
    group_of: Mapping[str, str],
    dataset: str,
    arm: str,
    conditions: Sequence[str],
    source: EnsembleSource,
    out: Path,
    hd95: Hd95Fn | None = None,
    on_case: Callable[[str], None] | None = None,
) -> Path:
    """Evaluate every case under every condition; resume from the per-case journal."""
    if out.exists():
        return out  # completed earlier: never recomputed
    missing = [c for c in cases if c not in group_of]
    if missing:
        raise DataValidationError(f"cases without a patient group: {missing[:5]}")
    journal = out.with_name(out.name + ".partial.jsonl")
    done: dict[str, list[dict[str, str]]] = {}
    if journal.is_file():
        for line in journal.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                done[rec["case_id"]] = rec["rows"]
    out.parent.mkdir(parents=True, exist_ok=True)
    subsets = [ModalitySubset.from_name(c) for c in conditions]
    for case in sorted(cases):
        if case in done:
            continue
        gt = source.ground_truth(case)
        rows: list[dict[str, str]] = []
        for subset in subsets:
            rows += unit_rows(
                case_id=case,
                group_id=group_of[case],
                dataset=dataset,
                arm=arm,
                condition=subset.name,
                member_probs=source.member_probabilities(case, subset),
                gt=gt,
                hd95=hd95,
            )
        with journal.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps({"case_id": case, "rows": rows}, sort_keys=True) + "\n")
        done[case] = rows
        if on_case is not None:
            on_case(case)
    unknown = set(done) - set(cases)
    if unknown:
        raise DataValidationError(
            f"journal holds cases outside this evaluation: {sorted(unknown)[:5]}"
        )
    write_units(out, [r for c in sorted(done) for r in done[c]])
    journal.unlink()
    return out
