"""Exception hierarchy. Research-gate violations must fail loudly."""

from __future__ import annotations


class BratsUncertaintyError(Exception):
    """Base class for all package errors."""


class ProtocolIntegrityError(BratsUncertaintyError):
    """The frozen protocol file or its machine-readable mirror is inconsistent."""


class ProtocolDeviationError(BratsUncertaintyError):
    """A configuration or call would deviate from the frozen protocol."""


class ResearchGateError(BratsUncertaintyError):
    """An action was attempted before its protocol gate was legitimately passed."""


class DataValidationError(BratsUncertaintyError):
    """Input data (manifests, labels, metadata) failed validation."""


class ProvenanceError(BratsUncertaintyError):
    """Provenance information is missing or inconsistent."""


class ConfigError(BratsUncertaintyError):
    """A configuration file is malformed or incomplete."""
