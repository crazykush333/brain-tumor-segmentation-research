"""Parse the TCIA BraTS 2021 crosswalk and derive the cohorts (§5, gate B6).

The crosswalk ``BraTS2021_MappingToTCIA.xlsx`` is licensed metadata and is never
committed. Its SHA-256 is recorded at gate B3. Column names are configuration
(``configs/dataset/brats2021.yaml``) and must be confirmed against the hashed
file at B3/B6.

Cohort rule: held-out institution = Site ID == "1" (all 511 UPenn-origin
cases); development = Site ID != "1" (740 cases). Selection is by site ID, never
by collection name. Count mismatches raise (SR3).
"""

from __future__ import annotations

import csv
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from brats_uncertainty.errors import DataValidationError

PLACEHOLDER_TCIA_ID = "new-not-previously-in-TCIA"


@dataclass(frozen=True)
class CrosswalkRow:
    case_id: str
    site_id: str
    collection: str
    tcia_subject_id: str | None

    @property
    def has_real_tcia_id(self) -> bool:
        return bool(self.tcia_subject_id) and self.tcia_subject_id != PLACEHOLDER_TCIA_ID


def _norm_site(value: Any) -> str:
    if value is None:
        raise DataValidationError("missing site ID")
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    s = str(value).strip()
    if not s:
        raise DataValidationError("missing site ID")
    if re.fullmatch(r"\d+\.0+", s):
        s = s.split(".")[0]
    return s


REQUIRED_COLUMN_KEYS = ("case_id", "site_id", "collection", "tcia_subject_id")
CROSSWALK_CONFIG_NAME = "brats2021_crosswalk.yaml"


def crosswalk_config_files(dataset_config: str | Path) -> list[Path]:
    """The dataset config plus the confirmed crosswalk mapping next to it (if present)."""
    base = Path(dataset_config)
    override = base.with_name(CROSSWALK_CONFIG_NAME)
    return [base, override] if override.is_file() else [base]


def load_crosswalk_config(dataset_config: str | Path) -> dict[str, Any]:
    """``crosswalk`` section of the dataset config, overlaid by the confirmed mapping."""
    from brats_uncertainty.utils.io import read_yaml

    files = crosswalk_config_files(dataset_config)
    cfg = dict(read_yaml(files[0])["crosswalk"])
    if len(files) == 2:
        confirmed = read_yaml(files[1]) or {}
        cfg["columns"] = {**cfg.get("columns", {}), **confirmed.get("columns", {})}
        cfg.update({k: v for k, v in confirmed.items() if k != "columns"})
    return cfg


def select_cohort(
    records: Iterable[Mapping[str, Any]], crosswalk_cfg: Mapping[str, Any]
) -> list[Mapping[str, Any]]:
    """Keep the study population (protocol section 5: the BraTS 2021 training set).

    The official crosswalk also lists validation and unassigned cases. When
    ``cohort_column`` is configured, only rows whose value equals ``cohort_value``
    are kept; a missing column fails closed.
    """
    records = list(records)
    column = crosswalk_cfg.get("cohort_column")
    if not column:
        return records
    value = str(crosswalk_cfg["cohort_value"])
    if records and not any(column in r for r in records):
        raise DataValidationError(f"crosswalk is missing the cohort column {column!r}")
    return [r for r in records if str(r.get(column) or "").strip() == value]


