"""Constants for the FinTS integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "fints"
PLATFORMS: list[Platform] = [Platform.SENSOR]

CONF_BLZ = "blz"
CONF_ENDPOINT = "endpoint"
CONF_PRODUCT_ID = "product_id"

DEFAULT_SCAN_INTERVAL = 3600
MIN_SCAN_INTERVAL = 300
DEFAULT_REQUEST_TIMEOUT = 30

REPAIR_AUTH_FAILED = "auth_failed"
