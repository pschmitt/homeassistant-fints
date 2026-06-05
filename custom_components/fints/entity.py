"""Base entity for FinTS."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_BLZ, CONF_ENDPOINT, DOMAIN
from .coordinator import FinTSCoordinator


class FinTSEntity(CoordinatorEntity[FinTSCoordinator]):
    """Base entity for all FinTS sensors."""

    _attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information representing the bank connection."""
        entry = self.coordinator.config_entry
        return DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}:{entry.data[CONF_BLZ]}")},
            name=self.coordinator.bank_name,
            manufacturer="FinTS",
            model=entry.data[CONF_BLZ],
            configuration_url=entry.data[CONF_ENDPOINT],
        )
