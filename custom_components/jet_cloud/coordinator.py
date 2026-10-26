"""Polls the JET Cloud API."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import Device, JetCloudAuthError, JetCloudClient, JetCloudError, Plant
from .const import (
    CONF_HOST,
    CONF_PASSWORD_HASH,
    CONF_PROJECT_TYPE,
    DOMAIN,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

type JetCloudConfigEntry = ConfigEntry[JetCloudCoordinator]


@dataclass
class JetCloudData:
    plants: dict[int, Plant]
    devices: dict[str, Device]


class JetCloudCoordinator(DataUpdateCoordinator[JetCloudData]):
    """Fetches all plants and devices of one account."""

    config_entry: JetCloudConfigEntry

    def __init__(self, hass: HomeAssistant, entry: JetCloudConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = JetCloudClient(
            async_get_clientsession(hass),
            entry.data[CONF_EMAIL],
            entry.data[CONF_PASSWORD_HASH],
            host=entry.data[CONF_HOST],
            project_type=entry.data[CONF_PROJECT_TYPE],
        )

    async def _async_update_data(self) -> JetCloudData:
        today = dt_util.now().date()
        try:
            plants = await self.client.get_plants()
            devices: dict[str, Device] = {}
            for plant in plants:
                for device in await self.client.get_devices(plant.id):
                    await self.client.update_device_detail(device, today)
                    devices[device.sn] = device
        except JetCloudAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except JetCloudError as err:
            raise UpdateFailed(str(err)) from err
        return JetCloudData(plants={p.id: p for p in plants}, devices=devices)
