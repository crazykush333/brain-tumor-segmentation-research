"""Step registry of the master run: every protocol gate and run, in dependency order.

Each step has an executor that either completes it (PASSED) or stops with the exact
blocker and the exact action needed (BLOCKED / REVIEW_REQUIRED / FAILED). Executors
only call the repository's existing gated stages; none re-implements science, and
none can bypass a research gate (``require_action`` runs inside every stage).

B-gate pattern (``GateStep``): AUTHORIZED -> RUNNING (committed) -> stage writes its
execution record into the committed records directory -> record committed -> PASSED
with that record as evidence (committed). A crash at any point resumes from the
committed state: an existing record is re-used, never re-produced.

Nothing here invents an input. A missing official delivery, a missing review
decision or an unimplemented executor is reported, not worked around.
"""

from __future__ import annotations

import csv
import shlex
import shutil
import traceback
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from brats_uncertainty.errors import (
    BratsUncertaintyError,
    DataValidationError,
    ProtocolDeviationError,
    ResearchGateError,
)
from brats_uncertainty.evaluation.lifecycle import CLOSED_STATUSES
from brats_uncertainty.orchestration.state import (
    BLOCKED,
    FAILED,
    LOCKED,
    PASSED,
    RUNNING,
    Outcome,
)
from brats_uncertainty.utils.io import read_json, read_yaml, write_json

MASTER_CONFIG = Path("configs/compute/master_run.yaml")
DATASET_CONFIG = Path("configs/dataset/brats2021.yaml")


# --------------------------------------------------------------------------- control flow
class StepStop(Exception):  # noqa: N818 - control flow, not an error
    """Raised by an executor to stop with an exact blocker and action."""

    status = BLOCKED

    def __init__(self, summary: str, action: str, **details: Any) -> None:
        super().__init__(summary)
        self.summary, self.action, self.details = summary, action, details


class StepBlocked(StepStop):
    status = BLOCKED


class StepReview(StepStop):
    status = "REVIEW_REQUIRED"


class StepFailed(StepStop):
    status = FAILED


# --------------------------------------------------------------------------- context
class Ops(Protocol):
    """Side effects, injectable for tests."""

    def gate_status(self, gid: str) -> str: ...

    def transition(
        self, gid: str, new: str, *, evidence: str | None = None, on: str | None = None
    ) -> list[str]: ...

    def milestone(self, message: str) -> str | None: ...

    def run(
        self, cmd: Sequence[str], *, cwd: Path | None = None, env: Mapping[str, str] | None = None
    ) -> int: ...

    def preflight(self, job: str | None) -> Any: ...

    def fetch(self, url: str, dest: Path) -> None: ...


@dataclass
class Context:
    repo_root: Path
    work_dir: Path
    state_dir: Path
    cfg: dict[str, Any]
    environ: Mapping[str, str]
    ops: Ops
    offline: bool = False
    approvals: frozenset[str] = frozenset()  # explicit owner approvals given on the CLI
    process_runner: Any = None  # EXP-001 process runner (default: real subprocesses)
    ensemble_factory: Any = None  # (kind, arm, cases) -> EnsembleSource (default: nnU-Net)
    today: str = field(default_factory=lambda: datetime.now(UTC).date().isoformat())

    @property
    def records(self) -> Path:
        return self.repo_root / self.cfg["paths"]["records_dir"]

    @property
    def splits(self) -> Path:
        return self.repo_root / self.cfg["paths"]["splits_dir"]

    @property
    def raw_root(self) -> Path:
        return self.work_dir / "raw"

    def rel(self, p: Path) -> str:
        return p.resolve().relative_to(self.repo_root.resolve()).as_posix()

    def training_root(self) -> Path:
        return self.raw_root / self.cfg["acquisition"]["training_set"]

    def metadata_path(self, gate: str) -> Path:
        item = next(m for m in self.cfg["acquisition"]["metadata_files"] if m["gate"] == gate)
        return self.raw_root / item["name"]


def load_master_config(repo_root: Path) -> dict[str, Any]:
    return read_yaml(repo_root / MASTER_CONFIG)


# --------------------------------------------------------------------------- step model
@dataclass(frozen=True)
class Step:
    id: str
    title: str
    phase: str
    needs: tuple[str, ...]
    execute: Callable[[Context], Outcome]
    gate: str | None = None  # project_status gate this step closes
    job: str | None = None  # remote_compute.yaml job whose compute requirements apply
    milestone: bool = True  # commit/push + website sync after PASSED


def gate_closed(ctx: Context, gid: str) -> bool:
    return ctx.ops.gate_status(gid) in CLOSED_STATUSES


def run_guarded(ctx: Context, step: Step) -> Outcome:
    """Execute a step, converting stops and unexpected errors into outcomes."""
    try:
        return step.execute(ctx)
    except StepStop as stop:
        return Outcome(stop.status, stop.summary, stop.action, details=stop.details)
    except ResearchGateError as exc:
        return Outcome(
            BLOCKED,
            f"research gate refused: {exc}",
            "close the unmet gates legitimately (they are listed above); the runner never "
            "bypasses a gate",
        )
    except (DataValidationError, ProtocolDeviationError) as exc:
        return Outcome(
            FAILED,
            f"integrity/protocol assertion failed: {exc}",
            f"investigate; the run stops here (no later step runs). After the cause is "
            f"documented, re-run with --retry {step.id}",
        )
    except (BratsUncertaintyError, OSError) as exc:
        return Outcome(
            BLOCKED,
            f"{type(exc).__name__}: {exc}",
            f"fix the reported problem, then re-run with --resume (step {step.id} resumes)",
        )
    except Exception as exc:  # a real bug: never continue past it silently
        return Outcome(
            FAILED,
            f"unexpected error (possible bug): {type(exc).__name__}: {exc}",
            "a real bug needs human review before continuing; traceback is in the state "
            f"journal. After the fix, re-run with --retry {step.id}",
            details={"traceback": traceback.format_exc(limit=8)},
        )


