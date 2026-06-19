"""Event platform for FinTS — one event entity per bank account."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import FinTSAccountData
from .const import DOMAIN
from .coordinator import FinTSCoordinator
from .entity import FinTSEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up per-account FinTS last-transaction event entities."""
    coordinator: FinTSCoordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    known_ibans: set[str] = set()

    @callback
    def _add_missing() -> None:
        new: list[FinTSAccountTransactionEvent] = []
        for iban, account in (coordinator.data or {}).items():
            if iban in known_ibans:
                continue
            known_ibans.add(iban)
            new.append(FinTSAccountTransactionEvent(coordinator, account))
        if new:
            async_add_entities(new)

    _add_missing()
    config_entry.async_on_unload(coordinator.async_add_listener(_add_missing))


class FinTSAccountTransactionEvent(FinTSEntity, EventEntity):
    """Event entity that fires when a new transaction arrives for one account.

    Named after the account's product name (e.g. "Top-Girokonto Last transaction")
    so entity IDs mirror the balance sensors and stay collision-free across
    multiple config entries for the same bank.
    """

    _attr_event_types = ["transaction"]
    _attr_icon = "mdi:bank-transfer"

    def __init__(
        self,
        coordinator: FinTSCoordinator,
        account: FinTSAccountData,
    ) -> None:
        super().__init__(coordinator)
        self._iban = account.iban
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}:{account.iban}:last_transaction"
        )
        account_label = account.product_name or account.iban_formatted
        self._attr_name = f"{account_label} Last transaction"
        self._last_fingerprint: str | None = None

    @callback
    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data
        if not data:
            super()._handle_coordinator_update()
            return

        account = data.get(self._iban)
        if account is None:
            super()._handle_coordinator_update()
            return

        latest = _latest_transaction(account)
        if latest is None:
            super()._handle_coordinator_update()
            return

        fingerprint = _fingerprint(latest)

        if self._last_fingerprint is None:
            self._last_fingerprint = fingerprint
        elif fingerprint != self._last_fingerprint:
            self._last_fingerprint = fingerprint
            attrs: dict[str, Any] = dict(latest)
            attrs["iban"] = self._iban
            self._trigger_event("transaction", attrs)
            return  # _trigger_event already calls async_write_ha_state

        super()._handle_coordinator_update()


def _latest_transaction(account: FinTSAccountData) -> dict | None:
    """Return the most recently booked transaction for one account."""
    best: dict | None = None
    best_date = ""
    for tx in (account.transactions or []):
        date = tx.get("date") or ""
        if date > best_date:
            best_date = date
            best = tx
    return best


def _fingerprint(tx: dict) -> str:
    return (
        f"{tx.get('date', '')}|"
        f"{tx.get('amount', '')}|"
        f"{tx.get('applicant_name', '')}|"
        f"{tx.get('purpose', '')}"
    )
