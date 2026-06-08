"""Base entity for FinTS."""

from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import FinTSCoordinator


class FinTSEntity(CoordinatorEntity[FinTSCoordinator]):
    """Base entity for all FinTS sensors."""

    _attr_has_entity_name = True
