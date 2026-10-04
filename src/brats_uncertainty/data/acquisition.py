"""Gate B2 acquisition layer: approved source -> acquisition -> recorded inventory.

Workflow (after B1 has PASSED and B2 is AUTHORIZED)::

    approved source -> acquisition (adapter) -> integrity verification (validate-data)
                    -> manifest (B5) -> count verification (B6)

Safety model:

- **Dry run is the default.** ``stage_acquire(..., execute=False)`` only returns
  the plan. It downloads, copies and writes nothing.
- **Real acquisition fails closed.** ``execute=True`` with a real adapter needs
  every one of: gate B1 PASSED, B2 AUTHORIZED/RUNNING, ``data.authorization:
  APPROVED`` and the adapter's route equal to ``data.approved_route``.
  Otherwise it raises ``ResearchGateError``: "Real-data acquisition is locked
  because B1 data-route authorization has not been recorded." Nothing is
  inferred from URLs, public downloadability, documentation or platform access.
- **No bypass flag exists.** The only exception is ``SyntheticFixtureAdapter``,
  which *generates* SYNTHETIC_TEST_DATA outside the repository. It cannot
  fetch or copy anything, and its records carry ``synthetic: true``.
- URLs are logged and recorded with credentials and query strings removed.
  Adapters never accept credentials: authenticated routes (e.g. Aspera or
  Synapse) are run by the operator, and ``LocalImportAdapter`` then imports the
  delivered files.
"""

from __future__ import annotations

import shutil
import urllib.request
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO
from urllib.parse import urlsplit, urlunsplit

from brats_uncertainty.data.preflight import GIB, require_free_space
from brats_uncertainty.data.records import (
    AcquisitionRecord,
    Clock,
    SourceInfo,
    inventory,
    make_stamp,
    utc_now,
    write_record,
)
from brats_uncertainty.data.synthetic import (
    MARKER_NAME,
    SYNTHETIC_ROUTE,
    SyntheticDataset,
    find_marker_root,
    generate_synthetic_dataset,
    require_synthetic,
)
from brats_uncertainty.errors import (
    ConfigError,
    DataValidationError,
    ProvenanceError,
    ResearchGateError,
)
from brats_uncertainty.evaluation.guards import ACQUISITION_LOCKED_MESSAGE, require_action
from brats_uncertainty.evaluation.status import load_status
from brats_uncertainty.utils.logging import get_logger, log_event
from brats_uncertainty.utils.paths import is_link, is_safe_relpath, is_within

_LOG = get_logger("acquisition")
_CHUNK = 1 << 20
IMPORT_RESERVE_BYTES = 1 * GIB  # free space that must remain after a local-import copy


def redact_url(url: str) -> str:
    """Remove user-info, query string and fragment (may contain tokens) from a URL."""
    parts = urlsplit(url)
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    return urlunsplit((parts.scheme, host, parts.path, "", ""))


@dataclass(frozen=True)
class PlannedItem:
    relpath: str  # destination path relative to the storage root
    origin: str  # redacted URL or a description of the local origin


@dataclass(frozen=True)
class AcquisitionPlan:
    adapter: str
    source: SourceInfo
    synthetic: bool
    items: tuple[PlannedItem, ...]
    notes: tuple[str, ...] = field(default_factory=tuple)

    def describe(self) -> str:
        lines = [
            f"DRY RUN - adapter={self.adapter} synthetic={self.synthetic}",
            f"source: {self.source.dataset} {self.source.dataset_version} doi={self.source.doi}",
            f"route: {self.source.route}",
            *(f"  {i.relpath} <- {i.origin}" for i in self.items),
            *self.notes,
        ]
        return "\n".join(lines)


