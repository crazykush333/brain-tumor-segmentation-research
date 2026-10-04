"""Dataset layout schemas (file naming and case-ID patterns).

File-naming conventions are configuration (``configs/dataset/*.yaml``) and must
be verified against the actual release at acquisition (B2/B5, C1-C2).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from brats_uncertainty.errors import ConfigError
from brats_uncertainty.preprocessing.modalities import MODALITIES
from brats_uncertainty.utils.io import read_yaml


@dataclass(frozen=True)
class DatasetSchema:
    name: str
    case_id_pattern: str
    modality_suffixes: dict[str, str]  # protocol modality -> filename suffix
    label_suffix: str
    file_ending: str
    verified_on_files: bool

    def __post_init__(self) -> None:
        if set(self.modality_suffixes) != set(MODALITIES):
            raise ConfigError(f"{self.name}: modality_suffixes must cover exactly {MODALITIES}")
        re.compile(self.case_id_pattern)

    def is_valid_case_id(self, case_id: str) -> bool:
        return re.fullmatch(self.case_id_pattern, case_id) is not None

    def image_name(self, case_id: str, modality: str) -> str:
        return f"{case_id}{self.modality_suffixes[modality]}{self.file_ending}"

    def label_name(self, case_id: str) -> str:
        return f"{case_id}{self.label_suffix}{self.file_ending}"


def load_schema(path: str | Path) -> DatasetSchema:
    raw: dict[str, Any] = read_yaml(path)
    try:
        layout = raw["layout"]
        return DatasetSchema(
            name=str(raw["name"]),
            case_id_pattern=str(layout["case_id_pattern"]),
            modality_suffixes={str(k): str(v) for k, v in layout["modality_suffixes"].items()},
            label_suffix=str(layout["label_suffix"]),
            file_ending=str(layout["file_ending"]),
            verified_on_files=bool(layout.get("verified_on_files", False)),
        )
    except KeyError as exc:
        raise ConfigError(f"{path}: missing key {exc}") from exc
