"""src/errors.py — Shared exception types and error utilities for the data pipeline."""

from __future__ import annotations

import re


def _snake_case(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _build_error_payload(stage: str, exc: Exception, **context) -> dict:
    payload = {
        "type": _snake_case(exc.__class__.__name__),
        "exception": exc.__class__.__name__,
        "stage": stage,
        "message": str(exc),
    }
    payload.update({k: v for k, v in context.items() if v is not None})
    return payload


class PipelineError(Exception):
    """Base class for pipeline-related failures."""


class DataFetchError(PipelineError):
    """Raised when an external market/news fetch fails after retries."""


class StorageError(PipelineError):
    """Raised when stored snapshot data cannot be read safely."""


class SignalComputationError(PipelineError):
    """Raised when signal derivation cannot be completed."""
