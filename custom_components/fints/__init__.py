"""The FinTS banking integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .api import FinTSApiClient
from .const import (
    CONF_BLZ,
    CONF_ENDPOINT,
    CONF_PRODUCT_ID,
    CONF_TAN_MECHANISM,
    CONF_TAN_MEDIUM,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import FinTSCoordinator


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up FinTS from a config entry."""
    client = FinTSApiClient(
        blz=config_entry.data[CONF_BLZ],
        username=config_entry.data[CONF_USERNAME],
        pin=config_entry.data[CONF_PASSWORD],
        endpoint=config_entry.data[CONF_ENDPOINT],
        product_id=config_entry.data[CONF_PRODUCT_ID],
        tan_mechanism=config_entry.data.get(CONF_TAN_MECHANISM),
        tan_medium=config_entry.data.get(CONF_TAN_MEDIUM),
    )
    coordinator = FinTSCoordinator(hass, client, config_entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    config_entry.async_on_unload(config_entry.add_update_listener(async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a FinTS config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)
    return unload_ok


async def async_update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Reload the integration after options change."""
    await hass.config_entries.async_reload(config_entry.entry_id)
