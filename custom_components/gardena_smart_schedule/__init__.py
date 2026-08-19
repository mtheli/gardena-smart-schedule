"""Gardena Smart Schedule integration.

Fetches schedule data from the Husqvarna API and exposes it
as sensor entities for use by the Gardena Smart System Card.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_call_later

from .api import GardenaScheduleClient
from .const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_LOCATION_ID, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
from .coordinator import GardenaScheduleCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]

STARTUP_DELAY_SECONDS = 30

type GardenaScheduleConfigEntry = ConfigEntry[GardenaScheduleCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: GardenaScheduleConfigEntry
) -> bool:
    """Set up Gardena Smart Schedule from a config entry."""
    session = async_get_clientsession(hass)
    client = GardenaScheduleClient(
        client_id=entry.data[CONF_CLIENT_ID],
        client_secret=entry.data[CONF_CLIENT_SECRET],
        session=session,
    )
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    coordinator = GardenaScheduleCoordinator(
        hass, client, entry.data[CONF_LOCATION_ID], scan_interval
    )
    entry.runtime_data = coordinator

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # The first poll is delayed so it does not race the main Gardena Smart
    # System integration for a token, but the wait happens in the background:
    # setup must return promptly or Home Assistant cancels it. Nothing else
    # touches the API in the meantime — the coordinator only starts its own
    # timer once a listener is added, and that first tick is a full scan
    # interval away. Sensors are created by the coordinator listener in
    # sensor.py once data arrives, so they show up a moment after startup
    # instead of blocking it. Unlike the config-entry first refresh this
    # cannot mark the entry as retrying: a poll that fails (expired
    # credentials, API down) is logged and retried on the next interval.
    async def _async_first_refresh(_now) -> None:
        _LOGGER.debug("Startup delay elapsed, requesting first schedule poll")
        await coordinator.async_refresh()

    _LOGGER.debug(
        "Delaying first token request by %s seconds", STARTUP_DELAY_SECONDS
    )
    entry.async_on_unload(
        async_call_later(hass, STARTUP_DELAY_SECONDS, _async_first_refresh)
    )
    return True


async def _async_options_updated(
    hass: HomeAssistant, entry: GardenaScheduleConfigEntry
) -> None:
    """Handle options update — reload the integration."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: GardenaScheduleConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
