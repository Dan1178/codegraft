"""Typed error hierarchy for codegraft.

Keeping a single base class makes it easy for the CLI to catch codegraft's own
errors and render them as clean messages, while letting unexpected exceptions
bubble up with a full traceback.
"""

from __future__ import annotations


class CodegraftError(Exception):
    """Base class for all expected, user-facing codegraft errors."""


class ConfigError(CodegraftError):
    """Raised when configuration is missing or invalid."""


class RepoError(CodegraftError):
    """Raised when a repository cannot be read or scanned."""


class ProviderError(CodegraftError):
    """Raised when an LLM provider fails or returns an unusable response."""


class PlanValidationError(CodegraftError):
    """Raised when a model response cannot be parsed into an ImplementationPlan."""
