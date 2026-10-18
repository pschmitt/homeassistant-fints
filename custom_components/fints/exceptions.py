"""Exceptions for the FinTS integration."""

from __future__ import annotations


class FinTSIntegrationError(Exception):
    """Base exception for the FinTS integration."""


class FinTSAuthError(FinTSIntegrationError):
    """Raised when authentication fails (wrong PIN or stale web session)."""


class FinTSIngReauthRequiredError(FinTSAuthError):
    """Raised when ING requires a fresh online banking login."""


class FinTSConnectionError(FinTSIntegrationError):
    """Raised when a network or protocol error occurs."""


class FinTSTanRequiredError(FinTSIntegrationError):
    """Raised when the bank requires an interactive TAN/SCA step."""

    def __init__(self, message: str, challenge_data: dict[str, str] | None = None) -> None:
        """Initialize with resumable FinTS challenge state, when available."""
        super().__init__(message)
        self.challenge_data = challenge_data