class AcquisitionAdapter(ABC):
    name: str = "abstract"
    synthetic: bool = False

    def __init__(self, source: SourceInfo) -> None:
        self.source = source

    @abstractmethod
    def plan(self) -> AcquisitionPlan: ...

    def execute(self, storage_root: Path, *, repo_root: Path) -> None:
        """Materialize the planned files under ``storage_root``.

        Real adapters re-check the B1/B2 authorization HERE, so calling ``execute``
        directly (outside ``stage_acquire``) cannot bypass the research gate.
        """
        if not self.synthetic:
            assert_real_acquisition_authorized(repo_root, self)
        self._materialize(storage_root)

    @abstractmethod
    def _materialize(self, storage_root: Path) -> None:
        """Adapter-specific transfer; never call directly (use ``execute``/``stage_acquire``)."""


class LocalImportAdapter(AcquisitionAdapter):
    """Import files that the operator obtained through the approved route.

    For example, files delivered by the TCIA Aspera download or the Synapse
    client, run by the operator with their own credentials. Files are copied
    byte-for-byte into the git-ignored storage root.
    """

    name = "local-import"

    def __init__(self, source: SourceInfo, delivered: Path) -> None:
        super().__init__(source)
        self.delivered = Path(delivered)

    def _files(self) -> list[Path]:
        if is_link(self.delivered) or not self.delivered.exists():
            raise DataValidationError(f"delivered path not found or a link: {self.delivered.name}")
        if self.delivered.is_file():
            return [self.delivered]
        found = sorted(self.delivered.rglob("*"))
        links = [p.name for p in found if is_link(p)]
        if links:
            raise DataValidationError(
                f"symbolic links in the delivered tree are refused: {links[:3]}"
            )
        return [p for p in found if p.is_file()]

    def _rel(self, p: Path) -> str:
        return p.name if self.delivered.is_file() else p.relative_to(self.delivered).as_posix()

    def required_bytes(self) -> int:
        return sum(p.stat().st_size for p in self._files())

    def plan(self) -> AcquisitionPlan:
        files = self._files()
        items = tuple(PlannedItem(self._rel(p), "operator-delivered local file") for p in files)
        total = sum(p.stat().st_size for p in files)
        notes = (
            f"{len(files)} files, {total} bytes; copied byte-for-byte with their relative "
            "paths (official hierarchy preserved, nothing flattened or renamed)",
        )
        return AcquisitionPlan(self.name, self.source, False, items, notes)

    def _materialize(self, storage_root: Path) -> None:
        # fail closed before copying anything if the storage drive is too small
        require_free_space(storage_root, self.required_bytes(), reserve_bytes=IMPORT_RESERVE_BYTES)
        for p in self._files():
            dest = storage_root / self._rel(p)
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                raise FileExistsError(f"refusing to overwrite {dest.name}")
            tmp = dest.with_name(dest.name + ".part")
            shutil.copyfile(p, tmp)
            tmp.replace(dest)  # no partially copied files under their final name


Opener = Callable[[str], IO[bytes]]


def _https_open(url: str) -> IO[bytes]:  # pragma: no cover - real network, never used in tests
    return urllib.request.urlopen(url, timeout=120)


