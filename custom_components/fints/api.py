"""FinTS API client wrapper."""

from __future__ import annotations

import logging
import re
from base64 import b64decode, b64encode
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from .exceptions import (
    FinTSAuthError,
    FinTSConnectionError,
    FinTSIngReauthRequiredError,
    FinTSTanRequiredError,
)

_LOGGER = logging.getLogger(__name__)

_TRANSACTION_LOOKBACK_DAYS = 30
_TAN_MECHANISM_LABELS = {
    "900": "mobile TAN",
    "910": "chipTAN",
    "911": "chipTAN optical",
    "912": "smsTAN",
    "913": "photoTAN",
    "914": "pushTAN",
    "920": "BestSign",
    "921": "BestSign Push",
    "922": "BestSign SMS",
}
# Some banks prepend the counterparty IBAN (or legacy account number) to the
# applicant name without a separator, e.g. "DE92500105175437945609Jane Doe".
_IBAN_LENGTHS = {
    "AD": 24,
    "AT": 20,
    "BE": 16,
    "BG": 22,
    "CH": 21,
    "CY": 28,
    "CZ": 24,
    "DE": 22,
    "DK": 18,
    "EE": 20,
    "ES": 24,
    "FI": 18,
    "FR": 27,
    "GB": 22,
    "GI": 23,
    "GR": 27,
    "HR": 21,
    "HU": 28,
    "IE": 22,
    "IS": 26,
    "IT": 27,
    "LI": 21,
    "LT": 20,
    "LU": 20,
    "LV": 21,
    "MC": 27,
    "MT": 31,
    "NL": 18,
    "NO": 15,
    "PL": 28,
    "PT": 25,
    "RO": 24,
    "SE": 24,
    "SI": 19,
    "SK": 24,
    "SM": 27,
    "VA": 22,
}
_ACCOUNT_NUMBER_PREFIX = re.compile(r"^(\d{6,10})(?=\D)")


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
        return _mask_iban(self.iban)


def _mask_iban(iban: str) -> str:
    """Mask the middle digits of an IBAN for log/display output."""
    if len(iban) < 8:
        return iban
    return f"{iban[:4]} **** **** {iban[-4:]}"


