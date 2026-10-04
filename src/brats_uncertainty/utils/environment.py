"""Capture the software/hardware environment for provenance records."""

from __future__ import annotations

import importlib
import platform
import sys
from typing import Any

_PACKAGES = ("numpy", "scipy", "yaml", "matplotlib", "nibabel", "torch", "nnunetv2")


def _version(module: str) -> str | None:
    try:
        mod = importlib.import_module(module)
    except Exception:  # optional dependency absent or broken
        return None
    return str(getattr(mod, "__version__", "unknown"))


def capture_environment() -> dict[str, Any]:
    """Return a JSON-serialisable description of the running environment.

    Only reports what is actually observed. GPU fields are filled only if torch
    is importable and reports a device.
    """
    env: dict[str, Any] = {
        "python": sys.version.split()[0],
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "packages": {name: _version(name) for name in _PACKAGES},
        "cuda_available": None,
        "gpu": None,
    }
    try:
        torch = importlib.import_module("torch")
        env["cuda_available"] = bool(torch.cuda.is_available())
        if env["cuda_available"]:
            env["gpu"] = torch.cuda.get_device_name(0)
            env["cuda_version"] = torch.version.cuda
    except Exception:  # torch not installed: leave as None
        pass
    return env
