"""DataUpdateCoordinator for Gardena Smart Schedule."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from datetime import timedelta

from .api import ApiError, AuthError, DeviceScheduleData, GardenaScheduleClient
from .const import CONF_LOCATION_ID, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

type GardenaScheduleConfigEntry = ConfigEntry[GardenaScheduleCoordinator]


class GardenaScheduleCoordinator(
    DataUpdateCoordinator[dict[str, DeviceScheduleData]]
):
    """Coordinator that polls the schedule API for schedule data."""

    config_entry: GardenaScheduleConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: GardenaScheduleClient,
        location_id: str,
        scan_interval_minutes: int = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=scan_interval_minutes),
        )
        self._client = client
        self._location_id = location_id
        self._device_info: dict[str, dict[str, str]] = {}

    async def _async_update_data(self) -> dict[str, DeviceScheduleData]:
        """Fetch schedule data from the schedule API."""
        try:
            # Refresh device info (serial/name mapping) every poll
            self._device_info = await self._client.async_get_devices(
                self._location_id
            )
        except AuthError as err:
            raise UpdateFailed(f"Authentication failed: {err}") from err
        except ApiError as err:
            raise UpdateFailed(f"Failed to fetch devices: {err}") from err

        try:
            return await self._client.async_get_schedules(
                self._location_id, self._device_info
            )
        except AuthError as err:
            raise UpdateFailed(f"Authentication failed: {err}") from err
