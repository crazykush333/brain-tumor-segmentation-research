"""SYNTHETIC nested-collection training tree, mirroring the official TCIA BraTS 2021 layout.

    <root>/<collection>/<case_id>/<case_id>_{t1,t1ce,t2,flair,seg}.nii.gz

Built at test time inside pytest temporary directories (never committed: the
repository refuses NIfTI files). Case IDs are clearly synthetic
(``BraTS2021_SYNTH001`` ...): they do not match the real ``BraTS2021_\\d{5}``
pattern and never name a real patient. Files are tiny all-zero NIfTI headers.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from brats_uncertainty.data.schema import DatasetSchema
from brats_uncertainty.data.synthetic import write_nifti_header_file

NESTED_SCHEMA = DatasetSchema(
    name="synthetic-nested",
    case_id_pattern=r"BraTS2021_SYNTH\d{3}",
    modality_suffixes={"T1": "_t1", "T1c": "_t1ce", "T2": "_t2", "FLAIR": "_flair"},
    label_suffix="_seg",
    file_ending=".nii.gz",
    verified_on_files=False,
)
SUFFIXES = ("_t1", "_t1ce", "_t2", "_flair", "_seg")
DEFAULT_TREE: dict[str, tuple[str, ...]] = {
    "ACRIN-FMISO-Brain": ("BraTS2021_SYNTH001",),
    "UCSF-PDGM": ("BraTS2021_SYNTH002",),
    "UPENN-GBM": ("BraTS2021_SYNTH003",),
}


def write_case(case_dir: Path, case_id: str, suffixes: Sequence[str] = SUFFIXES) -> None:
    for s in suffixes:
        write_nifti_header_file(case_dir / f"{case_id}{s}.nii.gz", (4, 4, 3))


def write_volume_case(case_dir: Path, case_id: str, seed: int, shape=(6, 5, 4)) -> None:  # type: ignore[no-untyped-def]
    """SYNTHETIC case with real voxel data (needs nibabel): 4 float channels + a BraTS-style
    label with values {0, 1, 2, 4}. Deterministic per seed; never real data."""
    import gzip
    import io

    import nibabel as nib
    import numpy as np

    rng = np.random.default_rng(seed)
    case_dir.mkdir(parents=True, exist_ok=True)
    affine = np.eye(4)

    def save(arr, name: str) -> None:  # type: ignore[no-untyped-def]
        buf = io.BytesIO()
        with gzip.GzipFile(filename="", mode="wb", fileobj=buf, mtime=0) as gz:
            gz.write(nib.Nifti1Image(arr, affine).to_bytes())
        (case_dir / name).write_bytes(buf.getvalue())

    for i, s in enumerate(("_t1", "_t1ce", "_t2", "_flair")):
        save(rng.normal(size=shape).astype(np.float32) + i, f"{case_id}{s}.nii.gz")
    label = rng.choice(np.array([0, 1, 2, 4], dtype=np.int16), size=shape)
    save(label, f"{case_id}_seg.nii.gz")


def make_nested_training_tree(
    root: Path, tree: Mapping[str, Sequence[str]] = DEFAULT_TREE, *, reverse: bool = False
) -> Path:
    """``root/<collection>/<case>/`` for every case; ``reverse`` creates them in reverse order."""
    items = [(c, cid) for c, ids in tree.items() for cid in ids]
    for collection, cid in reversed(items) if reverse else items:
        write_case(root / collection / cid, cid)
    return root