def _split_applicant(name: str, iban: str) -> tuple[str, str]:
    """Split a counterparty IBAN/account number glued onto the applicant name."""
    name = name.strip()
    if iban and name.startswith(iban):
        return name[len(iban) :].strip(), iban
    length = _IBAN_LENGTHS.get(name[:2])
    if length and len(name) > length and re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]+", name[:length]):
        return name[length:].strip(), name[:length]
    if match := _ACCOUNT_NUMBER_PREFIX.match(name):
        return name[match.end() :].strip(), match.group(1)
    return name, iban


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

    applicant_name, applicant_iban = _split_applicant(
        str(data.get("applicant_name") or ""),
        str(data.get("applicant_iban") or ""),
    )

    return {
        "date": date_str,
        "amount": round(amount_val, 2),
        "currency": currency,
        "applicant_name": applicant_name,
        "applicant_iban": applicant_iban,
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
        tan_mechanism: str | None = None,
        tan_medium: str | None = None,
    ) -> None:
        """Initialize the client."""
        self._blz = blz
        self._username = username
        self._pin = pin
        self._endpoint = endpoint
        self._product_id = product_id
        self._tan_mechanism = tan_mechanism
        self._tan_medium = tan_medium

    def _make_client(self, response_callback: Callable[[Any, Any], None] | None = None):
        """Create and bootstrap a FinTS client."""
        from fints.client import FinTS3PinTanClient, NeedTANResponse

        class _InitialTanChallenge(Exception):
            """Stop bootstrap after preserving a TAN challenge during dialog init."""

        client = FinTS3PinTanClient(
            self._blz,
            self._username,
            self._pin,
            self._endpoint,
            customer_id=self._username,
            product_id=self._product_id,
        )
        # The tan_medium constructor argument was only added in python-fints 4.2.4.
        # Assign the client field directly to remain compatible with older releases.
        client.selected_tan_medium = self._tan_medium or None
        if response_callback is not None:
            client.response_callbacks.append(response_callback)

        # Hibiscus handles TAN requests during dialog initialization as an
        # interactive two step exchange. python-fints records that request on
        # `init_tan_response`, but would otherwise close the dialog before an
        # integration can pause and resume it. Intercept init while the dialog
        # is still open so its state can be resumed from the repair flow.
        new_dialog = client._new_dialog

        def new_dialog_with_tan_capture(lazy_init: bool = False):
            dialog = new_dialog(lazy_init=lazy_init)
            dialog_init = dialog.init

            def init_with_tan_capture(*extra_segments: Any):
                response = dialog_init(*extra_segments)
                if isinstance(client.init_tan_response, NeedTANResponse):
                    client._fints_init_dialog_state = dialog.pause()
                    raise _InitialTanChallenge
                return response

            dialog.init = init_with_tan_capture
            return dialog

        client._new_dialog = new_dialog_with_tan_capture
        try:
            client.fetch_tan_mechanisms()
        except _InitialTanChallenge:
            pass
        if self._tan_mechanism:
            client.set_tan_mechanism(self._tan_mechanism)
        return client

    @staticmethod
    def _extract_tan_media_names(media: Any) -> set[str]:
        """Extract medium/device names from a python-fints HKTAB response."""
        names: set[str] = set()
        if not media:
            return names

        for tan_medium in media[1]:
            name = getattr(tan_medium, "tan_medium_name", "") or ""
            if name:
                names.add(name)
        return names

    @staticmethod
    def _format_tan_mechanism_label(security_function: str, info: Any) -> str:
        """Build a more human-friendly label for a TAN mechanism."""
        bank_name = (getattr(info, "name", "") or "").strip()
        friendly_name = _TAN_MECHANISM_LABELS.get(security_function, "").strip()

        parts: list[str] = []
        if bank_name:
            parts.append(bank_name)
        if friendly_name and friendly_name.lower() != bank_name.lower():
            parts.append(friendly_name)

        description = " / ".join(parts) or f"TAN method {security_function}"
        return f"{description} ({security_function})"

    @staticmethod
    def _get_tan_media_with_skip_sca(client: Any) -> Any:
        """Fetch TAN media like Hibiscus: fresh dialog, no HKTAN on init, then HKTAB."""
        from fints.formals import TANMediaClass4, TANMediaType2
        from fints.segments.auth import HKTAB4, HKTAB5

        dialog = client._new_dialog(lazy_init=True)
        hktab = client._find_highest_supported_command(HKTAB4, HKTAB5)
        seg = hktab(
            tan_media_type=TANMediaType2.ALL,
            tan_media_class=str(TANMediaClass4.ALL),
        )

        saved_allowed = list(client.allowed_security_functions)
        try:
            # Hibiscus fetches TAN media in a dedicated dialog with "skip sca: true".
            # python-fints otherwise injects an HKTAN into dialog init once mechanisms
            # are known, which Norisbank rejects before returning HITAB media names.
            client.allowed_security_functions = []
            client._bootstrap_mode = True
            with dialog:
                dialog.init()
                response = dialog.send(seg)
        finally:
            client.allowed_security_functions = saved_allowed
            client._bootstrap_mode = False

        for hitab in response.response_segments(seg, "HITAB"):
            return hitab.tan_usage_option, list(hitab.tan_media_list)
        return None

    @classmethod
    def discover_auth(
        cls,
        *,
        blz: str,
        username: str,
        pin: str,
        endpoint: str,
        product_id: str,
    ) -> dict[str, Any]:
        """Discover available TAN mechanisms and, when possible, media names."""
        from fints.client import FinTS3PinTanClient

        client = FinTS3PinTanClient(
            blz,
            username,
            pin,
            endpoint,
            customer_id=username,
            product_id=product_id,
        )
        client.fetch_tan_mechanisms()

        mechanisms = [
            {
                "value": key,
                "label": cls._format_tan_mechanism_label(key, info),
            }
            for key, info in client.get_tan_mechanisms().items()
        ]

        tan_media_names: set[str] = set()
        for key in client.get_tan_mechanisms():
            probe = FinTS3PinTanClient(
                blz,
                username,
                pin,
                endpoint,
                customer_id=username,
                product_id=product_id,
            )
            probe.fetch_tan_mechanisms()
            probe.set_tan_mechanism(key)
            try:
                media = probe.get_tan_media()
            except Exception as exc:
                _LOGGER.debug("Default TAN media fetch failed for %s: %s", key, exc)
                try:
                    media = cls._get_tan_media_with_skip_sca(probe)
                except Exception as fallback_exc:
                    _LOGGER.debug(
                        "Skip-SCA TAN media fetch failed for %s: %s",
                        key,
                        fallback_exc,
                    )
                    continue
            if not media:
                continue
            tan_media_names.update(cls._extract_tan_media_names(media))

        return {
            "mechanisms": mechanisms,
            "current_mechanism": client.get_current_tan_mechanism() or "",
            "tan_media_names": sorted(tan_media_names),
        }

    @staticmethod
    def _accounts_from_information(info: dict[str, Any]) -> list[Any]:
        """Build SEPA accounts from UPD metadata as a fallback."""
        from fints.models import SEPAAccount

        accounts: list[Any] = []
        for raw_account in info.get("accounts", []):
            iban = raw_account.get("iban")
            account_number = raw_account.get("account_number")
            bank_identifier = raw_account.get("bank_identifier")
            bank_code = getattr(bank_identifier, "bank_code", None)
            if not iban or not account_number or not bank_code:
                continue

            country = iban[:2] if len(iban) >= 2 else "DE"
            accounts.append(
                SEPAAccount(
                    iban=iban,
                    bic=raw_account.get("bic") or f"XXXX{country}XXX",
                    accountnumber=account_number,
                    subaccount=raw_account.get("subaccount_number") or "",
                    blz=bank_code,
                )
            )
        return accounts

    def _get_accounts(self, client, info: dict[str, Any]) -> list[Any]:
        """Get SEPA accounts, falling back to UPD metadata when HKSPA fails."""
        from fints.exceptions import FinTSSCARequiredError

        try:
            accounts = client.get_sepa_accounts()
        except Exception as exc:
            if isinstance(exc, FinTSSCARequiredError):
                raise
            _LOGGER.warning("Falling back to UPD account data after HKSPA failure: %s", exc)
            accounts = self._accounts_from_information(info)

        if accounts:
            return accounts
        return self._accounts_from_information(info)

    @staticmethod
    def _encode_tan_challenge(
        challenge: Any, client_state: bytes, dialog_state: bytes
    ) -> dict[str, str]:
        """Serialize a python-fints challenge for a local HA repair flow."""
        return {
            "challenge_data": b64encode(challenge.get_data()).decode("ascii"),
            "client_state": b64encode(client_state).decode("ascii"),
            "dialog_state": b64encode(dialog_state).decode("ascii"),
            "challenge": str(challenge.challenge or ""),
            "decoupled": "true" if challenge.decoupled else "false",
        }

    def fetch_data(
        self, previous: dict[str, FinTSAccountData] | None = None
    ) -> dict[str, FinTSAccountData]:
        """Fetch accounts, balances, and transactions in one FinTS session.

        Transactions are only re-fetched when the balance changed since the
        previous run (or on the very first run). Otherwise the cached list
        from *previous* is carried forward, saving one expensive bank round-trip.
        """
        response_codes: list[str] = []
        pending_tan: tuple[Any, bytes] | None = None

        def track_response(_segment: Any, response: Any) -> None:
            response_codes.append(response.code)

        try:
            client = self._make_client(track_response)
            from fints.client import NeedTANResponse

            if isinstance(client.init_tan_response, NeedTANResponse):
                raise FinTSTanRequiredError(
                    "Bank requires interactive TAN/SCA approval during dialog initialization",
                    self._encode_tan_challenge(
                        client.init_tan_response,
                        client.deconstruct(),
                        client._fints_init_dialog_state,
                    ),
                )
            # python-fints converts ING's 9942 response into a generic
            # "PIN wrong?" exception. Retain only the response code so we can
            # raise an actionable Home Assistant repair for this known case.
            with client:
                info = client.get_information()
                product_names: dict[str, str] = {
                    acc["iban"]: acc.get("product_name") or ""
                    for acc in info.get("accounts", [])
                    if acc.get("iban")
                }
                sepa_accounts = self._get_accounts(client, info)
                result: dict[str, FinTSAccountData] = {}

                if isinstance(sepa_accounts, NeedTANResponse):
                    pending_tan = (sepa_accounts, client.pause_dialog())

                for acc in sepa_accounts if not pending_tan else []:
                    try:
                        balance = client.get_balance(acc)
                        if isinstance(balance, NeedTANResponse):
                            pending_tan = (balance, client.pause_dialog())
                            break
                    except Exception as exc:
                        from fints.exceptions import FinTSSCARequiredError

                        if isinstance(exc, (FinTSTanRequiredError, FinTSSCARequiredError)):
                            raise
                        _LOGGER.warning(
                            "Failed to get balance for %s: %s", _mask_iban(acc.iban), exc
                        )
                        continue
                    if balance is None:
                        _LOGGER.warning("No balance returned for %s", _mask_iban(acc.iban))
                        continue

                    new_balance = balance.amount.amount
                    prev_acc = previous.get(acc.iban) if previous else None
                    balance_changed = prev_acc is None or prev_acc.balance != new_balance

                    # Re-use cached transactions when balance is unchanged and we
                    # already have some. Fetch when balance changed or cache empty.
                    if balance_changed or not (prev_acc and prev_acc.transactions):
                        transactions = self._fetch_transactions(client, acc)
                        if isinstance(transactions, NeedTANResponse):
                            pending_tan = (transactions, client.pause_dialog())
                            break
                        _LOGGER.debug(
                            "Fetched %d transactions for %s (balance_changed=%s)",
                            len(transactions),
                            _mask_iban(acc.iban),
                            balance_changed,
                        )
                    else:
                        transactions = prev_acc.transactions
                        _LOGGER.debug(
                            "Balance unchanged for %s, reusing %d cached transactions",
                            _mask_iban(acc.iban),
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

                    if pending_tan:
                        break

            if pending_tan:
                challenge, dialog_state = pending_tan
                raise FinTSTanRequiredError(
                    "Bank requires interactive TAN/SCA approval",
                    self._encode_tan_challenge(challenge, client.deconstruct(), dialog_state),
                )

            return result
        except Exception as exc:
            from fints.exceptions import (
                FinTSClientPINError,
                FinTSClientTemporaryAuthError,
                FinTSSCARequiredError,
            )

            if isinstance(exc, FinTSTanRequiredError):
                raise
            if isinstance(exc, FinTSSCARequiredError):
                raise FinTSTanRequiredError(str(exc)) from exc
            if isinstance(exc, FinTSClientPINError) and self._blz == "50010517":
                response_code = response_codes[-1] if response_codes else "unknown"
                raise FinTSIngReauthRequiredError(
                    f"ING rejected FinTS authentication (last response code: {response_code})"
                ) from exc
            if isinstance(exc, (FinTSClientPINError, FinTSClientTemporaryAuthError)):
                raise FinTSAuthError(str(exc)) from exc
            raise FinTSConnectionError(str(exc)) from exc

    def _fetch_transactions(self, client, acc) -> list[dict[str, Any]] | Any:
        """Fetch and serialize recent transactions for one account."""
        from fints.exceptions import FinTSSCARequiredError

        try:
            start = date.today() - timedelta(days=_TRANSACTION_LOOKBACK_DAYS)
            raw = client.get_transactions(acc, start_date=start)
            from fints.client import NeedTANResponse

            if isinstance(raw, NeedTANResponse):
                return raw
            return [_serialize_transaction(t) for t in raw]
        except (FinTSTanRequiredError, FinTSSCARequiredError):
            raise
        except Exception as exc:
            _LOGGER.warning("Failed to get transactions for %s: %s", _mask_iban(acc.iban), exc)
            return []

    @staticmethod
    def resume_tan(
        entry_data: dict[str, Any], challenge_data: dict[str, str], tan: str
    ) -> dict[str, str] | None:
        """Resume a paused python-fints dialog with a user-entered TAN."""
        from fints.client import FinTS3PinTanClient, NeedRetryResponse, NeedTANResponse

        client = FinTS3PinTanClient(
            entry_data["blz"],
            entry_data["username"],
            entry_data["password"],
            entry_data["endpoint"],
            customer_id=entry_data["username"],
            product_id=entry_data["product_id"],
            from_data=b64decode(challenge_data["client_state"]),
        )
        client.selected_tan_medium = entry_data.get("tan_medium") or None
        if entry_data.get("tan_mechanism"):
            client.set_tan_mechanism(entry_data["tan_mechanism"])
        challenge = NeedRetryResponse.from_data(b64decode(challenge_data["challenge_data"]))
        dialog_state = b64decode(challenge_data["dialog_state"])

        pending_tan = None
        with client.resume_dialog(dialog_state):
            response = client.send_tan(challenge, tan)
            if isinstance(response, NeedTANResponse):
                pending_tan = (response, client.pause_dialog())

        if pending_tan:
            next_challenge, next_dialog_state = pending_tan
            return FinTSApiClient._encode_tan_challenge(
                next_challenge, client.deconstruct(), next_dialog_state
            )
        return None

    def fetch_accounts_and_balances(self) -> dict[str, FinTSAccountData]:
        """Backward-compat alias — fetches balances only (no previous data)."""
        return self.fetch_data()

    def validate(self) -> dict[str, FinTSAccountData]:
        """Validate credentials by fetching accounts. Returns the same as fetch_data."""
        return self.fetch_data()
