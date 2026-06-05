"""FinTS API client wrapper."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

from .exceptions import FinTSAuthError, FinTSConnectionError

_LOGGER = logging.getLogger(__name__)


@dataclass
class FinTSAccountData:
    """Represents one bank account with its current balance."""

    iban: str
    bic: str
    account_number: str
    balance: Decimal
    currency: str

    @property
    def iban_formatted(self) -> str:
        """Return IBAN with spaces every 4 characters."""
        return " ".join(self.iban[i : i + 4] for i in range(0, len(self.iban), 4))

    @property
    def iban_masked(self) -> str:
        """Return IBAN with middle digits masked."""
        if len(self.iban) < 8:
            return self.iban
        return f"{self.iban[:4]} **** **** {self.iban[-4:]}"


class FinTSApiClient:
    """Synchronous wrapper around python-fints. All public methods are blocking."""

    def __init__(
        self,
        blz: str,
        username: str,
        pin: str,
        endpoint: str,
        product_id: str,
    ) -> None:
        """Initialize the client."""
        self._blz = blz
        self._username = username
        self._pin = pin
        self._endpoint = endpoint
        self._product_id = product_id

    def _make_client(self):
        """Create and bootstrap a FinTS client."""
        from fints.client import FinTS3PinTanClient
        from fints.utils import minimal_interactive_cli_bootstrap

        client = FinTS3PinTanClient(
            self._blz,
            self._username,
            self._pin,
            self._endpoint,
            product_id=self._product_id,
        )
        minimal_interactive_cli_bootstrap(client)
        return client

    def fetch_accounts_and_balances(self) -> dict[str, FinTSAccountData]:
        """Fetch all SEPA accounts and their current balances.

        Blocking — must be called from an executor.
        Returns a dict keyed by IBAN.
        """
        try:
            client = self._make_client()
            with client:
                accounts = client.get_sepa_accounts()
                result: dict[str, FinTSAccountData] = {}
                for acc in accounts:
                    try:
                        balance = client.get_balance(acc)
                        result[acc.iban] = FinTSAccountData(
                            iban=acc.iban,
                            bic=acc.bic or "",
                            account_number=acc.accountnumber or "",
                            balance=balance.amount.amount,
                            currency=balance.amount.currency,
                        )
                    except Exception as exc:
                        _LOGGER.warning(
                            "Failed to get balance for %s: %s", acc.iban, exc
                        )
                return result
        except Exception as exc:
            from fints.exceptions import FinTSClientPINError

            if isinstance(exc, FinTSClientPINError):
                raise FinTSAuthError(str(exc)) from exc
            raise FinTSConnectionError(str(exc)) from exc

    def validate(self) -> dict[str, FinTSAccountData]:
        """Validate credentials by fetching accounts. Returns the same as fetch."""
        return self.fetch_accounts_and_balances()