# --------------------------------------------------------------------------- B gates
def gate_step_executor(
    gid: str,
    produce: Callable[[Context], list[Path]],
    *,
    describe: str,
    confirm: str | None = None,
) -> Callable[[Context], Outcome]:
    def execute(ctx: Context) -> Outcome:
        st = ctx.ops.gate_status(gid)
        if st in CLOSED_STATUSES:
            return Outcome(PASSED, f"{gid} already {st}")
        if st == LOCKED:
            raise StepBlocked(
                f"{gid} is LOCKED in docs/project_status.yaml although its prerequisites ran",
                "inspect docs/project_status.yaml (status validation names the cause)",
            )
        if st in ("FAILED", "BLOCKED"):
            raise StepReview(
                f"{gid} is {st} in docs/project_status.yaml",
                f"owner decision: document it and move {gid} with `brats-uncertainty "
                "gate-transition` (FAILED -> BLOCKED -> AUTHORIZED); the runner never "
                "reopens a failed gate itself",
            )
        if confirm is not None:
            from brats_uncertainty.orchestration.study_steps import require_confirmations

            require_confirmations(ctx, confirm)
        if st == "AUTHORIZED":
            ctx.ops.transition(gid, "RUNNING")
            ctx.ops.milestone(f"chore(gates): {gid} RUNNING ({describe})")
        evidence = produce(ctx)
        ctx.ops.milestone(f"data({gid}): {describe} execution record")
        ctx.ops.transition(gid, "PASSED", evidence=ctx.rel(evidence[0]), on=ctx.today)
        ctx.ops.milestone(f"chore(gates): {gid} PASSED ({describe})")
        return Outcome(PASSED, f"{gid} PASSED: {describe}", evidence=[ctx.rel(p) for p in evidence])

    return execute


def _delivery_dir(ctx: Context) -> Path:
    """Route B (official delivery already in private storage) or route A (receive)."""
    acq = ctx.cfg["acquisition"]
    env_dir = ctx.environ.get(acq["delivery_env"], "").strip()
    if env_dir:
        return Path(env_dir)
    cmd, evidence = acq.get("receive_command"), acq.get("receive_command_evidence")
    if not cmd or not evidence:
        raise StepBlocked(
            "B2: no official delivery and no verified official receive command",
            f"either (A) set acquisition.receive_command and acquisition.receive_command_"
            f"evidence in {MASTER_CONFIG} to the exact command confirmed from the installed "
            f"IBM Aspera CLI's own help (`ascli faspex5 -h`; save that output in the "
            f"repository as the evidence file), or (B) receive the official package with the "
            f"official client into private storage and set {acq['delivery_env']} to that "
            "folder. Nothing is guessed",
        )
    if not (ctx.repo_root / evidence).is_file():
        raise StepBlocked(
            f"B2: receive-command evidence {evidence} not found",
            "commit the client help output that confirms the receive command",
        )
    if not acq.get("selected_gib"):
        raise StepBlocked(
            "B2: selection size unknown",
            "enter the selection size the official client shows for the training set + .sums "
            "as acquisition.selected_gib (measured, never guessed)",
        )
    delivery = ctx.work_dir / "delivery"
    if not (delivery / acq["sums_file"]).is_file():
        from brats_uncertainty.data.preflight import GIB, storage_preflight

        pre = storage_preflight(
            int(float(acq["selected_gib"]) * GIB),
            delivery_dir=delivery,
            storage_dir=ctx.raw_root,
        )
        if not pre.ok:
            raise StepBlocked(
                f"B2: storage preflight failed: {pre.describe()}",
                "provide persistent storage with enough free space (compute environment "
                "insufficient)",
            )
        delivery.mkdir(parents=True, exist_ok=True)
        code = ctx.ops.run(shlex.split(str(cmd)), cwd=delivery)
        if code != 0:
            raise StepBlocked(
                f"B2: official receive command exited {code}",
                "inspect the client output above; re-run with --resume (the client resumes "
                "partial transfers by its own mechanism only if it supports that)",
            )
    return delivery


def _tree_bytes(root: Path) -> int:
    return sum(p.stat().st_size for p in root.rglob("*") if p.is_file())


