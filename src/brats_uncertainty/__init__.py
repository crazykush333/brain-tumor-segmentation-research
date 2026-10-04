"""Research software for the frozen protocol v1.0.

Pre-registered evaluation of case-level reliability of glioma segmentation under
missing MRI sequences. The authoritative scientific definition is
``docs/research/FINAL_RESEARCH_PROTOCOL_v1.0.md`` (git tag ``protocol-v1.0``).

This package contains software infrastructure only. It ships no data, no model
weights and no scientific results.
"""

from __future__ import annotations

__all__ = ["PROTOCOL_VERSION", "__version__"]

__version__ = "0.1.0"
PROTOCOL_VERSION = "v1.0"
