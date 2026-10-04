"""FAKE gate evidence for TEMPORARY test repositories only.

These records are fully schema-valid so that the positive paths of the gate
machinery can be tested. They exist only inside pytest temporary directories.
They are marked with an obviously fake commit (``f`` * 40), a fake route and
"FAKE" names, and they never reach the real repository.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from brats_uncertainty import __version__
from brats_uncertainty.data.manifest_doc import build_raw_manifest
from brats_uncertainty.data.records import (
    B6_TARGETS,
    CROSSWALK_FILENAME,
    UCSF_METADATA_FILENAME,
    AcquisitionRecord,
    CountsRecord,
    HashedFile,
    InventoryEntry,
    MetadataFileRecord,
    ProvenanceStamp,
    SourceInfo,
    record_body,
    write_record,
)
from brats_uncertainty.data.schema import DatasetSchema
from brats_uncertainty.data.synthetic import write_nifti_header_file
from brats_uncertainty.utils.hashing import sha256_bytes, sha256_file

FAKE_ROUTE = "SYNTHETIC-TEST-ROUTE"
FAKE_COMMIT = "f" * 40
PROTOCOL_SHA = "704c0b495917344f44b93e7548ade0e32a71220265419516a2c83d626fcd9811"
FAKE_SCHEMA = DatasetSchema(
    name="fake",
    case_id_pattern=r"FAKE-\d{3}",
    modality_suffixes={"T1": "_t1", "T1c": "_t1ce", "T2": "_t2", "FLAIR": "_flair"},
    label_suffix="_seg",
    file_ending=".nii.gz",
    verified_on_files=False,
)


def fake_stamp() -> ProvenanceStamp:
    return ProvenanceStamp(
        created_at="2000-01-01T00:00:00+00:00",
        code_commit=FAKE_COMMIT,
        code_dirty=False,
        package_version=__version__,
        protocol_version="v1.0",
        protocol_sha256=PROTOCOL_SHA,
        config_sha256={},
        environment={},
    )


def fake_source() -> SourceInfo:
    return SourceInfo("FAKE", "fake-1", "10.0000/fake", "https://fake.invalid/source", FAKE_ROUTE)


B1_FAKE_FIELDS = {
    "Source class": "EXTERNAL_PROVIDER_AUTHORIZATION",
    "Protocol version": "v1.0",
    "Dataset": "FAKE",
    "DOI": "10.0000/fake",
    "Inquiry date": "1999-12-01",
    "Recipient": "fake-provider@fake.invalid",
    "Sender": "pytest",
    "Proposed route": FAKE_ROUTE,
    "Route category": "B",
    "Evidence type": "TCIA Help Desk written response",
    "Provider/source": "FAKE provider (temporary test repository)",
    "Response date": "2000-01-01",
    "Evidence reference": "FAKE-TICKET-0",
    "Interpretation": "FAKE: the fake route is permitted",
    "Conditions": "None stated",
    "Restrictions": "None stated",
    "Attribution requirements": "Cite the FAKE DOI",
    "Approved route": FAKE_ROUTE,
    "Authorization status": "AUTHORIZED",
    "Conclusion": "APPROVED",
}


def b1_evidence_text(wording: str = "> FAKE: this route is fine.", **fields: str) -> str:
    """FAKE B1 evidence in the template's format; ``fields`` override single values."""
    values = {**B1_FAKE_FIELDS, **fields}
    lines = "".join(f"{k}: {v}\n" for k, v in values.items())
    return (
        "# FAKE TEST EVIDENCE (temporary test repository)\n\n"
        f"{lines}\n## Exact provider wording\n\n{wording}\n\n## Notes\n\nFAKE.\n"
    )


def write_b1_evidence(root: Path, route: str = FAKE_ROUTE, text: str | None = None) -> str:
    rel = "docs/data/B1_EVIDENCE_2000-01-01.md"
    (root / rel).parent.mkdir(parents=True, exist_ok=True)
    body = text if text is not None else b1_evidence_text(**{"Approved route": route})
    (root / rel).write_text(body, encoding="utf-8")
    return rel


