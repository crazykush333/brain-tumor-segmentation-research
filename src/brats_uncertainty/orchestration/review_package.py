"""Gate B8 review package (protocol §6.2 step 4): material for the two named reviewers.

Written ONLY to private storage (it contains patient images); never committed.
Contents:

- ``review_queue.csv``: every flagged pair with the permitted metadata (collection,
  site, TCIA ID) and the decision fields left empty;
- ``reviews_TEMPLATE.csv``: the exact header the frozen grouping code reads
  (``grouping.review.CSV_FIELDS``), one primary-review row per pair;
- ``pairs/<case_a>__<case_b>.png``: T1, T1c, T2 and FLAIR of both cases with the WT
  label contour, on the axial slice of largest combined WT area (all BraTS cases share
  SRI24 space, so no registration);
- ``README.md``: the frozen §6.2 procedure, quoted from the protocol file.

No Dice value, prediction or any study outcome is included (§6.2 "Never inspected").
Decisions are never filled in by software.
"""

from __future__ import annotations

import csv
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from brats_uncertainty.grouping.review import CSV_FIELDS
from brats_uncertainty.preprocessing.labels import BRATS2021_REGIONS

MODALITY_ORDER = ("T1", "T1c", "T2", "FLAIR")
QUEUE_FIELDS = (
    "case_a",
    "case_b",
    "collection_a",
    "collection_b",
    "site_a",
    "site_b",
    "tcia_id_a",
    "tcia_id_b",
    "decision",
    "reviewer",
    "round",
    "timestamp",
    "reason",
)


def protocol_section(protocol_text: str, heading: str = "### 6.2") -> str:
    """The protocol section starting at ``heading`` up to the next heading of that level."""
    lines = protocol_text.splitlines()
    start = next((i for i, ln in enumerate(lines) if ln.startswith(heading)), None)
    if start is None:
        raise ValueError(f"protocol section {heading!r} not found")
    level = heading.split(" ", 1)[0]
    end = next(
        (
            j
            for j in range(start + 1, len(lines))
            if lines[j].startswith("#") and len(lines[j].split(" ", 1)[0]) <= len(level)
        ),
        len(lines),
    )
    return "\n".join(lines[start:end]).strip() + "\n"


def review_slice(label_a: NDArray[Any], label_b: NDArray[Any]) -> int:
    """Axial index with the largest combined WT area (deterministic: lowest index on ties)."""
    wt = BRATS2021_REGIONS["WT"]
    area = np.isin(label_a, wt).sum(axis=(0, 1)) + np.isin(label_b, wt).sum(axis=(0, 1))
    return int(np.argmax(area))


def write_pair_figure(
    out: Path,
    case_a: str,
    case_b: str,
    images: Mapping[str, Mapping[str, NDArray[Any]]],
    labels: Mapping[str, NDArray[Any]],
) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    z = review_slice(labels[case_a], labels[case_b])
    fig, axes = plt.subplots(2, 4, figsize=(12, 6.4))
    for row, case in enumerate((case_a, case_b)):
        wt = np.isin(labels[case], BRATS2021_REGIONS["WT"])[:, :, z]
        for col, mod in enumerate(MODALITY_ORDER):
            ax = axes[row][col]
            ax.imshow(np.rot90(images[case][mod][:, :, z]), cmap="gray")
            if wt.any():
                ax.contour(np.rot90(wt), levels=[0.5], colors="r", linewidths=0.6)
            ax.set_title(f"{case} {mod} (z={z})", fontsize=8)
            ax.axis("off")
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=110)
    plt.close(fig)
    return out


def build_review_package(
    out_dir: Path,
    flagged: Sequence[tuple[str, str]],
    metadata: Mapping[str, Mapping[str, str]],
    protocol_text: str,
    reviewers: tuple[str, str],
    *,
    load_case: Callable[[str], tuple[Mapping[str, NDArray[Any]], NDArray[Any]]] | None = None,
) -> dict[str, Any]:
    """Write the package; ``load_case(case_id) -> (images by modality, label)`` draws figures."""
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "review_queue.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=QUEUE_FIELDS, lineterminator="\n")
        w.writeheader()
        for a, b in flagged:
            ma, mb = metadata.get(a, {}), metadata.get(b, {})
            w.writerow(
                {
                    "case_a": a,
                    "case_b": b,
                    "collection_a": ma.get("collection", ""),
                    "collection_b": mb.get("collection", ""),
                    "site_a": ma.get("site", ""),
                    "site_b": mb.get("site", ""),
                    "tcia_id_a": ma.get("tcia_id", ""),
                    "tcia_id_b": mb.get("tcia_id", ""),
                }
            )
    with (out_dir / "reviews_TEMPLATE.csv").open("w", encoding="utf-8", newline="") as fh:
        w2 = csv.DictWriter(fh, fieldnames=CSV_FIELDS, lineterminator="\n")
        w2.writeheader()
        for a, b in flagged:
            w2.writerow({"case_a": a, "case_b": b, "reviewer": reviewers[0], "round": "primary"})
    figures: list[str] = []
    if load_case is not None:
        cache: dict[str, tuple[Mapping[str, NDArray[Any]], NDArray[Any]]] = {}
        for a, b in flagged:
            for c in (a, b):
                if c not in cache:
                    cache[c] = load_case(c)
            fig = write_pair_figure(
                out_dir / "pairs" / f"{a}__{b}.png",
                a,
                b,
                {a: cache[a][0], b: cache[b][0]},
                {a: cache[a][1], b: cache[b][1]},
            )
            figures.append(fig.relative_to(out_dir).as_posix())
            if len(cache) > 64:  # bound memory on large queues
                cache.clear()
    readme = [
        "# Gate B8 review package (PRIVATE - contains patient images; never commit)",
        "",
        f"Flagged pairs: {len(flagged)}. Primary reviewer: {reviewers[0]}; "
        f"second reviewer (disagreements): {reviewers[1]}.",
        "",
        "Fill one `primary` row per pair in a copy of `reviews_TEMPLATE.csv` "
        "(decision SAME_PATIENT / DIFFERENT_PATIENT / UNRESOLVED, ISO timestamp, reason). "
        "Add a `second` row by the second reviewer for every disagreement. Save it as the "
        "committed decisions file named in configs/compute/master_run.yaml (IDs only), "
        "then re-run the master runner with --resume.",
        "",
        "Software never fills in a decision. Figures show T1, T1c, T2, FLAIR and the WT "
        "label contour of both cases on one axial slice; open the full volumes in a viewer "
        "where needed. No Dice value, prediction or outcome is shown.",
        "",
        "## Frozen procedure (verbatim from the protocol)",
        "",
        protocol_section(protocol_text),
    ]
    (out_dir / "README.md").write_text("\n".join(readme), encoding="utf-8", newline="\n")
    return {"n_pairs": len(flagged), "figures": figures, "dir": str(out_dir)}
