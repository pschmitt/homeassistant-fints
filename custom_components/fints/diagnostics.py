"""Diagnostics support for FinTS."""

from __future__ import annotations

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .const import DOMAIN

TO_REDACT = {CONF_PASSWORD, "username", "product_id"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> dict:
    """Return diagnostics for a FinTS config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    accounts = []
    for account in (coordinator.data or {}).values():
        accounts.append(
            {
                "iban_masked": account.iban_masked,
                "bic": account.bic,
                "currency": account.currency,
                "balance_available": account.balance is not None,
            }
        )

    return {
        "entry": async_redact_data(dict(config_entry.data), TO_REDACT),
        "options": dict(config_entry.options),
        "accounts": accounts,
    }