def build_fake_chain(root: Path) -> dict[str, str]:
    """Write linked, valid fake B2-B6 evidence records under ``root/evidence``; return paths."""
    ev = root / "evidence"
    ev.mkdir(parents=True, exist_ok=True)
    work = root / "fake_work"
    tree = work / "images"
    for suffix in ("_t1", "_t1ce", "_t2", "_flair", "_seg"):
        write_nifti_header_file(tree / "FAKE-001" / f"FAKE-001{suffix}.nii.gz")
    xw = work / "metadata" / CROSSWALK_FILENAME
    ucsf = work / "metadata" / UCSF_METADATA_FILENAME
    xw.parent.mkdir(parents=True, exist_ok=True)
    xw.write_bytes(b"FAKE crosswalk bytes")
    ucsf.write_bytes(b"FAKE ucsf bytes")
    stamp = fake_stamp()
    b2 = AcquisitionRecord(
        gate="B2",
        synthetic=False,
        source=fake_source(),
        adapter="local-import",
        acquired_at="2000-01-01T00:00:00+00:00",
        acquired_by="pytest",
        storage_location="data/raw/fake",
        inventory=(InventoryEntry("fake.bin", sha256_bytes(b"fake"), 4),),
        stamp=stamp,
    )
    b3 = MetadataFileRecord(
        "B3",
        False,
        "crosswalk",
        HashedFile.from_path(xw),
        "data/raw/fake/x",
        "https://fake.invalid/b3",
        "10.0000/fake",
        stamp,
    )
    b4 = MetadataFileRecord(
        "B4",
        False,
        "ucsf_pdgm_metadata",
        HashedFile.from_path(ucsf),
        "data/raw/fake/u",
        "https://fake.invalid/b4",
        "10.0000/fake",
        stamp,
    )
    paths = {}
    for gid, rec in (("B2", b2), ("B3", b3), ("B4", b4)):
        paths[gid] = f"evidence/{gid}_record.json"
        write_record(root / paths[gid], rec)
    b5 = build_raw_manifest(
        tree, FAKE_SCHEMA, b2, stamp, metadata=[(xw, b3), (ucsf, b4)], extra={"gate": "B5"}
    )
    paths["B5"] = "evidence/B5_manifest.json"
    (root / paths["B5"]).write_text(json.dumps(b5, indent=2, sort_keys=True), encoding="utf-8")
    b6 = CountsRecord(
        gate="B6",
        synthetic=False,
        status="VERIFIED_FROM_SOURCE",
        crosswalk_sha256=sha256_file(xw),
        crosswalk_matches_b3=True,
        b3_record_fingerprint=str(record_body(b3)["record_fingerprint"]),
        counts=dict(B6_TARGETS),
        targets=dict(B6_TARGETS),
        checks={k: True for k in B6_TARGETS},
        diagnostics=[],
        site_counts={"1": 511, "18": 740},
        hoi_site_id="1",
        development_ids_sha256=sha256_bytes(b"fake dev"),
        hoi_ids_sha256=sha256_bytes(b"fake hoi"),
        stamp=stamp,
    )
    paths["B6"] = "evidence/B6_record.json"
    write_record(root / paths["B6"], b6)
    return paths


def write_record_copy(root: Path, rel: str, body: dict) -> str:  # type: ignore[type-arg]
    (root / rel).parent.mkdir(parents=True, exist_ok=True)
    (root / rel).write_text(json.dumps(body, indent=2, sort_keys=True), encoding="utf-8")
    return rel


__all__ = [
    "B1_FAKE_FIELDS",
    "FAKE_ROUTE",
    "asdict",
    "b1_evidence_text",
    "build_fake_chain",
    "fake_stamp",
    "write_b1_evidence",
    "write_record_copy",
]
