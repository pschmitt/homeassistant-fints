"""Data update coordinator for FinTS."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import FinTSAccountData, FinTSApiClient
from .const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    REPAIR_AUTH_FAILED,
    REPAIR_ING_REAUTH_REQUIRED,
    REPAIR_SCA_REQUIRED,
)
from .exceptions import (
    FinTSAuthError,
    FinTSConnectionError,
    FinTSIngReauthRequiredError,
    FinTSTanRequiredError,
)

_LOGGER = logging.getLogger(__name__)


class FinTSCoordinator(DataUpdateCoordinator[dict[str, FinTSAccountData]]):
    """Coordinate periodic balance fetches for one FinTS bank connection."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: FinTSApiClient,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{config_entry.entry_id}",
            update_interval=timedelta(
                seconds=config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.client = client
        self.config_entry = config_entry

    @property
    def bank_name(self) -> str:
        """Return the configured entry title (bank name)."""
        return self.config_entry.title

    async def _async_update_data(self) -> dict[str, FinTSAccountData]:
        """Fetch account balances and transactions from the bank."""
        previous = self.data
        try:
            data = await self.hass.async_add_executor_job(self.client.fetch_data, previous)
        except FinTSTanRequiredError as err:
            ir.async_delete_issue(
                self.hass,
                DOMAIN,
                f"{REPAIR_AUTH_FAILED}_{self.config_entry.entry_id}",
            )
            ir.async_delete_issue(
                self.hass,
                DOMAIN,
                f"{REPAIR_ING_REAUTH_REQUIRED}_{self.config_entry.entry_id}",
            )
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                f"{REPAIR_SCA_REQUIRED}_{self.config_entry.entry_id}",
                data=(
                    {"entry_id": self.config_entry.entry_id, **err.challenge_data}
                    if err.challenge_data
                    else None
                ),
                is_fixable=err.challenge_data is not None,
                severity=ir.IssueSeverity.ERROR,
                translation_key=REPAIR_SCA_REQUIRED,
                translation_placeholders={"bank_name": self.bank_name},
            )
            raise UpdateFailed(f"TAN/SCA approval required for {self.bank_name}: {err}") from err
        except FinTSIngReauthRequiredError as err:
            ir.async_delete_issue(
                self.hass,
                DOMAIN,
                f"{REPAIR_AUTH_FAILED}_{self.config_entry.entry_id}",
            )
            ir.async_delete_issue(
                self.hass,
                DOMAIN,
                f"{REPAIR_SCA_REQUIRED}_{self.config_entry.entry_id}",
            )
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                f"{REPAIR_ING_REAUTH_REQUIRED}_{self.config_entry.entry_id}",
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key=REPAIR_ING_REAUTH_REQUIRED,
                translation_placeholders={"bank_name": self.bank_name},
            )
            raise UpdateFailed(
                f"ING online banking login required for {self.bank_name}: {err}"
            ) from err
        except FinTSAuthError as err:
            ir.async_delete_issue(
                self.hass,
                DOMAIN,
                f"{REPAIR_SCA_REQUIRED}_{self.config_entry.entry_id}",
            )
            ir.async_delete_issue(
                self.hass,
                DOMAIN,
                f"{REPAIR_ING_REAUTH_REQUIRED}_{self.config_entry.entry_id}",
            )
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                f"{REPAIR_AUTH_FAILED}_{self.config_entry.entry_id}",
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key=REPAIR_AUTH_FAILED,
                translation_placeholders={"bank_name": self.bank_name},
            )
            raise UpdateFailed(f"Authentication failed for {self.bank_name}: {err}") from err
        except FinTSConnectionError as err:
            raise UpdateFailed(f"FinTS connection error for {self.bank_name}: {err}") from err

        ir.async_delete_issue(
            self.hass,
            DOMAIN,
            f"{REPAIR_AUTH_FAILED}_{self.config_entry.entry_id}",
        )
        ir.async_delete_issue(
            self.hass,
            DOMAIN,
            f"{REPAIR_SCA_REQUIRED}_{self.config_entry.entry_id}",
        )
        ir.async_delete_issue(
            self.hass,
            DOMAIN,
            f"{REPAIR_ING_REAUTH_REQUIRED}_{self.config_entry.entry_id}",
        )
        return data
