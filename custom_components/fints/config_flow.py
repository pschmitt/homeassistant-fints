"""Config flow for FinTS."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import FinTSApiClient
from .const import (
    CONF_BLZ,
    CONF_ENDPOINT,
    CONF_PRODUCT_ID,
    DEFAULT_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    DOMAIN,
)
from .exceptions import FinTSAuthError, FinTSConnectionError

_LOGGER = logging.getLogger(__name__)

CONF_BANK_PRESET = "bank_preset"
PRESET_CUSTOM = "custom"

BANK_PRESETS: dict[str, dict[str, str]] = {
    "ing": {
        "name": "ING",
        CONF_BLZ: "50010517",
        CONF_ENDPOINT: "https://fints.ing.de/fints",
    },
    "deutsche_bank": {
        "name": "Deutsche Bank",
        CONF_BLZ: "20070000",
        CONF_ENDPOINT: "https://meine.deutsche-bank.de/pfpd",
    },
    "commerzbank": {
        "name": "Commerzbank",
        CONF_BLZ: "20040000",
        CONF_ENDPOINT: "https://fints.commerzbank.de/",
    },
    "postbank": {
        "name": "Postbank",
        CONF_BLZ: "20010020",
        CONF_ENDPOINT: "https://banking.postbank.de/rai/fints",
    },
    "dkb": {
        "name": "DKB",
        CONF_BLZ: "12030000",
        CONF_ENDPOINT: "https://banking.dkb.de/api/fints",
    },
    "comdirect": {
        "name": "comdirect",
        CONF_BLZ: "20041111",
        CONF_ENDPOINT: "https://fints.comdirect.de/fints",
    },
    PRESET_CUSTOM: {
        "name": "Other / Custom",
        CONF_BLZ: "",
        CONF_ENDPOINT: "",
    },
}

PRESET_OPTIONS = [
    {"value": key, "label": info["name"]}
    for key, info in BANK_PRESETS.items()
]


async def _validate(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, str]:
    """Validate credentials and return metadata."""
    client = FinTSApiClient(
        blz=data[CONF_BLZ],
        username=data[CONF_USERNAME],
        pin=data[CONF_PASSWORD],
        endpoint=data[CONF_ENDPOINT],
        product_id=data[CONF_PRODUCT_ID],
    )
    accounts = await hass.async_add_executor_job(client.validate)
    return {
        "unique_id": f"{data[CONF_BLZ]}:{data[CONF_USERNAME]}",
        "account_count": str(len(accounts)),
    }


def _credentials_schema(
    defaults: dict[str, Any],
    *,
    show_blz: bool = True,
    show_endpoint: bool = True,
    pin_required: bool = True,
) -> vol.Schema:
    fields: dict[vol.Marker, Any] = {}
    if show_blz:
        fields[vol.Required(CONF_BLZ, default=defaults.get(CONF_BLZ, ""))] = TextSelector()
    fields[vol.Required(CONF_USERNAME, default=defaults.get(CONF_USERNAME, ""))] = TextSelector()
    if pin_required:
        fields[vol.Required(CONF_PASSWORD)] = TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        )
    else:
        fields[vol.Optional(CONF_PASSWORD)] = TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        )
    if show_endpoint:
        fields[vol.Required(CONF_ENDPOINT, default=defaults.get(CONF_ENDPOINT, ""))] = TextSelector()
    fields[vol.Required(CONF_PRODUCT_ID, default=defaults.get(CONF_PRODUCT_ID, ""))] = TextSelector()
    return vol.Schema(fields)


class FinTSConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for FinTS."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._preset: str | None = None
        self._preset_data: dict[str, str] = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> FinTSOptionsFlow:
        """Return the options flow for this handler."""
        return FinTSOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 1: pick a bank preset (or custom)."""
        if user_input is not None:
            preset_key = user_input[CONF_BANK_PRESET]
            self._preset = preset_key
            self._preset_data = dict(BANK_PRESETS[preset_key])
            return await self.async_step_credentials()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_BANK_PRESET, default="ing"): SelectSelector(
                        SelectSelectorConfig(
                            options=PRESET_OPTIONS,
                            mode=SelectSelectorMode.LIST,
                        )
                    )
                }
            ),
        )

    async def async_step_credentials(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 2: enter credentials (BLZ/endpoint pre-filled for presets)."""
        errors: dict[str, str] = {}
        is_custom = self._preset == PRESET_CUSTOM

        if user_input is not None:
            data = {
                CONF_BLZ: user_input.get(CONF_BLZ) or self._preset_data.get(CONF_BLZ, ""),
                CONF_USERNAME: user_input[CONF_USERNAME],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
                CONF_ENDPOINT: user_input.get(CONF_ENDPOINT) or self._preset_data.get(CONF_ENDPOINT, ""),
                CONF_PRODUCT_ID: user_input[CONF_PRODUCT_ID],
            }
            name = user_input.get(CONF_NAME) or self._preset_data.get("name") or data[CONF_BLZ]

            try:
                info = await _validate(self.hass, data)
            except FinTSAuthError:
                errors["base"] = "invalid_auth"
            except FinTSConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during FinTS config validation")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info["unique_id"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=name,
                    data=data,
                    options={CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL},
                )

        defaults = {**self._preset_data, **(user_input or {})}
        schema = _credentials_schema(
            defaults,
            show_blz=is_custom,
            show_endpoint=is_custom,
        )
        if not is_custom:
            # For presets, append the optional name field
            schema = vol.Schema(
                {
                    **schema.schema,
                    vol.Optional(CONF_NAME, default=defaults.get(CONF_NAME, "")): TextSelector(),
                }
            )

        return self.async_show_form(
            step_id="credentials",
            data_schema=schema,
            description_placeholders={
                "bank": self._preset_data.get("name", ""),
                "blz": self._preset_data.get(CONF_BLZ, ""),
                "endpoint": self._preset_data.get(CONF_ENDPOINT, ""),
            },
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of an existing entry."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            if not user_input.get(CONF_PASSWORD):
                user_input[CONF_PASSWORD] = entry.data[CONF_PASSWORD]
            merged = {**entry.data, **user_input}

            try:
                info = await _validate(self.hass, merged)
            except FinTSAuthError:
                errors["base"] = "invalid_auth"
            except FinTSConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during FinTS reconfigure validation")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data=merged,
                    unique_id=info["unique_id"],
                )

        defaults = entry.data
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_credentials_schema(defaults, pin_required=False),
            errors=errors,
        )


class FinTSOptionsFlow(OptionsFlow):
    """Handle options for FinTS."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage FinTS options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=self._config_entry.options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_SCAN_INTERVAL,
                            mode=NumberSelectorMode.BOX,
                            step=1,
                        )
                    )
                }
            ),
        )