def produce_b2(ctx: Context) -> list[Path]:
    from brats_uncertainty.data.acquisition import LocalImportAdapter, stage_acquire
    from brats_uncertainty.data.preflight import storage_preflight
    from brats_uncertainty.data.records import SourceInfo
    from brats_uncertainty.data.stages import stage_verify_checksums

    acq = ctx.cfg["acquisition"]
    record = ctx.records / "B2.json"
    checks = ctx.records / "B2_provider_checksums.json"
    if record.is_file():
        return [record, checks]  # resume: the committed/written record is the result
    delivery = _delivery_dir(ctx)
    missing = [
        n
        for n, p in (
            (acq["sums_file"], delivery / acq["sums_file"]),
            (acq["training_set"], delivery / acq["training_set"]),
        )
        if not p.exists()
    ]
    if missing:
        raise StepBlocked(
            f"B2: official delivery at {delivery} lacks {missing}",
            "deliver exactly the official .sums file and the training set (official nested "
            "hierarchy, never flattened) into that folder",
        )
    for item in acq["metadata_files"]:
        dest = delivery / item["name"]
        if not dest.is_file():
            if ctx.offline:
                raise StepBlocked(
                    f"B2: {item['name']} missing and the runner is offline",
                    f"download it byte-for-byte from {item['url']} into {delivery}",
                )
            ctx.ops.fetch(item["url"], dest)
    pre = storage_preflight(_tree_bytes(delivery), delivery_dir=delivery, storage_dir=ctx.raw_root)
    if not pre.ok:
        raise StepBlocked(
            f"B2: storage preflight for the import copy failed: {pre.describe()}",
            "provide more persistent storage (compute environment insufficient)",
        )
    ctx.records.mkdir(parents=True, exist_ok=True)
    if not checks.is_file():
        stage_verify_checksums(
            ctx.repo_root,
            delivery / acq["sums_file"],
            delivery,
            prefix=acq["training_set"],
            out=checks,
        )
    source = SourceInfo(
        dataset=acq["dataset"],
        dataset_version=acq["dataset_version"],
        doi=acq["doi"],
        source_url=acq["source_url"],
        route=acq["route"],
    )
    stage_acquire(
        ctx.repo_root,
        LocalImportAdapter(source, delivery),
        storage_root=ctx.raw_root,
        out_record=record,
        acquired_by=acq["acquired_by"],
        execute=True,
        storage_label="private study storage",
    )
    return [record, checks]


def _metadata_producer(gid: str) -> Callable[[Context], list[Path]]:
    def produce(ctx: Context) -> list[Path]:
        from brats_uncertainty.data.stages import stage_hash_metadata

        out = ctx.records / f"{gid}.json"
        if out.is_file():
            return [out]
        item = next(m for m in ctx.cfg["acquisition"]["metadata_files"] if m["gate"] == gid)
        stage_hash_metadata(
            ctx.repo_root,
            gid,
            ctx.metadata_path(gid),
            source_url=item["source_url"],
            doi=ctx.cfg["acquisition"]["doi"],
            out=out,
            path_reference=f"private study storage/{item['name']}",
        )
        return [out]

    return produce


def produce_b5(ctx: Context) -> list[Path]:
    from brats_uncertainty.data.stages import stage_build_manifest

    out = ctx.records / "B5_manifest.json"
    out_csv = ctx.records / "B5_manifest.csv"
    if out.is_file():
        return [out, out_csv]
    stage_build_manifest(
        ctx.repo_root,
        ctx.repo_root / DATASET_CONFIG,
        ctx.training_root(),
        ctx.records / "B2.json",
        out,
        out_csv=out_csv,
        metadata_files=[ctx.metadata_path("B3"), ctx.metadata_path("B4")],
        metadata_records=[ctx.records / "B3.json", ctx.records / "B4.json"],
        data_root_reference=ctx.cfg["acquisition"]["training_set"],
    )
    return [out, out_csv]


def produce_b6(ctx: Context) -> list[Path]:
    from brats_uncertainty.data.records import read_counts_record
    from brats_uncertainty.data.stages import stage_derive_counts

    out = ctx.records / "B6.json"
    if not out.is_file():
        stage_derive_counts(
            ctx.repo_root,
            ctx.metadata_path("B3"),
            ctx.records / "B3.json",
            ctx.repo_root / DATASET_CONFIG,
            out,
        )
    rec = read_counts_record(out)
    if rec.status != "VERIFIED_FROM_SOURCE":
        raise StepFailed(
            f"B6: counts not verified ({rec.status}): {rec.counts}",
            "SR3 applies (protocol §20): the owner decides and logs the deviation; no later "
            "gate runs",
        )
    return [out]


def crosswalk_rows(ctx: Context) -> list[Any]:
    from brats_uncertainty.data.crosswalk import parse_rows, read_table_records

    cw = read_yaml(ctx.repo_root / DATASET_CONFIG)["crosswalk"]
    return parse_rows(read_table_records(ctx.metadata_path("B3"), cw.get("sheet")), cw["columns"])


def development_rows(ctx: Context) -> list[Any]:
    from brats_uncertainty.protocol import load_protocol

    hoi = str(load_protocol(ctx.repo_root).raw["cohorts"]["hoi_site_id"])
    return [r for r in crosswalk_rows(ctx) if r.site_id != hoi]


def _b7_dir(ctx: Context) -> Path:
    return ctx.records / "B7"


def produce_b7(ctx: Context) -> list[Path]:
    from brats_uncertainty.data.manifest_doc import load_case_manifest
    from brats_uncertainty.pipeline import stage_screen, stage_t_screen

    out = _b7_dir(ctx)
    t_screen = out / "t_screen.json"
    summary = out / "screen_summary.json"
    if summary.is_file():
        return [t_screen, out / "flagged_pairs.csv", summary]
    manifest = load_case_manifest(ctx.records / "B5_manifest.json")
    out.mkdir(parents=True, exist_ok=True)
    if not t_screen.is_file():  # computed once, before the distribution is examined
        stage_t_screen(ctx.repo_root, manifest, ctx.training_root(), t_screen)
    dev_ids = [r.case_id for r in development_rows(ctx)]
    stage_screen(ctx.repo_root, manifest, ctx.training_root(), t_screen, dev_ids, out)
    return [t_screen, out / "flagged_pairs.csv", summary]


