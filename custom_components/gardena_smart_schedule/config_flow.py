"""Config flow for Gardena Smart Schedule."""

from __future__ import annotations

from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AuthError, ApiError, GardenaScheduleClient
from .const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_LOCATION_ID,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)


class GardenaScheduleConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Gardena Smart Schedule."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry):
        """Return the options flow handler."""
        return GardenaScheduleOptionsFlow()

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._client_id: str = ""
        self._client_secret: str = ""
        self._locations: list[dict[str, str]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial credentials step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._client_id = user_input[CONF_CLIENT_ID]
            self._client_secret = user_input[CONF_CLIENT_SECRET]

            session = async_get_clientsession(self.hass)
            client = GardenaScheduleClient(
                self._client_id, self._client_secret, session
            )

            try:
                self._locations = await client.async_get_locations()
            except AuthError:
                errors["base"] = "invalid_auth"
            except (ApiError, aiohttp.ClientError):
                errors["base"] = "cannot_connect"
            else:
                if len(self._locations) == 1:
                    return self.async_create_entry(
                        title=self._locations[0].get("name", "Gardena"),
                        data={
                            CONF_CLIENT_ID: self._client_id,
                            CONF_CLIENT_SECRET: self._client_secret,
                            CONF_LOCATION_ID: self._locations[0]["id"],
                        },
                    )
                if len(self._locations) > 1:
                    return await self.async_step_location()
                errors["base"] = "no_locations"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CLIENT_ID): str,
                    vol.Required(CONF_CLIENT_SECRET): str,
                }
            ),
            errors=errors,
        )

    async def async_step_location(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle location selection when multiple locations exist."""
        if user_input is not None:
            location_id = user_input[CONF_LOCATION_ID]
            name = next(
                (loc["name"] for loc in self._locations if loc["id"] == location_id),
                "Gardena",
            )
            return self.async_create_entry(
                title=name,
                data={
                    CONF_CLIENT_ID: self._client_id,
                    CONF_CLIENT_SECRET: self._client_secret,
                    CONF_LOCATION_ID: location_id,
                },
            )

        location_options = {
            loc["id"]: loc.get("name", loc["id"]) for loc in self._locations
        }
        return self.async_show_form(
            step_id="location",
            data_schema=vol.Schema(
                {vol.Required(CONF_LOCATION_ID): vol.In(location_options)}
            ),
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-authentication confirmation."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()

        if user_input is not None:
            client_id = user_input[CONF_CLIENT_ID]
            client_secret = user_input[CONF_CLIENT_SECRET]

            session = async_get_clientsession(self.hass)
            client = GardenaScheduleClient(client_id, client_secret, session)

            try:
                await client.async_get_locations()
            except AuthError:
                errors["base"] = "invalid_auth"
            except (ApiError, aiohttp.ClientError):
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data={
                        **entry.data,
                        CONF_CLIENT_ID: client_id,
                        CONF_CLIENT_SECRET: client_secret,
                    },
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_CLIENT_ID, default=entry.data.get(CONF_CLIENT_ID, "")
                    ): str,
                    vol.Required(CONF_CLIENT_SECRET): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            client_id = user_input[CONF_CLIENT_ID]
            client_secret = user_input[CONF_CLIENT_SECRET]

            session = async_get_clientsession(self.hass)
            client = GardenaScheduleClient(client_id, client_secret, session)

            try:
                locations = await client.async_get_locations()
            except AuthError:
                errors["base"] = "invalid_auth"
            except (ApiError, aiohttp.ClientError):
                errors["base"] = "cannot_connect"
            else:
                # Keep existing location if still valid
                existing_loc = entry.data.get(CONF_LOCATION_ID, "")
                loc_ids = [loc["id"] for loc in locations]
                location_id = existing_loc if existing_loc in loc_ids else loc_ids[0] if loc_ids else ""

                if not location_id:
                    errors["base"] = "no_locations"
                else:
                    return self.async_update_reload_and_abort(
                        entry,
                        data={
                            CONF_CLIENT_ID: client_id,
                            CONF_CLIENT_SECRET: client_secret,
                            CONF_LOCATION_ID: location_id,
                        },
                    )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_CLIENT_ID, default=entry.data.get(CONF_CLIENT_ID, "")
                    ): str,
                    vol.Required(CONF_CLIENT_SECRET): str,
                }
            ),
            errors=errors,
        )


class GardenaScheduleOptionsFlow(OptionsFlow):
    """Handle options for Gardena Smart Schedule."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the options form."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL, default=current_interval
                    ): vol.All(
                        int,
                        vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                    ),
                }
            ),
        )
