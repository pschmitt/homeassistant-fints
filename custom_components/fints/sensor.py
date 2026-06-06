"""Sensor platform for FinTS account balances."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import FinTSAccountData
from .const import DOMAIN
from .coordinator import FinTSCoordinator
from .entity import FinTSEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up FinTS balance sensors from a config entry."""
    coordinator: FinTSCoordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    known_ibans: set[str] = set()

    @callback
    def async_add_missing_entities() -> None:
        new_entities: list[SensorEntity] = []
        for iban, account in coordinator.data.items():
            if iban in known_ibans:
                continue
            known_ibans.add(iban)
            new_entities.append(
                FinTSBalanceSensor(
                    coordinator=coordinator,
                    account=account,
                )
            )
        if new_entities:
            async_add_entities(new_entities)

    async_add_missing_entities()
    config_entry.async_on_unload(
        coordinator.async_add_listener(async_add_missing_entities)
    )


class FinTSBalanceSensor(FinTSEntity, SensorEntity):
    """Sensor representing the current balance of one bank account."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:bank-outline"
    # Exclude transactions from the recorder — they change on every balance update
    # and storing lists in the history DB causes significant bloat.
    _unrecorded_attributes = frozenset({"transactions"})

    def __init__(
        self,
        coordinator: FinTSCoordinator,
        account: FinTSAccountData,
    ) -> None:
        """Initialize the balance sensor."""
        super().__init__(coordinator)
        self._iban = account.iban
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}:{account.iban}:balance"
        self._attr_name = account.product_name or account.iban_formatted
        self._attr_native_unit_of_measurement = account.currency

    @property
    def _account(self) -> FinTSAccountData | None:
        """Return the current account data from the coordinator."""
        return self.coordinator.data.get(self._iban)

    @property
    def available(self) -> bool:
        """Return True if the coordinator has up-to-date data for this IBAN."""
        return self.coordinator.last_update_success and self._account is not None

    @property
    def native_value(self) -> Decimal | None:
        """Return the current balance."""
        account = self._account
        return account.balance if account else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return IBAN, BIC, account number, and recent transactions as attributes."""
        account = self._account
        if account is None:
            return {}
        attrs: dict[str, Any] = {"iban": account.iban}
        if account.bic:
            attrs["bic"] = account.bic
        if account.account_number:
            attrs["account_number"] = account.account_number
        attrs["transactions"] = account.transactions
        return attrs