def parse_rows(
    records: Iterable[Mapping[str, Any]],
    columns: Mapping[str, str],
    *,
    case_id_pattern: str | None = None,
) -> list[CrosswalkRow]:
    """Convert raw records (dicts keyed by spreadsheet header) to typed rows.

    Malformed metadata fails loudly: missing configured columns, missing site
    IDs, case IDs not matching ``case_id_pattern`` and duplicate case IDs.
    """
    missing_keys = [k for k in REQUIRED_COLUMN_KEYS if not columns.get(k)]
    if missing_keys:
        raise DataValidationError(f"crosswalk column mapping incomplete: {missing_keys}")
    records = list(records)
    if not records:
        raise DataValidationError("crosswalk contains no records")
    header = set().union(*(r.keys() for r in records))
    absent = sorted(columns[k] for k in REQUIRED_COLUMN_KEYS if columns[k] not in header)
    if absent:
        raise DataValidationError(f"crosswalk is missing expected columns: {absent}")
    pattern = re.compile(case_id_pattern) if case_id_pattern else None
    rows: list[CrosswalkRow] = []
    for rec in records:
        case = rec.get(columns["case_id"])
        if case is None or str(case).strip() == "":
            continue  # blank spreadsheet row
        if pattern and not pattern.fullmatch(str(case).strip()):
            raise DataValidationError(f"malformed case ID in crosswalk: {str(case)!r}")
        tcia = rec.get(columns["tcia_subject_id"])
        rows.append(
            CrosswalkRow(
                case_id=str(case).strip(),
                site_id=_norm_site(rec.get(columns["site_id"])),
                collection=str(rec.get(columns["collection"], "")).strip(),
                tcia_subject_id=str(tcia).strip() if tcia is not None else None,
            )
        )
    ids = [r.case_id for r in rows]
    if len(ids) != len(set(ids)):
        raise DataValidationError("duplicate case IDs in crosswalk")
    return rows


def read_table_records(path: str | Path, sheet: str | None = None) -> list[dict[str, Any]]:
    """Read ``.xlsx`` (requires the ``io`` extra) or ``.csv`` into header-keyed dicts."""
    p = Path(path)
    if not p.is_file():
        raise DataValidationError(f"metadata file not found: {p}")
    if p.suffix.lower() == ".csv":
        with p.open(encoding="utf-8-sig", newline="") as fh:
            return [dict(r) for r in csv.DictReader(fh)]
    if p.suffix.lower() == ".xlsx":
        return read_xlsx_records(p, sheet)
    raise DataValidationError(f"unsupported metadata format: {p.suffix}")


def read_xlsx_records(path: str | Path, sheet: str | None = None) -> list[dict[str, Any]]:
    """Read a spreadsheet into header-keyed dicts (requires the ``io`` extra)."""
    try:
        import openpyxl
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "install the optional extra: pip install 'brats-uncertainty[io]'"
        ) from exc
    wb = openpyxl.load_workbook(Path(path), read_only=True, data_only=True)
    ws = wb[sheet] if sheet else wb.worksheets[0]
    it = ws.iter_rows(values_only=True)
    header = [str(h).strip() if h is not None else "" for h in next(it)]
    return [dict(zip(header, row, strict=False)) for row in it]


@dataclass(frozen=True)
class Cohorts:
    development: tuple[CrosswalkRow, ...]
    held_out_institution: tuple[CrosswalkRow, ...]


def derive_cohorts(
    rows: Iterable[CrosswalkRow],
    *,
    hoi_site_id: str,
    expected_total: int,
    expected_hoi: int,
    expected_development: int,
) -> Cohorts:
    """Split by site ID and assert the frozen counts (1,251 / 511 / 740)."""
    rows = list(rows)
    hoi = tuple(r for r in rows if r.site_id == hoi_site_id)
    dev = tuple(r for r in rows if r.site_id != hoi_site_id)
    problems = []
    if len(rows) != expected_total:
        problems.append(f"total {len(rows)} != {expected_total}")
    if len(hoi) != expected_hoi:
        problems.append(f"held-out institution {len(hoi)} != {expected_hoi}")
    if len(dev) != expected_development:
        problems.append(f"development {len(dev)} != {expected_development}")
    if problems:
        raise DataValidationError(
            "crosswalk counts do not match the frozen protocol (SR3 applies): "
            + "; ".join(problems)
        )
    return Cohorts(development=dev, held_out_institution=hoi)


def shared_tcia_id_groups(rows: Iterable[CrosswalkRow]) -> list[list[str]]:
    """Case-ID sets sharing a real (non-placeholder) TCIA subject ID (§6.1)."""
    by_id: dict[str, list[str]] = {}
    for r in rows:
        if r.has_real_tcia_id and r.tcia_subject_id is not None:
            by_id.setdefault(r.tcia_subject_id, []).append(r.case_id)
    return sorted(sorted(v) for v in by_id.values() if len(v) > 1)
