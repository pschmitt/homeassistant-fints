"""Exceptions for the FinTS integration."""

from __future__ import annotations


class FinTSIntegrationError(Exception):
    """Base exception for the FinTS integration."""


class FinTSAuthError(FinTSIntegrationError):
    """Raised when authentication fails (wrong PIN or stale web session)."""


class FinTSConnectionError(FinTSIntegrationError):
    """Raised when a network or protocol error occurs."""


class FinTSTanRequiredError(FinTSIntegrationError):
    """Raised when the bank requires an interactive TAN/SCA step."""
