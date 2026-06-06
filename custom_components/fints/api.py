"""FinTS API client wrapper."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from .exceptions import FinTSAuthError, FinTSConnectionError

_LOGGER = logging.getLogger(__name__)

_TRANSACTION_LOOKBACK_DAYS = 30


@dataclass
class FinTSAccountData:
    """Represents one bank account with its current balance."""

    iban: str
    bic: str
    account_number: str
    balance: Decimal
    currency: str
    product_name: str = ""
    transactions: list[dict[str, Any]] = field(default_factory=list)

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


def _serialize_transaction(txn: Any) -> dict[str, Any]:
    """Convert an mt940/fints Transaction object to a JSON-serializable dict."""
    data: dict[str, Any] = txn.data if hasattr(txn, "data") else {}

    amount_obj = data.get("amount")
    if amount_obj is not None:
        amount_val = float(getattr(amount_obj, "amount", 0) or 0)
        currency = str(getattr(amount_obj, "currency", "") or "")
        status = str(data.get("status") or "C")
        if status.startswith("D"):
            amount_val = -abs(amount_val)
    else:
        amount_val = 0.0
        currency = ""

    date_val = data.get("date")
    date_str = date_val.isoformat() if hasattr(date_val, "isoformat") else str(date_val or "")

    return {
        "date": date_str,
        "amount": round(amount_val, 2),
        "currency": currency,
        "applicant_name": str(data.get("applicant_name") or ""),
        "purpose": str(data.get("purpose") or ""),
        "posting_text": str(data.get("posting_text") or ""),
    }


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

    def fetch_data(
        self, previous: dict[str, FinTSAccountData] | None = None
    ) -> dict[str, FinTSAccountData]:
        """Fetch accounts, balances, and transactions in one FinTS session.

        Transactions are only re-fetched when the balance changed since the
        previous run (or on the very first run). Otherwise the cached list
        from *previous* is carried forward, saving one expensive bank round-trip.
        """
        try:
            client = self._make_client()
            with client:
                info = client.get_information()
                product_names: dict[str, str] = {
                    acc["iban"]: acc.get("product_name") or ""
                    for acc in info.get("accounts", [])
                }
                sepa_accounts = client.get_sepa_accounts()
                result: dict[str, FinTSAccountData] = {}

                for acc in sepa_accounts:
                    try:
                        balance = client.get_balance(acc)
                    except Exception as exc:
                        _LOGGER.warning("Failed to get balance for %s: %s", acc.iban, exc)
                        continue

                    new_balance = balance.amount.amount
                    prev_acc = previous.get(acc.iban) if previous else None
                    balance_changed = prev_acc is None or prev_acc.balance != new_balance

                    # Re-use cached transactions when balance is unchanged and we
                    # already have some. Fetch when balance changed or cache empty.
                    if balance_changed or not (prev_acc and prev_acc.transactions):
                        transactions = self._fetch_transactions(client, acc)
                        _LOGGER.debug(
                            "Fetched %d transactions for %s (balance_changed=%s)",
                            len(transactions),
                            acc.iban,
                            balance_changed,
                        )
                    else:
                        transactions = prev_acc.transactions
                        _LOGGER.debug(
                            "Balance unchanged for %s, reusing %d cached transactions",
                            acc.iban,
                            len(transactions),
                        )

                    result[acc.iban] = FinTSAccountData(
                        iban=acc.iban,
                        bic=acc.bic or "",
                        account_number=acc.accountnumber or "",
                        balance=new_balance,
                        currency=balance.amount.currency,
                        product_name=product_names.get(acc.iban, ""),
                        transactions=transactions,
                    )

                return result
        except Exception as exc:
            from fints.exceptions import FinTSClientPINError

            if isinstance(exc, FinTSClientPINError):
                raise FinTSAuthError(str(exc)) from exc
            raise FinTSConnectionError(str(exc)) from exc

    def _fetch_transactions(self, client, acc) -> list[dict[str, Any]]:
        """Fetch and serialize recent transactions for one account."""
        try:
            start = date.today() - timedelta(days=_TRANSACTION_LOOKBACK_DAYS)
            raw = client.get_transactions(acc, start_date=start)
            return [_serialize_transaction(t) for t in raw]
        except Exception as exc:
            _LOGGER.warning("Failed to get transactions for %s: %s", acc.iban, exc)
            return []

    def fetch_accounts_and_balances(self) -> dict[str, FinTSAccountData]:
        """Backward-compat alias — fetches balances only (no previous data)."""
        return self.fetch_data()

    def validate(self) -> dict[str, FinTSAccountData]:
        """Validate credentials by fetching accounts. Returns the same as fetch_data."""
        return self.fetch_data()
