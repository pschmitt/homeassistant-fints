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


def _user_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    d = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_BLZ, default=d.get(CONF_BLZ, "")): TextSelector(),
            vol.Required(CONF_USERNAME, default=d.get(CONF_USERNAME, "")): TextSelector(),
            vol.Required(CONF_PASSWORD): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD)
            ),
            vol.Required(CONF_ENDPOINT, default=d.get(CONF_ENDPOINT, "")): TextSelector(),
            vol.Required(CONF_PRODUCT_ID, default=d.get(CONF_PRODUCT_ID, "")): TextSelector(),
            vol.Optional(CONF_NAME, default=d.get(CONF_NAME, "")): TextSelector(),
        }
    )


class FinTSConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for FinTS."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> FinTSOptionsFlow:
        """Return the options flow for this handler."""
        return FinTSOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial setup step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await _validate(self.hass, user_input)
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
                title = user_input.get(CONF_NAME) or user_input[CONF_BLZ]
                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_BLZ: user_input[CONF_BLZ],
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_ENDPOINT: user_input[CONF_ENDPOINT],
                        CONF_PRODUCT_ID: user_input[CONF_PRODUCT_ID],
                    },
                    options={CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_user_schema(user_input),
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
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_BLZ, default=defaults.get(CONF_BLZ, "")): TextSelector(),
                    vol.Required(
                        CONF_USERNAME, default=defaults.get(CONF_USERNAME, "")
                    ): TextSelector(),
                    vol.Optional(CONF_PASSWORD): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                    vol.Required(
                        CONF_ENDPOINT, default=defaults.get(CONF_ENDPOINT, "")
                    ): TextSelector(),
                    vol.Required(
                        CONF_PRODUCT_ID, default=defaults.get(CONF_PRODUCT_ID, "")
                    ): TextSelector(),
                }
            ),
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
