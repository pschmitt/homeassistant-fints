"""Base entity for FinTS."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FinTSCoordinator


class FinTSEntity(CoordinatorEntity[FinTSCoordinator]):
    """Base entity for all FinTS sensors."""

    _attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        entry = self.coordinator.config_entry
        return DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer=entry.title,
            model="FinTS",
            entry_type=DeviceEntryType.SERVICE,
        )
