from __future__ import annotations
from datetime import timedelta
from typing import Any
import logging

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, CONF_TOKEN, CONF_APPLIANCE_ID
from .api import NatureRemoApi, RemoAuthError, RemoConnectionError

_LOGGER = logging.getLogger(__name__)

class RemoCoordinator(DataUpdateCoordinator[dict[str, Any] | None]):

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        self.api = NatureRemoApi(entry.data[CONF_TOKEN])
        self.appliance_id = entry.data[CONF_APPLIANCE_ID]
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}-coordinator",
            update_interval=timedelta(seconds=30),
        )

    async def _async_update_data(self) -> dict[str, Any] | None:
        try:
            apps = await self.api._req("GET", "/appliances")
        except RemoAuthError as e:
            raise UpdateFailed("Unauthorized token") from e
        except RemoConnectionError as e:
            raise UpdateFailed(f"Connection error: {e}") from e

        ac = next((a for a in apps if a.get("id") == self.appliance_id), None)
        if not ac:
            raise UpdateFailed("Appliance not found")
        return ac