def flagged_pairs(ctx: Context) -> list[tuple[str, str]]:
    with (_b7_dir(ctx) / "flagged_pairs.csv").open(encoding="utf-8", newline="") as fh:
        return [(r["case_a"], r["case_b"]) for r in csv.DictReader(fh)]


def _review_file(ctx: Context) -> Path | None:
    rv = ctx.cfg["review"]
    env = ctx.environ.get(rv["decisions_env"], "").strip()
    committed = ctx.repo_root / rv["decisions_file"]
    if env:
        src = Path(env)
        if src.is_file() and not committed.is_file():
            committed.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, committed)  # decisions are committed (IDs only)
    return committed if committed.is_file() else None


def produce_b8(ctx: Context) -> list[Path]:
    from brats_uncertainty.grouping.review import read_reviews, resolve_reviews
    from brats_uncertainty.protocol import load_protocol

    spec = load_protocol(ctx.repo_root)
    flagged = flagged_pairs(ctx)
    record = ctx.records / "B8_review_record.json"
    if record.is_file():
        return [record, ctx.repo_root / ctx.cfg["review"]["decisions_file"]]
    decisions_path = _review_file(ctx)
    if flagged and decisions_path is None:
        package = ctx.work_dir / "review" / "B8"
        info = _write_b8_package(ctx, flagged, package)
        raise StepReview(
            f"B8: {len(flagged)} flagged pair(s) need the frozen §6.2 manual review",
            f"reviewers {spec.reviewers[0]} (primary) and {spec.reviewers[1]} (disagreements) "
            f"review the private package at {package} and record SAME_PATIENT / "
            f"DIFFERENT_PATIENT / UNRESOLVED per pair in {ctx.cfg['review']['decisions_file']} "
            "(header of reviews_TEMPLATE.csv); also confirm the second-review resolution rule "
            "noted in src/brats_uncertainty/grouping/review.py. Then re-run with --resume",
            package=info,
        )
    decisions: dict[str, str] = {}
    if flagged:
        assert decisions_path is not None
        resolved = resolve_reviews(flagged, read_reviews(decisions_path), spec.reviewers)
        decisions = {f"{a}|{b}": d for (a, b), d in resolved.items()}
    write_json(
        record,
        {
            "gate": "B8",
            "n_flagged": len(flagged),
            "decisions": decisions,
            "reviewers": list(spec.reviewers),
            "decisions_file": ctx.cfg["review"]["decisions_file"] if flagged else None,
            "recorded_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        },
    )
    out = [record]
    if decisions_path is not None:
        out.append(decisions_path)
    return out


def _write_b8_package(
    ctx: Context, flagged: list[tuple[str, str]], package: Path
) -> dict[str, Any]:
    from brats_uncertainty.data.manifest_doc import load_case_manifest
    from brats_uncertainty.orchestration.review_package import build_review_package
    from brats_uncertainty.pipeline import load_label
    from brats_uncertainty.protocol import load_protocol

    rows = {r.case_id: r for r in crosswalk_rows(ctx)}
    meta = {
        c: {"collection": r.collection, "site": r.site_id, "tcia_id": r.tcia_subject_id or ""}
        for c, r in rows.items()
    }
    manifest = {e.case_id: e for e in load_case_manifest(ctx.records / "B5_manifest.json").entries}
    root = ctx.training_root()

    def load_case(cid: str) -> tuple[dict[str, Any], Any]:
        import nibabel as nib
        import numpy as np

        e = manifest[cid]
        assert e.label is not None
        images = {
            m: np.asarray(nib.load(str(root / f.relpath)).dataobj, dtype=np.float32)  # type: ignore[attr-defined]
            for m, f in e.images.items()
        }
        return images, load_label(root / e.label.relpath)

    text = (ctx.repo_root / "docs/research/FINAL_RESEARCH_PROTOCOL_v1.0.md").read_text("utf-8")
    return build_review_package(
        package, flagged, meta, text, load_protocol(ctx.repo_root).reviewers, load_case=load_case
    )


def produce_b9(ctx: Context) -> list[Path]:
    from brats_uncertainty.pipeline import stage_freeze_groups

    out = ctx.splits / "patient_groups_dev.csv"
    audit = ctx.splits / "grouping_audit_dev.json"
    if out.is_file():
        return [out, audit]
    reviews = ctx.repo_root / ctx.cfg["review"]["decisions_file"]
    if not reviews.is_file():  # zero flagged pairs: an empty, valid review file
        from brats_uncertainty.grouping.review import write_reviews

        reviews.parent.mkdir(parents=True, exist_ok=True)
        write_reviews(reviews, [])
    stage_freeze_groups(
        ctx.repo_root,
        development_rows(ctx),
        _b7_dir(ctx) / "flagged_pairs.csv",
        reviews,
        ctx.splits,
    )
    return [out, audit]


def _labels(ctx: Context) -> dict[str, Path]:
    from brats_uncertainty.data.manifest_doc import load_case_manifest

    root = ctx.training_root()
    m = load_case_manifest(ctx.records / "B5_manifest.json")
    return {e.case_id: root / e.label.relpath for e in m.entries if e.label}


def produce_b10(ctx: Context) -> list[Path]:
    from brats_uncertainty.grouping.groups import PatientGrouping
    from brats_uncertainty.pipeline import stage_create_split

    split = ctx.splits / "split_all.csv"
    summary = ctx.splits / "split_summary.json"
    if split.is_file():
        return [split, summary]
    with (ctx.splits / "patient_groups_dev.csv").open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    groups: dict[str, list[str]] = {}
    for r in rows:
        groups.setdefault(r["group_id"], []).append(r["case_id"])
    grouping = PatientGrouping(
        prefix="DEV",
        case_to_group={r["case_id"]: r["group_id"] for r in rows},
        groups={g: tuple(sorted(m)) for g, m in groups.items()},
        link_sources={},
    )
    stage_create_split(ctx.repo_root, crosswalk_rows(ctx), grouping, _labels(ctx), ctx.splits)
    return [split, summary]


def produce_b11(ctx: Context) -> list[Path]:
    # §6.3 assertions run inside stage_create_split before anything is written (B10);
    # a split file therefore exists only if every assertion passed.
    summary = ctx.splits / "split_summary.json"
    if not summary.is_file():
        raise StepBlocked("B11: split summary missing", "B10 must complete first")
    return [summary]


def split_partitions(ctx: Context) -> dict[str, list[str]]:
    parts: dict[str, list[str]] = {}
    with (ctx.splits / "split_all.csv").open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            parts.setdefault(r["partition"], []).append(r["case_id"])
    return {k: sorted(v) for k, v in parts.items()}


def produce_b12(ctx: Context) -> list[Path]:
    from brats_uncertainty.utils.hashing import sha256_bytes, sha256_file

    out = ctx.splits / "split_hashes.json"
    if out.is_file():
        return [out]
    parts = split_partitions(ctx)
    write_json(
        out,
        {
            "gate": "B12",
            "split_all_csv_sha256": sha256_file(ctx.splits / "split_all.csv"),
            "patient_groups_dev_csv_sha256": sha256_file(ctx.splits / "patient_groups_dev.csv"),
            "partition_id_list_sha256": {
                k: sha256_bytes(("\n".join(v) + "\n").encode()) for k, v in sorted(parts.items())
            },
            "partition_counts": {k: len(v) for k, v in sorted(parts.items())},
        },
    )
    return [out]


# --------------------------------------------------------------------------- D gates
def _execution_doc(ctx: Context, name: str, lines: list[str]) -> Path:
    path = ctx.repo_root / "docs/research/execution" / name
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return path


def close_cd_gate(ctx: Context, gid: str, evidence: Path, describe: str) -> Outcome:
    st = ctx.ops.gate_status(gid)
    if st in CLOSED_STATUSES:
        return Outcome(PASSED, f"{gid} already closed")
    ctx.ops.milestone(f"docs({gid}): {describe}")
    ctx.ops.transition(gid, "CLOSED", evidence=ctx.rel(evidence), on=ctx.today)
    ctx.ops.milestone(f"chore(gates): {gid} CLOSED ({describe})")
    return Outcome(PASSED, f"{gid} CLOSED: {describe}", evidence=[ctx.rel(evidence)])


D1_EVIDENCE = "docs/research/execution/D1_EXP-001_OWNER_AUTHORIZATION_2026-10-04.md"


def execute_d1(ctx: Context) -> Outcome:
    ev = ctx.repo_root / D1_EVIDENCE
    if not ev.is_file():
        raise StepReview(
            "D1: no owner authorization record for EXP-001",
            f"the owner records the EXP-001 authorization in {D1_EVIDENCE}",
        )
    return close_cd_gate(ctx, "D1", ev, "owner authorization of EXP-001")


def execute_d2(ctx: Context) -> Outcome:
    from brats_uncertainty.evaluation.status import load_status

    st = load_status(ctx.repo_root)
    b1 = st.gate("B1")
    if not b1.is_closed:
        raise StepBlocked("D2: B1 has not passed", "B1 must pass first")
    ev = _execution_doc(
        ctx,
        "D2_APPROVED_DATA_ROUTE.md",
        [
            "# Gate D2: approved data route (B1)",
            "",
            f"- B1 status: {b1.status} on {b1.closed_on}; evidence: `{b1.evidence}`.",
            f"- Approved route: {st.raw['data']['approved_route']}.",
            "- Basis: owner-approved alternative, amendment v1.0-A1; external provider "
            "authorization: none (recorded in the B1 evidence).",
            "",
            "D2 restates B1 for the compute pilot; it adds no new authorization.",
        ],
    )
    return close_cd_gate(ctx, "D2", ev, "approved data route (B1)")


def _pilot_constraint(gid: str, text: str) -> Callable[[Context], Outcome]:
    def execute(ctx: Context) -> Outcome:
        ev = ctx.repo_root / ctx.cfg["paths"]["exp001_dir"] / "constraints.json"
        if not ev.is_file():
            raise StepBlocked(f"{gid}: pilot constraint record missing", "EXP-001 must run first")
        body = read_json(ev)
        if not body.get(gid):
            raise StepFailed(f"{gid}: pilot constraint violated: {text}", "owner review")
        return close_cd_gate(ctx, gid, ev, text)

    return execute


# --------------------------------------------------------------------------- training
def training_executor(job_id: str) -> Callable[[Context], Outcome]:
    def execute(ctx: Context) -> Outcome:
        from brats_uncertainty.compute.jobs import find_checkpoint, load_jobs, read_manifest
        from brats_uncertainty.models.nnunet import run_namespace

        job = load_jobs(ctx.repo_root)[job_id]
        from brats_uncertainty.orchestration.study_steps import (
            _set_status,
            planned_epochs,
            require_confirmations,
        )

        epochs = planned_epochs(ctx)  # 250, or 150 under SR1/SR6 (D6)
        results_root = ctx.work_dir / "nnunet_results"
        run_dir = run_namespace(results_root, job.experiment_id, job.run)
        manifest = read_manifest(run_dir)
        if manifest and manifest["status"] == "COMPLETED":
            _publish_run_manifest(ctx, job.experiment_id, run_dir)
            return Outcome(PASSED, f"{job_id} COMPLETED", evidence=[str(run_dir.name)])
        if manifest and manifest["status"] == "INVALIDATED":
            raise StepFailed(
                f"{job_id}: run INVALIDATED ({manifest.get('invalidation_reason')})",
                "an invalidated run never resumes; owner decision required",
            )
        resume = restart = False
        if manifest is not None:
            if find_checkpoint(run_dir, "checkpoint_latest.pth"):
                resume = True
            elif f"restart:{job_id}" in ctx.approvals:
                restart = True
            else:
                raise StepReview(
                    f"{job_id}: earlier attempt ({manifest['status']}) left no checkpoint",
                    f"owner approval to restart it from scratch: re-run with --approve-restart "
                    f"{job_id} (recorded in the run manifest)",
                )
        require_confirmations(ctx, job_id.replace("JOB", "TRAIN"))
        _set_status(
            ctx,
            {("training", "status"): "IN_PROGRESS"},
            message="chore(status): training IN_PROGRESS",
        )
        from brats_uncertainty.models.trainer_registration import register_trainers

        register_trainers()
        dataset_id, provenance = _ensure_nnunet_dataset(ctx)
        b5 = read_json(ctx.records / "B5_manifest.json")
        hashes = read_json(ctx.splits / "split_hashes.json")
        from brats_uncertainty.compute.jobs import run_training_job

        rec = run_training_job(
            ctx.repo_root,
            job,
            dataset_id=dataset_id,
            results_root=results_root,
            dataset_provenance=provenance,
            manifest_sha256=str(b5["manifest_sha256"]),
            split_sha256=str(hashes["split_all_csv_sha256"]),
            resume=resume,
            restart_without_checkpoint=restart,
            epochs=epochs,
        )
        if rec["status"] != "COMPLETED":
            raise StepBlocked(
                f"{job_id}: run {rec['status']} after attempt {len(rec['attempts'])}",
                "re-run with --resume: the run continues from its own verified checkpoint "
                "(never from scratch silently)",
            )
        _publish_run_manifest(ctx, job.experiment_id, run_dir)  # committed at the milestone
        return Outcome(PASSED, f"{job_id} COMPLETED", evidence=[run_dir.name])

    return execute


def _publish_run_manifest(ctx: Context, experiment: str, run_dir: Path) -> None:
    src = run_dir / "run_manifest.json"
    if src.is_file():
        dest = ctx.repo_root / "results" / experiment / "runs" / run_dir.name / "run_manifest.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)


def _ensure_nnunet_dataset(ctx: Context) -> tuple[int, Path]:
    from brats_uncertainty.data.nnunet_dataset import write_nnunet_dataset
    from brats_uncertainty.data.schema import load_schema
    from brats_uncertainty.models.nnunet import build_splits_final, plan_and_preprocess_command

    tr = ctx.cfg["training"]
    did, name = int(tr["dataset_id"]), str(tr["dataset_name"])
    raw_base = ctx.work_dir / "nnUNet_raw"
    pre_base = ctx.work_dir / "nnUNet_preprocessed"
    raw = raw_base / f"Dataset{did:03d}_{name}"
    env = {"nnUNet_raw": str(raw_base), "nnUNet_preprocessed": str(pre_base)}
    parts = split_partitions(ctx)
    if not raw.is_dir():
        write_nnunet_dataset(
            ctx.repo_root,
            ctx.training_root(),
            load_schema(ctx.repo_root / DATASET_CONFIG),
            raw,
            dataset_id=did,
            dataset_name=name,
            case_ids=parts["train"] + parts["validation"],  # never test data (§8)
            gate_action="train_main",
            training_root_reference=ctx.cfg["acquisition"]["training_set"],
        )
    plans = pre_base / raw.name / "nnUNetPlans.json"
    if not plans.is_file():
        code = ctx.ops.run(plan_and_preprocess_command(did), env=env)
        if code != 0:
            raise StepBlocked(
                f"nnU-Net plan/preprocess exited {code}", "inspect its output; re-run with --resume"
            )
    splits_final = pre_base / raw.name / "splits_final.json"
    if not splits_final.is_file():
        write_json(splits_final, build_splits_final(parts["train"], parts["validation"]))
    return did, raw / "conversion_provenance.json"


# --------------------------------------------------------------------------- registry
def build_steps() -> list[Step]:
    """All steps in protocol order. ``needs`` are runner-level dependencies."""
    from brats_uncertainty.orchestration import study_steps as ss

    b = gate_step_executor
    steps = [
        Step(
            "ENV",
            "Environment preflight (measured facts, every session)",
            "env",
            (),
            _execute_env,
            milestone=False,
        ),
        Step("D1", "Owner authorization of EXP-001", "D", (), execute_d1, gate="D1"),
        Step("D2", "Approved data route (B1)", "D", (), execute_d2, gate="D2"),
        Step(
            "B2",
            "Official data acquired via the approved route",
            "B",
            ("ENV",),
            b("B2", produce_b2, describe="official acquisition", confirm="B2"),
            gate="B2",
            job="JOB-01",
        ),
        Step(
            "B3",
            "SHA-256 of BraTS2021_MappingToTCIA.xlsx",
            "B",
            ("B2",),
            b("B3", _metadata_producer("B3"), describe="crosswalk hash"),
            gate="B3",
        ),
        Step(
            "B4",
            "SHA-256 of UCSF-PDGM-metadata_v5.csv",
            "B",
            ("B3",),
            b("B4", _metadata_producer("B4"), describe="UCSF metadata hash"),
            gate="B4",
        ),
        Step(
            "B5",
            "Data manifest and hashes",
            "B",
            ("B4",),
            b("B5", produce_b5, describe="raw data manifest"),
            gate="B5",
        ),
        Step(
            "B6",
            "Counts from the hashed crosswalk (1,251 / 511 / 740)",
            "B",
            ("B5",),
            b("B6", produce_b6, describe="cohort counts", confirm="B6"),
            gate="B6",
        ),
        Step(
            "B7",
            "T_screen and pairwise WT-label screen",
            "B",
            ("B6",),
            b("B7", produce_b7, describe="T_screen and pairwise screen"),
            gate="B7",
            job="JOB-GROUPING",
        ),
        Step(
            "B8",
            "Manual review of flagged pairs (human)",
            "B",
            ("B7",),
            b("B8", produce_b8, describe="manual review record", confirm="B8"),
            gate="B8",
        ),
        Step(
            "B9",
            "Patient groups frozen (IDs only)",
            "B",
            ("B8",),
            b("B9", produce_b9, describe="frozen patient groups"),
            gate="B9",
        ),
        Step(
            "B10",
            "Final split created once (70/10/20, seed 20260927)",
            "B",
            ("B9",),
            b("B10", produce_b10, describe="final split", confirm="B10"),
            gate="B10",
        ),
        Step(
            "B11",
            "Split assertions pass",
            "B",
            ("B10",),
            b("B11", produce_b11, describe="split assertions"),
            gate="B11",
        ),
        Step(
            "B12",
            "Split hashes recorded",
            "B",
            ("B11",),
            b("B12", produce_b12, describe="split hashes"),
            gate="B12",
        ),
        Step(
            "PILOT",
            "EXP-001 compute pilot (measurements only)",
            "D",
            ("B6", "D1", "D2"),
            ss.execute_pilot,
            job="JOB-PILOT",
        ),
        Step(
            "D3",
            "Pilot restricted to site != 1 development cases",
            "D",
            ("PILOT",),
            _pilot_constraint("D3", "pilot restricted to site != 1 development cases"),
            gate="D3",
        ),
        Step(
            "D4",
            "Pilot computes no label-based scientific metrics",
            "D",
            ("PILOT",),
            _pilot_constraint("D4", "no label-based scientific metrics"),
            gate="D4",
        ),
        Step(
            "D5",
            "No site-1 or BraTS-Africa data in the pilot",
            "D",
            ("PILOT",),
            _pilot_constraint("D5", "no site-1 or BraTS-Africa data"),
            gate="D5",
        ),
        Step(
            "D6",
            "SR1/SR6/SR8 applied before main training",
            "D",
            ("D3", "D4", "D5"),
            ss.execute_d6,
            gate="D6",
        ),
    ]
    for job_id, run in (
        ("JOB-02", "A0"),
        ("JOB-03", "A1"),
        ("JOB-04", "A2"),
        ("JOB-05", "B0"),
        ("JOB-06", "B1"),
        ("JOB-07", "B2"),
    ):
        steps.append(
            Step(
                f"TRAIN-{run}",
                f"Main training arm {run[0]} seed {run[1]} ({job_id})",
                "train",
                ("B12", "D6"),
                training_executor(job_id),
                job=job_id,
            )
        )
    train = tuple(s.id for s in steps if s.id.startswith("TRAIN-"))
    steps += [
        Step(
            "VALIDATION",
            "Validation inference; SR2 (arm A full-input ET Dice >= 0.75)",
            "eval",
            train,
            ss.execute_validation,
            job="JOB-08",
        ),
        Step(
            "C5",
            "Validation-derived tau_q and I frozen",
            "C",
            ("VALIDATION",),
            ss.execute_c5,
            gate="C5",
        ),
        Step(
            "C4",
            "HOI patient grouping frozen",
            "C",
            ("B9",),
            ss.execute_c4,
            gate="C4",
            job="JOB-GROUPING",
        ),
        Step(
            "C1",
            "BraTS-Africa file-level label verification",
            "C",
            ("ENV",),
            ss.execute_c1,
            gate="C1",
        ),
        Step(
            "C2", "BraTS-Africa four-sequence verification", "C", ("C1",), ss.execute_c2, gate="C2"
        ),
        Step(
            "C3",
            "BraTS-Africa eligible count frozen (<= 95)",
            "C",
            ("C2",),
            ss.execute_c3,
            gate="C3",
        ),
        Step("C6", "Evaluation code tagged eval-v1", "C", ("C5",), ss.execute_c6, gate="C6"),
        Step(
            "INTERNAL_TEST",
            "Internal test evaluated once (eval-v1)",
            "eval",
            ("C5", "C6"),
            ss.evaluation_executor("internal_test"),
            job="JOB-08",
        ),
        Step(
            "EXTERNAL_HOI",
            "UPenn HOI evaluated once (eval-v1)",
            "eval",
            ("C4", "C5", "C6", "INTERNAL_TEST"),
            ss.evaluation_executor("upenn_hoi"),
            job="JOB-08",
        ),
        Step(
            "EXTERNAL_AFRICA",
            "BraTS-Africa evaluated once (eval-v1)",
            "eval",
            ("C1", "C2", "C3", "C5", "C6", "INTERNAL_TEST"),
            ss.evaluation_executor("brats_africa"),
            job="JOB-08",
        ),
        Step(
            "STATISTICS",
            "Pre-registered analyses, figures, tables (private; awaiting verification)",
            "report",
            ("INTERNAL_TEST", "EXTERNAL_HOI", "EXTERNAL_AFRICA"),
            ss.execute_statistics,
        ),
        Step(
            "VERIFY",
            "Independent result verification (publication only if VERIFIED)",
            "report",
            ("STATISTICS",),
            ss.execute_verify,
        ),
        Step(
            "WEBSITE",
            "Website build, rendered-value and public-export reconciliation",
            "report",
            ("VERIFY",),
            ss.execute_website,
        ),
        Step("FINAL_AUDIT", "Final research audit", "report", ("WEBSITE",), _execute_final_audit),
    ]
    return steps


def _execute_env(ctx: Context) -> Outcome:
    report = ctx.ops.preflight(None)
    facts = report.facts
    path = ctx.state_dir / "environment_latest.json"
    write_json(path, report.to_dict(), overwrite=True)
    if not facts["protocol"].get("verified"):
        raise StepFailed(
            f"frozen protocol not verified: {facts['protocol'].get('error')}",
            "restore docs/research/FINAL_RESEARCH_PROTOCOL_v1.0.md to the tagged bytes",
        )
    gpu = facts["gpu"]
    return Outcome(
        PASSED,
        f"{facts['environment']}: GPU {gpu.get('name') or 'none'}, status {report.status}",
        details={"status": report.status, "blockers": report.blockers, "limits": report.limits},
    )


def _execute_final_audit(ctx: Context) -> Outcome:
    from brats_uncertainty.orchestration.audit import write_final_audit

    path = write_final_audit(ctx)
    return Outcome(PASSED, "final research audit written", evidence=[ctx.rel(path)])


# --------------------------------------------------------------------------- real side effects
class RealOps:
    def __init__(
        self,
        repo_root: Path,
        cfg: Mapping[str, Any],
        *,
        commit: bool,
        push: bool,
        environ: Mapping[str, str],
        work_dir: Path,
        offline: bool,
    ) -> None:
        self.repo_root, self.cfg = repo_root, cfg
        self.commit_enabled, self.push_enabled = commit, push
        self.environ, self.work_dir, self.offline = environ, work_dir, offline
        self.commits: list[str] = []

    def gate_status(self, gid: str) -> str:
        from brats_uncertainty.evaluation.status import load_status

        return load_status(self.repo_root).gate(gid).status

    def transition(
        self, gid: str, new: str, *, evidence: str | None = None, on: str | None = None
    ) -> list[str]:
        from brats_uncertainty.evaluation.transitions import write_transition

        return write_transition(self.repo_root, gid, new, evidence=evidence, on=on, apply=True)

    def milestone(self, message: str) -> str | None:
        if not self.commit_enabled:
            return None
        from brats_uncertainty.orchestration import gitops
        from brats_uncertainty.results.site_export import export_site_data

        export_site_data(self.repo_root)  # website data always follows the sources of truth
        sha = gitops.commit_milestone(self.repo_root, message, self.cfg["git"])
        if sha:
            self.commits.append(sha)
            if self.push_enabled:
                gitops.push(self.repo_root, self.cfg["git"], self.environ)
        return sha

    def run(
        self, cmd: Sequence[str], *, cwd: Path | None = None, env: Mapping[str, str] | None = None
    ) -> int:
        import os
        import subprocess

        return subprocess.run(
            list(cmd), cwd=cwd, env={**os.environ, **(env or {})}, check=False
        ).returncode

    def preflight(self, job: str | None) -> Any:
        from brats_uncertainty.compute.probe import compute_preflight

        return compute_preflight(
            self.repo_root, work_dir=self.work_dir, job=job, offline=self.offline
        )

    def fetch(self, url: str, dest: Path) -> None:
        from brats_uncertainty.data.acquisition import fetch_official_file

        prefixes = tuple(
            read_yaml(self.repo_root / DATASET_CONFIG)["evidence_identity"][
                "official_source_prefixes"
            ]
        )
        try:
            fetch_official_file(url, dest, official_prefixes=prefixes)
        except OSError as exc:  # includes urllib.error.URLError
            raise StepBlocked(
                f"download of {url} failed: {exc}", "check internet access; re-run --resume"
            ) from exc


def compute_ready(ctx: Context, step: Step) -> Outcome | None:
    """BLOCKED outcome if this environment cannot run the step's job, else None."""
    if step.job is None:
        return None
    report = ctx.ops.preflight(step.job)
    if report.status == "NOT_READY":
        return Outcome(
            BLOCKED,
            f"compute environment not ready for {step.job}: {'; '.join(report.blockers)}",
            "run the master runner in an environment that meets "
            "configs/compute/remote_compute.yaml for this job (see the blockers); "
            "the preferred full-study environment is a private persistent GPU VM",
            details={"blockers": report.blockers, "limits": report.limits},
        )
    return None


__all__ = [
    "BLOCKED",
    "FAILED",
    "PASSED",
    "RUNNING",
    "Context",
    "RealOps",
    "Step",
    "build_steps",
    "compute_ready",
    "load_master_config",
    "run_guarded",
]