def fetch_official_file(
    url: str,
    dest: Path,
    *,
    official_prefixes: tuple[str, ...],
    opener: Opener = _https_open,
) -> Path:
    """Byte-for-byte download of one official public file into the B2 delivery folder.

    Used for the two B3/B4 metadata files (B2 runbook §1), which travel with the
    official delivery into the gated B2 import. Only HTTPS URLs under an official
    source prefix (dataset ``evidence_identity``) are accepted, never credentials;
    an existing file is never overwritten and the bytes are not altered.
    """
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.username or parts.password:
        raise ProvenanceError("only plain https URLs (no credentials) are allowed")
    if not any(url.startswith(p) for p in official_prefixes):
        raise ProvenanceError(f"{redact_url(url)} is not under an official source prefix")
    if dest.exists():
        raise FileExistsError(f"refusing to overwrite {dest.name}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    log_event(_LOG, "download", url=redact_url(url), dest=dest.name)
    tmp = dest.with_name(dest.name + ".part")
    try:
        with opener(url) as resp, tmp.open("wb") as fh:
            while chunk := resp.read(_CHUNK):
                fh.write(chunk)
        tmp.replace(dest)
    finally:
        if tmp.exists():
            tmp.unlink()
    return dest


class HttpsFileAdapter(AcquisitionAdapter):
    """Download individual public HTTPS files from an official source page.

    Intended only for small official files (e.g. a metadata CSV). It accepts no
    credentials and refuses non-HTTPS URLs and URLs that carry credentials.
    """

    name = "https-file"

    def __init__(
        self, source: SourceInfo, urls: dict[str, str], opener: Opener = _https_open
    ) -> None:
        super().__init__(source)
        for rel, url in urls.items():
            parts = urlsplit(url)
            if parts.scheme != "https":
                raise ProvenanceError(f"{rel}: only https URLs are allowed")
            if parts.username or parts.password:
                raise ProvenanceError(f"{rel}: URLs with embedded credentials are refused")
            if not is_safe_relpath(rel):
                raise ProvenanceError(f"{rel}: destination must be a safe relative path")
        self.urls = dict(urls)
        self.opener = opener

    def plan(self) -> AcquisitionPlan:
        items = tuple(PlannedItem(rel, redact_url(u)) for rel, u in sorted(self.urls.items()))
        return AcquisitionPlan(self.name, self.source, False, items)

    def _materialize(self, storage_root: Path) -> None:
        for rel, url in sorted(self.urls.items()):
            dest = storage_root / rel
            if dest.exists():
                raise FileExistsError(f"refusing to overwrite {rel}")
            dest.parent.mkdir(parents=True, exist_ok=True)
            log_event(_LOG, "download", url=redact_url(url), dest=rel)
            tmp = dest.with_suffix(dest.suffix + ".part")
            with self.opener(url) as resp, tmp.open("wb") as fh:
                while chunk := resp.read(_CHUNK):
                    fh.write(chunk)
            tmp.replace(dest)


class SyntheticFixtureAdapter(AcquisitionAdapter):
    """Generate a SYNTHETIC_TEST_DATA tree. Cannot fetch or copy real data."""

    name = "synthetic-fixture"
    synthetic = True

    def __init__(
        self,
        repo_root: Path,
        n_cases: int = 3,
        crosswalk_counts: tuple[int, int] = (2, 1),
        collections: tuple[str, ...] | None = None,
    ) -> None:
        super().__init__(
            SourceInfo(
                dataset="SYNTHETIC_TEST_DATA",
                dataset_version="generated",
                doi="10.0000/SYNTHETIC_TEST_DATA",
                source_url="https://synthetic.invalid/SYNTHETIC_TEST_DATA",
                route=SYNTHETIC_ROUTE,
            )
        )
        self.repo_root = repo_root
        self.n_cases = n_cases
        self.crosswalk_counts = crosswalk_counts
        self.collections = collections
        self.generated: SyntheticDataset | None = None

    def plan(self) -> AcquisitionPlan:
        items = (
            PlannedItem("images/", f"{self.n_cases} generated synthetic cases"),
            PlannedItem("metadata/", "generated synthetic metadata files"),
        )
        return AcquisitionPlan(
            self.name, self.source, True, items, ("SYNTHETIC_TEST_DATA - not BraTS",)
        )

    def _materialize(self, storage_root: Path) -> None:
        self.generated = generate_synthetic_dataset(
            storage_root,
            repo_root=self.repo_root,
            n_cases=self.n_cases,
            crosswalk_counts=self.crosswalk_counts,
            collections=self.collections,
        )


def _storage_label(storage_root: Path, repo_root: Path, label: str | None) -> str:
    if label:
        return label
    if is_within(storage_root, repo_root):
        return storage_root.resolve().relative_to(repo_root.resolve()).as_posix()
    raise ProvenanceError(
        "storage outside the repository needs a logical --storage-label "
        "(absolute paths are never recorded)"
    )


def assert_real_acquisition_authorized(repo_root: Path, adapter: AcquisitionAdapter) -> None:
    """Fail closed unless B1 PASSED, B2 runnable, authorization APPROVED and route matches."""
    try:
        require_action("acquire_data", repo_root)  # raises with ACQUISITION_LOCKED_MESSAGE
        data = load_status(repo_root).raw["data"]
    except ConfigError as exc:  # invalid status or evidence (e.g. synthetic B1): fail closed
        raise ResearchGateError(f"{ACQUISITION_LOCKED_MESSAGE} {exc}") from exc
    if data.get("authorization") != "APPROVED" or not data.get("approved_route"):
        raise ResearchGateError(ACQUISITION_LOCKED_MESSAGE)
    if adapter.source.route != data["approved_route"]:
        raise ResearchGateError(
            f"adapter route {adapter.source.route!r} is not the "
            f"B1-approved route {data['approved_route']!r}"
        )


def stage_acquire(
    repo_root: Path,
    adapter: AcquisitionAdapter,
    *,
    storage_root: Path,
    out_record: Path,
    acquired_by: str,
    execute: bool = False,
    storage_label: str | None = None,
    require_clean_commit: bool = True,
    clock: Clock = utc_now,
) -> AcquisitionPlan | AcquisitionRecord:
    """Gate B2. Dry run (default) returns the plan; ``execute=True`` acquires and records."""
    plan = adapter.plan()
    if not execute:
        log_event(_LOG, "dry-run", adapter=adapter.name, items=len(plan.items))
        return plan
    if adapter.synthetic:
        if is_within(storage_root, repo_root) or is_within(out_record, repo_root):
            raise ProvenanceError("synthetic acquisition must write outside the repository")
    else:
        if clock is not utc_now:
            raise ProvenanceError("a custom clock is only allowed for SYNTHETIC_TEST_DATA runs")
        assert_real_acquisition_authorized(repo_root, adapter)
        if is_link(storage_root):
            raise ProvenanceError("storage root may not be a link")
        if isinstance(adapter, LocalImportAdapter) and (
            find_marker_root(adapter.delivered) is not None
            or any(p.name == MARKER_NAME for p in adapter._files())
        ):
            raise ProvenanceError(
                "SYNTHETIC_TEST_DATA cannot be acquired through a real-data adapter"
            )
        if is_within(storage_root, repo_root) and not is_within(storage_root, repo_root / "data"):
            raise ProvenanceError(
                "real data inside the repository may only be stored under the "
                "git-ignored data/ tree"
            )
        if storage_root.exists() and any(storage_root.iterdir()):
            raise FileExistsError(
                "storage root is not empty; acquisition writes into a fresh location"
            )
    if adapter.synthetic:
        label = storage_label or "SYNTHETIC_TEST_DATA (temporary, outside repository)"
    else:
        label = _storage_label(storage_root, repo_root, storage_label)
        storage_root.mkdir(parents=True, exist_ok=True)
    adapter.execute(storage_root, repo_root=repo_root)
    if adapter.synthetic:
        require_synthetic([storage_root], repo_root)
    inv = inventory(storage_root)
    if not adapter.synthetic and any(Path(e.relpath).name == MARKER_NAME for e in inv):
        raise ProvenanceError("a SYNTHETIC_TEST_DATA marker appeared in real storage")
    record = AcquisitionRecord(
        gate="B2",
        synthetic=adapter.synthetic,
        source=adapter.source,
        adapter=adapter.name,
        acquired_at=clock().isoformat(),
        acquired_by=acquired_by,
        storage_location=label,
        inventory=inv,
        stamp=make_stamp(
            repo_root,
            require_clean_commit=require_clean_commit and not adapter.synthetic,
            clock=clock,
        ),
    )
    write_record(out_record, record)
    return record
