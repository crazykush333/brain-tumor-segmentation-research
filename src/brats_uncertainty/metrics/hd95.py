"""HD95 placeholder (§4 S3).

The protocol states that HD95 uses the BraTS evaluation convention implemented
by the exact evaluation code pinned at gate C6, and that empty-mask behaviour
is verified before ``eval-v1`` is tagged. No numerical convention is stated, so
none is invented here.
"""

from __future__ import annotations

from typing import Any


def hd95(*_args: Any, **_kwargs: Any) -> float:
    raise NotImplementedError(
        "HD95 must use the BraTS evaluation code pinned at gate C6 (protocol §4 S3). "
        "Pin and wrap that evaluator before eval-v1; do not implement an ad-hoc convention."
    )
