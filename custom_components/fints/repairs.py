"""Interactive FinTS repair flows."""

from __future__ import annotations

import logging
from typing import Any

import probatio
from homeassistant.components.repairs import RepairsFlow, RepairsFlowResult
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .api import FinTSApiClient
from .const import DOMAIN, REPAIR_SCA_REQUIRED

_LOGGER = logging.getLogger(__name__)


class FinTSTanRepairFlow(RepairsFlow):
    """Resume a paused FinTS dialog with a TAN or app approval."""

    def __init__(self, data: dict[str, str | int | float | None]) -> None:
        """Initialize the repair flow with its resumable challenge data."""
        super().__init__()
        self._repair_data = {key: str(value) for key, value in data.items() if value is not None}

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> RepairsFlowResult:
        """Ask for a TAN, or wait for approval in the bank app."""
        if user_input is not None:
            entry_id = self._repair_data["entry_id"]
            entry = self.hass.config_entries.async_get_entry(entry_id)
            if entry is None:
                return self.async_abort(reason="entry_not_found")

            tan = "" if self._repair_data.get("decoupled") == "true" else user_input["tan"]
            try:
                next_challenge = await self.hass.async_add_executor_job(
                    FinTSApiClient.resume_tan,
                    entry.data,
                    self._repair_data,
                    tan,
                )
            except Exception:
                # TANs and bank responses must never be copied into HA logs.
                _LOGGER.warning("FinTS TAN submission failed for %s", entry.title)
                return self._async_show_tan_form(errors={"base": "invalid_tan"})

            if next_challenge:
                self._repair_data.update(next_challenge)
                self._async_update_issue(entry)
                return self._async_show_tan_form()

            runtime = self.hass.data.get(DOMAIN, {}).get(entry_id)
            if runtime:
                entry.async_create_background_task(
                    self.hass,
                    runtime["coordinator"].async_request_refresh(),
                    f"{DOMAIN}_{entry_id}_refresh_after_tan",
                )
            return self.async_create_entry(data={})

        return self._async_show_tan_form()

    def _async_show_tan_form(self, errors: dict[str, str] | None = None) -> RepairsFlowResult:
        """Show the appropriate code-entry or decoupled approval form."""
        challenge = self._repair_data.get("challenge", "")
        schema = (
            probatio.Schema({})
            if self._repair_data.get("decoupled") == "true"
            else probatio.Schema(
                {
                    probatio.Required("tan"): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    )
                }
            )
        )
        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors or {},
            description_placeholders={"challenge": challenge},
        )

    def _async_update_issue(self, entry: ConfigEntry) -> None:
        """Persist updated dialog state if another decoupled retry is needed."""
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            self.issue_id,
            data=self._repair_data,
            is_fixable=True,
            severity=ir.IssueSeverity.ERROR,
            translation_key=REPAIR_SCA_REQUIRED,
            translation_placeholders={"bank_name": entry.title},
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create the interactive TAN repair flow."""
    if data is None:
        raise ValueError(f"Missing FinTS repair data for {issue_id}")
    return FinTSTanRepairFlow(data)
