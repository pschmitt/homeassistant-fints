"""Constants for the FinTS integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "fints"
PLATFORMS: list[Platform] = [Platform.SENSOR]

CONF_BLZ = "blz"
CONF_ENDPOINT = "endpoint"
CONF_PRODUCT_ID = "product_id"
CONF_TAN_MECHANISM = "tan_mechanism"
CONF_TAN_MEDIUM = "tan_medium"

DEFAULT_SCAN_INTERVAL = 3600
MIN_SCAN_INTERVAL = 300
DEFAULT_REQUEST_TIMEOUT = 30

REPAIR_AUTH_FAILED = "auth_failed"
REPAIR_SCA_REQUIRED = "sca_required"
