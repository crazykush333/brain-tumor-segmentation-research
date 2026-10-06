"""Export website data (``website/data/*.json``) from the single sources of truth.

Sources: ``docs/project_status.yaml`` (status, gates, timeline),
``configs/protocol/protocol_v1.0.yaml`` (design parameters),
``experiments/*/metadata.yaml`` (experiment lifecycle) and
``results/index.json`` (provenance-checked result artifacts, if any).

The website never contains hand-typed status or numbers. ``--check`` mode
compares a fresh export to the committed files (CI sync test). Synthetic
artifacts are refused.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from brats_uncertainty import __version__
from brats_uncertainty.data.evidence import (
    SOURCE_CLASS_EXTERNAL,
    SOURCE_CLASS_OWNER,
    b1_source_class,
)
from brats_uncertainty.data.records import protocol_count_targets, read_record_body
from brats_uncertainty.errors import ProvenanceError
from brats_uncertainty.evaluation.status import load_status
from brats_uncertainty.experiments.metadata import load_experiment
from brats_uncertainty.protocol import load_protocol
from brats_uncertainty.results.artifacts import read_artifact

SITE_DATA_RELPATH = Path("website/data")
NO_RESULTS_STATEMENT = (
    "Scientific results are not yet available. Experimental execution is pending."
)


def _results(root: Path, status_raw: dict[str, Any]) -> dict[str, Any]:
    index_path = root / "results" / "index.json"
    artifacts: list[dict[str, Any]] = []
    if index_path.is_file():
        index = json.loads(index_path.read_text(encoding="utf-8"))
        for rel in index.get("artifacts", []):
            body = read_artifact(root / rel)
            if body["provenance"]["synthetic"]:
                raise ProvenanceError(f"synthetic artifact listed in results index: {rel}")
            artifacts.append({"path": rel, **body})
    available = bool(status_raw["results"].get("available")) and bool(artifacts)
    if bool(status_raw["results"].get("available")) != bool(artifacts):
        raise ProvenanceError(
            "results.available in project_status.yaml disagrees with results/index.json"
        )
    return {
        "available": available,
        "statement": status_raw["results"].get("statement", NO_RESULTS_STATEMENT),
        "artifacts": artifacts,
        "verification": verification_state(root, available=available),
    }


VERIFICATION_MANIFEST = Path("results/verification/verification_manifest.json")
VERIFICATION_CERTIFICATE = "results/verification/RESULT_VERIFICATION_CERTIFICATE.md"


def verification_state(root: Path, *, available: bool) -> dict[str, Any]:
    """Independent-verification state for the website.

    Scientific values reach the Results page only through ``result_index``, which is
    non-empty only when the independent verification of the scientific stages is
    VERIFIED and the results are published. Publishing unverified results is refused.
    """
    path = root / VERIFICATION_MANIFEST
    manifest: dict[str, Any] = (
        json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    )
    scientific = str(manifest.get("scientific_status", "NOT_RUN"))
    index = manifest.get("result_index") or {}
    verified = scientific == "VERIFIED"
    if available and not verified:
        raise ProvenanceError(
            "results.available is true but the independent verification is "
            f"{scientific} (results/verification/verification_manifest.json)"
        )
    if verified and not index:
        raise ProvenanceError("verification is VERIFIED but its result index is empty")
    if not verified and index:
        raise ProvenanceError("an unverified verification manifest lists result values")
    return {
        "scientific_status": scientific,
        "overall": str(manifest.get("overall", "NOT_RUN")),
        "generated_at": manifest.get("generated_at"),
        "certificate": VERIFICATION_CERTIFICATE,
        "result_index": index if (verified and available) else {},
    }


_DONE = ("CLOSED", "OWNER_WAIVED", "PASSED")


def _aggregate(statuses: list[str]) -> str:
    """Summarize a run of gates as one stage status."""
    if all(s in _DONE for s in statuses):
        return "COMPLETED"
    if all(s == "LOCKED" for s in statuses):
        return "LOCKED"
    if all(s == "NOT_STARTED" for s in statuses):
        return "NOT_STARTED"
    if any(s in ("BLOCKED", "FAILED") for s in statuses):
        return "BLOCKED"
    if any(s in _DONE or s in ("IN_PROGRESS", "RUNNING", "AUTHORIZED") for s in statuses):
        return "IN_PROGRESS"
    return "PENDING"


_GATE_ROWS = (
    (
        "b2",
        "B2",
        "B2 Data acquisition",
        "official files via the B1-approved route; inventory hashed",
    ),
    ("b3", "B3", "B3 Mapping-file hash", "exact SHA-256 of BraTS2021_MappingToTCIA.xlsx"),
    ("b4", "B4", "B4 UCSF-PDGM metadata hash", "exact SHA-256 of UCSF-PDGM-metadata_v5.csv"),
    ("b5", "B5", "B5 Data manifest", "integrity audit + hashed manifest"),
    (
        "b6",
        "B6",
        "B6 Count verification",
        "counts derived from the hashed crosswalk vs protocol targets",
    ),
    ("b7", "B7", "B7 Patient grouping", "T_screen and same-patient screen; after B6 has passed"),
    ("b8", "B8", "B8 Manual review", "flagged pairs reviewed"),
    ("b9", "B9", "B9 Patient groups", "patient groups frozen (IDs only)"),
    ("b10", "B10", "B10 Final split", "created once"),
    ("b11", "B11", "B11 Split assertions", "split assertions pass"),
    ("b12", "B12", "B12 Split hashes", "split hashes recorded"),
)


_BASIS_LABELS = {
    SOURCE_CLASS_OWNER: "Authorized — Owner-approved alternative",
    SOURCE_CLASS_EXTERNAL: "Authorized — external provider authorization",
}


def authorization_basis(raw: dict[str, Any], repo_root: Path | None) -> str | None:
    """Source class of the B1 evidence once B1 has passed (read from the evidence record)."""
    b1 = next((g for g in raw["gates"] if g["id"] == "B1"), None)
    if not b1 or b1.get("status") != "PASSED" or not b1.get("evidence") or repo_root is None:
        return None
    text = (repo_root / str(b1["evidence"]).split("#")[0]).read_text(encoding="utf-8")
    return b1_source_class(text)


def _b1_row(raw: dict[str, Any], status: str, repo_root: Path | None) -> dict[str, str]:
    row = {"key": "b1", "label": "B1 Data route", "status": status}
    if status != "PASSED":
        row["detail"] = (
            "a recorded data-route authorization is required before any data acquisition"
        )
        return row
    basis = authorization_basis(raw, repo_root)
    # B1's authorized state is PASSED in the gate lifecycle; never shown as "TCIA approved"
    row["status"] = "ROUTE_AUTHORIZED"
    row["status_label"] = _BASIS_LABELS.get(str(basis), "Authorized")
    if basis == SOURCE_CLASS_OWNER:
        row["detail"] = (
            "owner-approved alternative permitted by the frozen B1 wording (amendment v1.0-A1); "
            f"no external TCIA authorization is claimed. Route: {raw['data']['approved_route']}"
        )
    else:
        row["detail"] = f"Route: {raw['data']['approved_route']}"
    return row


AMENDMENTS_DIR = Path("docs/research/protocol-amendments")


def list_amendments(repo_root: Path) -> list[dict[str, str]]:
    """Logged protocol amendments (one file each, see the directory README); never hand-typed."""
    out = []
    for p in sorted((repo_root / AMENDMENTS_DIR).glob("*.md")):
        if p.name == "README.md":
            continue
        text = p.read_text(encoding="utf-8")
        fields = dict(
            re.findall(r"(?m)^(Amendment ID|Amendment type|Date):[ \t]*(.+?)[ \t]*$", text)
        )
        if "Amendment ID" not in fields:
            continue  # administrative entries are indexed in the README, not listed as amendments
        title = re.search(r"(?m)^# (.+)$", text)
        out.append(
            {
                "id": fields.get("Amendment ID", p.stem),
                "type": fields.get("Amendment type", ""),
                "date": fields.get("Date", ""),
                "title": title.group(1) if title else p.stem,
                "file": (AMENDMENTS_DIR / p.name).as_posix(),
            }
        )

    def order(a: dict[str, str]) -> tuple[str, int, str]:
        m = re.search(r"-A(\d+)$", a["id"])
        return (a["date"], int(m.group(1)) if m else 0, a["id"])

    return sorted(out, key=order)


def build_overview(
    raw: dict[str, Any], gate_status: dict[str, str], repo_root: Path | None = None
) -> list[dict[str, str]]:
    """High-level stage overview for the website, derived only from the status file."""

    def run(prefix: str, lo: int, hi: int) -> str:
        return _aggregate([gate_status[f"{prefix}{i}"] for i in range(lo, hi + 1)])

    docs = [raw["data"].get(k) for k in ("b1_record", "inquiry", "b1_evidence_template")]
    docs_ready = bool(all(docs)) and (
        repo_root is None or all((repo_root / str(d)).is_file() for d in docs)
    )
    ev = raw["evaluation"]
    evaluation = (
        "NOT_STARTED"
        if ev["internal"] == ev["external"] == "NOT_STARTED"
        else ("COMPLETED" if ev["internal"] == ev["external"] == "COMPLETED" else "IN_PROGRESS")
    )
    rows = [
        {
            "key": "protocol",
            "label": f"Protocol {raw['protocol']['version']}",
            "status": str(raw["protocol"]["status"]),
            "detail": f"frozen {raw['protocol']['frozen_on']}, tag {raw['protocol']['git_tag']}",
        },
        {
            "key": "route_docs",
            "label": "Data-route documentation",
            "status": "PREPARED" if docs_ready else "NOT_STARTED",
            "detail": "B1 record, TCIA inquiry and B1 evidence template prepared"
            + ("" if raw["data"].get("inquiry_sent") else " (inquiry not yet sent)"),
        },
        _b1_row(raw, gate_status["B1"], repo_root),
    ]
    rows += [
        {"key": key, "label": label, "status": gate_status[gid], "detail": detail}
        for key, gid, label, detail in _GATE_ROWS
    ]
    rows += [
        {
            "key": "training",
            "label": "Training",
            "status": str(raw["training"]["status"]),
            "detail": "arms A/B x seeds 0-2",
        },
        {
            "key": "evaluation",
            "label": "Evaluation",
            "status": evaluation,
            "detail": f"internal: {ev['internal']}; external: {ev['external']}",
        },
        {
            "key": "results",
            "label": "Results",
            "status": "AVAILABLE" if raw["results"]["status"] == "AVAILABLE" else "NOT_AVAILABLE",
            "detail": str(raw["results"]["statement"]),
        },
    ]
    return rows


def count_verification_state(
    repo_root: Path, raw: dict[str, Any]
) -> tuple[str, dict[str, Any] | None]:
    """B6 verification state derived ONLY from the gate status and its evidence record.

    - UNAVAILABLE: B6 has not produced a result (LOCKED/AUTHORIZED/RUNNING/BLOCKED);
    - VERIFIED_FROM_SOURCE: B6 PASSED on a REAL_RESEARCH_DATA record with that status;
    - FAILED_VERIFICATION: B6 FAILED.
    The protocol targets alone can never yield VERIFIED_FROM_SOURCE.
    """
    b6 = next((g for g in raw["gates"] if g["id"] == "B6"), None)
    if b6 is None:
        return "UNAVAILABLE", None
    if b6.get("status") == "FAILED":
        return "FAILED_VERIFICATION", None
    if b6.get("status") == "PASSED":
        rec = read_record_body(repo_root / str(b6["evidence"]))
        if (
            rec.get("status") != "VERIFIED_FROM_SOURCE"
            or rec.get("synthetic") is not False
            or rec.get("data_class") != "REAL_RESEARCH_DATA"
        ):
            raise ProvenanceError(
                "B6 is PASSED but its evidence is not a verified real-data record"
            )
        return "VERIFIED_FROM_SOURCE", rec
    return "UNAVAILABLE", None


def build_count_block(repo_root: Path, raw: dict[str, Any]) -> dict[str, Any]:
    """B6 counts for display: protocol targets unless a PASSED, verified B6 record exists."""
    block = protocol_count_targets()
    state, rec = count_verification_state(repo_root, raw)
    block["verification"] = state
    if state == "VERIFIED_FROM_SOURCE" and rec is not None:
        block.update(
            status="VERIFIED_FROM_SOURCE",
            label="Counts verified from the hashed crosswalk (gate B6)",
            targets=rec["targets"],
            counts=rec["counts"],
        )
    elif state == "FAILED_VERIFICATION":
        block.update(
            status="FAILED_VERIFICATION",
            label="Protocol verification targets (gate B6 verification FAILED; see B6 evidence)",
        )
    return block


def build_site_data(repo_root: str | Path) -> dict[str, Any]:
    root = Path(repo_root)
    protocol = load_protocol(root)
    status = load_status(root)
    experiments = []
    for meta_path in sorted((root / "experiments").glob("EXP-*/metadata.yaml")):
        m = load_experiment(meta_path)
        experiments.append(
            {
                "id": m.experiment_id,
                "title": m.title,
                "status": m.status,
                "protocol_sections": m.protocol_sections,
                "required_gates": m.required_gates,
                "notes": m.notes,
            }
        )
    raw = status.raw
    gates = [
        {
            "id": g.id,
            "group": g.group,
            "title": g.title,
            "status": g.status,
            "closed_on": g.closed_on,
        }
        for g in status.gates.values()
    ]
    return {
        "status.json": {
            "headline": raw["headline"],
            "last_updated": raw.get("last_updated"),
            "package_version": __version__,
            "protocol": raw["protocol"],
            "gates": gates,
            "gate_groups": raw.get("gate_groups", {}),
            "next_step": raw.get("next_step"),
            "timeline": raw.get("timeline", []),
            "overview": build_overview(raw, {g.id: g.status for g in status.gates.values()}, root),
            "count_verification": build_count_block(root, raw),
            "data": {
                k: raw["data"].get(k)
                for k in (
                    "authorization",
                    "approved_route",
                    "acquired",
                    "inquiry_sent",
                    "statement",
                )
            }
            | {"authorization_basis": authorization_basis(raw, root)},
            "project": raw.get("project", {}),
            "results_status": results_status(root, raw),
        },
        "protocol.json": {
            "version": protocol.version,
            "sha256": protocol.raw["protocol"]["sha256"],
            "git_tag": protocol.raw["protocol"]["git_tag"],
            "frozen_on": protocol.raw["protocol"]["frozen_on"],
            "amendments": list_amendments(root),
            "parameters": {k: v for k, v in protocol.raw.items() if k != "protocol"},
        },
        "experiments.json": {"experiments": experiments},
        "results.json": _results(root, raw),
        "demo.json": demo_site_data(root),
    }


RESULTS_STATUS_RELPATH = Path("results/status.json")
DEMO_DIR = Path("results/demo")
SITE_DEMO_FIGURES = Path("website/public/demo")


def results_status(root: Path, raw: dict[str, Any]) -> dict[str, Any]:
    """Machine-readable real-result status, derived from docs/project_status.yaml only."""
    available = bool(raw["results"].get("available"))
    acquired = bool(raw["data"].get("acquired"))
    executed = raw["evaluation"].get("internal") == "COMPLETED"
    if available:
        state = "results_available"
    elif executed or raw["training"].get("status") != "NOT_STARTED":
        state = "execution_in_progress"
    elif acquired:
        state = "data_acquired_execution_pending"
    else:
        state = "pending_official_data_and_compute"
    return {
        "scientific_results_available": available,
        "real_experiment_executed": executed,
        "real_brats_data_processed": acquired,
        "training_status": raw["training"].get("status"),
        "status": state,
        "synthetic_demo_available": (root / DEMO_DIR / "synthetic_summary.json").is_file(),
        "synthetic_results_in_scientific_namespace": False,
        "statement": raw["results"].get("statement", NO_RESULTS_STATEMENT),
        "generated_from": "docs/project_status.yaml (brats-uncertainty export-site-data)",
    }


def demo_site_data(root: Path) -> dict[str, Any]:
    """Website block for the synthetic demonstration (flags checked; never a result)."""
    from brats_uncertainty.demo import DEMO_FLAGS

    path = root / DEMO_DIR / "synthetic_summary.json"
    if not path.is_file():
        return {"available": False}
    body = json.loads(path.read_text(encoding="utf-8"))
    if any(body.get(k) != v for k, v in DEMO_FLAGS.items()):
        raise ProvenanceError("results/demo/synthetic_summary.json lacks the demo flags")
    keep = (
        "label",
        "disclaimer",
        "demo_seed",
        "generated_at",
        "git_commit",
        "code_sha256",
        "synthetic_study",
        "example_primary_statistic",
        "example_delta_aurc_by_condition",
        "example_tau_q",
        "example_threshold_transfer_q080",
        "example_mean_ece_et",
        "example_failure_counts",
        "bootstrap_replicates",
    )
    figures = sorted(p.name for p in (root / DEMO_DIR).glob("synthetic_*.svg"))
    return {
        "available": True,
        **DEMO_FLAGS,
        **{k: body[k] for k in keep if k in body},
        "figures": figures,
        "artifacts_path": DEMO_DIR.as_posix(),
    }


def _dump(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def export_site_data(repo_root: str | Path, *, check: bool = False) -> list[str]:
    """Write (or, with ``check``, compare) the website data files.

    Returns the list of files that differ (check mode) or were written.
    """
    root = Path(repo_root)
    out_dir = root / SITE_DATA_RELPATH
    data = build_site_data(root)
    changed: list[str] = []
    for name, obj in data.items():
        path = out_dir / name
        text = _dump(obj)
        current = path.read_text(encoding="utf-8") if path.is_file() else None
        if current != text:
            changed.append(name)
            if not check:
                out_dir.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8", newline="\n")
    changed += _export_extras(root, data["demo.json"], check=check)
    return changed


def _export_extras(root: Path, demo: dict[str, Any], *, check: bool) -> list[str]:
    """results/status.json and the demo figures copied for the website."""
    changed: list[str] = []
    targets: dict[Path, bytes] = {
        root / RESULTS_STATUS_RELPATH: _dump(results_status(root, load_status(root).raw)).encode(),
    }
    for name in demo.get("figures", []):
        targets[root / SITE_DEMO_FIGURES / name] = (root / DEMO_DIR / name).read_bytes()
    for path, content in targets.items():
        current = path.read_bytes() if path.is_file() else None
        if current != content:
            changed.append(path.relative_to(root).as_posix())
            if not check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
    return changed
