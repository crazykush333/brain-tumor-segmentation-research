"""T_screen: computed once, at gate B7, from the two verified positive-control pairs.

Frozen rule (§6.2): T_screen = min(WT-Dice(A), WT-Dice(B)) with
A = BraTS2021_00626 + BraTS2021_00758 and B = BraTS2021_00639 + BraTS2021_00557.
The value is never set by hand: a ``TScreenRecord`` can only be validated if its
value equals the minimum of its recorded positive-control Dice values, and the
screen accepts only a validated record.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from brats_uncertainty.errors import ProtocolDeviationError
from brats_uncertainty.grouping.similarity import MaskIndex, ScreenResult, pairwise_screen, wt_dice

PROTOCOL_POSITIVE_CONTROLS: dict[str, tuple[str, str]] = {
    "A": ("BraTS2021_00626", "BraTS2021_00758"),
    "B": ("BraTS2021_00639", "BraTS2021_00557"),
}


@dataclass(frozen=True)
class TScreenRecord:
    value: float
    control_dice: dict[str, float]
    control_pairs: dict[str, tuple[str, str]]
    label_sha256: dict[str, str]
    computed_at: str
    rule: str = "min WT-label Dice over verified positive-control pairs A and B (protocol §6.2)"

    def validate(
        self, controls: Mapping[str, tuple[str, str]] = PROTOCOL_POSITIVE_CONTROLS
    ) -> None:
        if {k: tuple(v) for k, v in self.control_pairs.items()} != dict(controls):
            raise ProtocolDeviationError(
                "T_screen record does not use the protocol positive-control pairs"
            )
        if set(self.control_dice) != set(controls):
            raise ProtocolDeviationError("T_screen record lacks a positive-control Dice value")
        if self.value != min(self.control_dice.values()):
            raise ProtocolDeviationError("T_screen value is not the minimum positive-control Dice")
        needed = {c for pair in controls.values() for c in pair}
        if set(self.label_sha256) != needed:
            raise ProtocolDeviationError(
                "T_screen record must hash the four positive-control label files"
            )

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)


def compute_t_screen(
    masks: Mapping[str, MaskIndex],
    label_sha256: Mapping[str, str],
    controls: Mapping[str, tuple[str, str]] = PROTOCOL_POSITIVE_CONTROLS,
) -> TScreenRecord:
    """Compute T_screen from the positive-control WT masks only."""
    control_dice: dict[str, float] = {}
    for name, (a, b) in controls.items():
        if a not in masks or b not in masks:
            raise ProtocolDeviationError(f"positive-control case missing for pair {name}: {a}, {b}")
        control_dice[name] = wt_dice(masks[a], masks[b])
    value = min(control_dice.values())
    if value <= 0.0:
        raise ProtocolDeviationError(
            "positive-control WT Dice is 0; T_screen would flag every pair. "
            "Stop and consult the owner."
        )
    needed = {c for pair in controls.values() for c in pair}
    record = TScreenRecord(
        value=value,
        control_dice=control_dice,
        control_pairs={k: (v[0], v[1]) for k, v in controls.items()},
        label_sha256={c: label_sha256[c] for c in sorted(needed)},
        computed_at=datetime.now(UTC).isoformat(),
    )
    record.validate(controls)
    return record


def run_screen(
    masks: Mapping[str, MaskIndex],
    record: TScreenRecord,
    controls: Mapping[str, tuple[str, str]] = PROTOCOL_POSITIVE_CONTROLS,
) -> ScreenResult:
    """Run the pairwise screen with a validated T_screen record.

    Asserts the construction property that both positive-control pairs are flagged.
    """
    record.validate(controls)
    result = pairwise_screen(masks, record.value)
    flagged = {p.key for p in result.flagged}
    for name, (a, b) in controls.items():
        key = (a, b) if a < b else (b, a)
        if key not in flagged:
            raise ProtocolDeviationError(f"positive-control pair {name} was not flagged")
    return result
