"""Data coordinator for Mini EMS integration."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MiniEmsApi, MiniEmsApiError, MiniEmsAuthError
from .const import (
    CONF_INVERTER_ID,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class MiniEmsCoordinator(DataUpdateCoordinator):
    """Coordinator to manage data fetching from Mini EMS API."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize coordinator."""
        self.entry = entry
        # Use inverter_name (serial number) to identify the device
        self.inverter_name: str | None = entry.data.get("inverter_name")

        session = async_get_clientsession(hass, verify_ssl=False)
        self.api = MiniEmsApi(
            username=entry.data[CONF_USERNAME],
            password=entry.data[CONF_PASSWORD],
            session=session,
        )

        scan_interval = entry.options.get(
            CONF_SCAN_INTERVAL,
            entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API."""
        try:
            return await self.api.async_fetch_all(inverter_name=self.inverter_name)
        except MiniEmsAuthError as err:
            try:
                await self.api.async_login()
                return await self.api.async_fetch_all(inverter_name=self.inverter_name)
            except MiniEmsApiError as err2:
                raise UpdateFailed(f"Auth failed: {err2}") from err2
        except MiniEmsApiError as err:
            raise UpdateFailed(f"Error fetching Mini EMS data: {err}") from err
