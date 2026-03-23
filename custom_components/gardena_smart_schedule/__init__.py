"""Gardena Smart Schedule integration.

Fetches schedule data from the Husqvarna API and exposes it
as sensor entities for use by the Gardena Smart System Card.
"""

from __future__ import annotations

import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

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
    # Delay startup to avoid simultaneous login with the main integration
    _LOGGER.debug("Waiting %s seconds before first token request", STARTUP_DELAY_SECONDS)
    await asyncio.sleep(STARTUP_DELAY_SECONDS)

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
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
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
