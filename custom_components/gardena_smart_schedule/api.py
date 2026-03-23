"""API client for Gardena Smart Schedule.

Handles OAuth token management and schedule API calls.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import logging

import aiohttp

from .const import (
    AUTH_TOKEN_URL,
    SCHEDULE_API_BASE_URL,
    GARDENA_API_BASE_URL,
    REQUEST_TIMEOUT,
    TOKEN_REFRESH_BUFFER_SECONDS,
)


_LOGGER = logging.getLogger(__name__)


class AuthError(Exception):
    """Authentication failed."""


class ApiError(Exception):
    """API request failed."""


@dataclass
class Schedule:
    """A scheduled event for a Gardena device."""

    schedule_id: str
    start_at: str
    end_at: str
    weekdays: list[str]
    valve_id: int | None
    paused_until: str | None = None

    @property
    def is_paused(self) -> bool:
        """True if this schedule is currently paused."""
        if not self.paused_until:
            return False
        try:
            ts = datetime.fromisoformat(self.paused_until.replace("Z", "+00:00"))
            return ts > datetime.now(timezone.utc)
        except ValueError:
            return False

    @property
    def paused_until_date(self) -> str | None:
        """Return the pause end date, or None if paused indefinitely or not paused."""
        if not self.is_paused:
            return None
        try:
            ts = datetime.fromisoformat(self.paused_until.replace("Z", "+00:00"))
            if ts.year >= 2038:
                return None
            return self.paused_until
        except ValueError:
            return None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Schedule:
        """Parse from a schedule object in the API device response."""
        recurrence = data.get("recurrence", {})
        return cls(
            schedule_id=str(data.get("id", "")),
            start_at=_normalize_time(data.get("start_at", "")),
            end_at=_normalize_time(data.get("end_at", "")),
            weekdays=recurrence.get("weekdays", []),
            valve_id=data.get("valve_id"),
        )

    def as_dict(self) -> dict[str, Any]:
        """Return schedule as a dict for entity attributes."""
        result: dict[str, Any] = {
            "start_at": self.start_at,
            "end_at": self.end_at,
            "weekdays": self.weekdays,
            "paused": self.is_paused,
        }
        if self.paused_until_date:
            result["paused_until"] = self.paused_until_date
        return result


@dataclass
class DeviceScheduleData:
    """Schedule data for a single Gardena device."""

    device_id: str
    serial: str
    name: str
    model: str
    schedules: list[Schedule] = field(default_factory=list)
    valve_names: dict[int, str] = field(default_factory=dict)


def _normalize_time(time_str: str) -> str:
    """Strip MN+ prefix, keep SR/SS for sunrise/sunset times."""
    if time_str.startswith("MN+"):
        return time_str[3:]
    return time_str


def _parse_valve_names(settings: list[dict[str, Any]]) -> dict[int, str]:
    """Extract valve names from device settings."""
    for setting in settings:
        if setting.get("name") == "valve_names":
            value = setting.get("value", [])
            if isinstance(value, list):
                return {
                    entry["id"]: entry["name"]
                    for entry in value
                    if isinstance(entry, dict) and entry.get("name")
                }
    return {}


def _parse_pause_settings(
    settings: list[dict[str, Any]],
) -> dict[int | None, str | None]:
    """Extract pause timestamps from device settings."""
    result: dict[int | None, str | None] = {}
    for setting in settings:
        name = setting.get("name", "")
        if not name.startswith("schedules_paused_until"):
            continue
        value = setting.get("value", "")
        if not value:
            continue
        parts = name.split("_")
        if parts[-1].isdigit():
            valve_id: int | None = int(parts[-1])
        else:
            valve_id = None
        result[valve_id] = value
    return result


class GardenaScheduleClient:
    """Client for fetching Gardena schedule data."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        session: aiohttp.ClientSession,
    ) -> None:
        """Initialize the client."""
        self._client_id = client_id
        self._client_secret = client_secret
        self._session = session
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._token_expires_at: float = 0

    @property
    def _is_token_valid(self) -> bool:
        return (
            self._access_token is not None
            and time.monotonic() < self._token_expires_at - TOKEN_REFRESH_BUFFER_SECONDS
        )

    async def async_get_token(self) -> str:
        """Return a valid access token, refreshing if needed."""
        if self._is_token_valid:
            assert self._access_token is not None
            return self._access_token

        if self._refresh_token:
            try:
                return await self._async_post_token({
                    "grant_type": "refresh_token",
                    "client_id": self._client_id,
                    "refresh_token": self._refresh_token,
                })
            except AuthError:
                self._refresh_token = None

        return await self._async_post_token({
            "grant_type": "client_credentials",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
        })

    async def _async_post_token(self, data: dict[str, str]) -> str:
        """Post to the token endpoint and store the result."""
        try:
            async with self._session.post(
                AUTH_TOKEN_URL,
                data=data,
                headers={"Accept": "application/json"},
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            ) as resp:
                if resp.status in (400, 401):
                    body = await resp.json()
                    raise AuthError(body.get("error_description", "Authentication failed"))
                resp.raise_for_status()
                token_data: dict[str, Any] = await resp.json()
        except aiohttp.ClientError as err:
            raise AuthError(f"Token request failed: {err}") from err

        self._access_token = str(token_data["access_token"])
        refresh = token_data.get("refresh_token")
        self._refresh_token = str(refresh) if refresh is not None else None
        expires_in = int(token_data.get("expires_in", 3600))
        self._token_expires_at = time.monotonic() + expires_in
        return self._access_token

    async def async_get_locations(self) -> list[dict[str, str]]:
        """Fetch available Gardena locations. Returns list of {id, name}."""
        token = await self.async_get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Authorization-Provider": "husqvarna",
            "X-Api-Key": self._client_id,
            "Accept": "application/vnd.api+json",
        }
        async with self._session.get(
            f"{GARDENA_API_BASE_URL}/locations",
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
        ) as resp:
            if resp.status != 200:
                raise ApiError(f"Failed to fetch locations: {resp.status}")
            data = await resp.json()

        raw = data.get("data", [])
        if isinstance(raw, dict):
            raw = [raw]
        locations: list[dict[str, str]] = []
        for loc in raw:
            locations.append({
                "id": loc.get("id", ""),
                "name": loc.get("attributes", {}).get("name", loc.get("id", "")),
            })
        return locations

    async def async_get_devices(
        self, location_id: str
    ) -> dict[str, dict[str, str]]:
        """Fetch devices from Gardena API. Returns {device_id: {serial, name, model}}."""
        token = await self.async_get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Authorization-Provider": "husqvarna",
            "X-Api-Key": self._client_id,
            "Accept": "application/vnd.api+json",
        }
        async with self._session.get(
            f"{GARDENA_API_BASE_URL}/locations/{location_id}",
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
        ) as resp:
            if resp.status != 200:
                raise ApiError(f"Failed to fetch devices: {resp.status}")
            data = await resp.json()

        devices: dict[str, dict[str, str]] = {}
        for item in data.get("included", []):
            if item.get("type") != "COMMON":
                continue
            item_id = str(item["id"]).split(":")[0]
            attrs = item.get("attributes", {})
            serial = attrs.get("serial", "")
            if isinstance(serial, dict):
                serial = serial.get("value", "")
            name = attrs.get("name", "")
            if isinstance(name, dict):
                name = name.get("value", "")
            model = attrs.get("modelType", "")
            if isinstance(model, dict):
                model = model.get("value", "")
            devices[item_id] = {
                "serial": str(serial),
                "name": str(name),
                "model": str(model),
            }
        return devices

    async def async_get_schedules(
        self, location_id: str, device_info: dict[str, dict[str, str]],
    ) -> dict[str, DeviceScheduleData]:
        """Fetch schedules from schedule API. Returns {device_id: DeviceScheduleData}."""
        token = await self.async_get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }
        try:
            async with self._session.get(
                f"{SCHEDULE_API_BASE_URL}/v1/devices",
                headers=headers,
                params={"locationId": location_id},
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            ) as resp:
                if resp.status != 200:
                    return {}
                data = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError):
            return {}

        result: dict[str, DeviceScheduleData] = {}
        for device_data in data.get("devices", []):
            device_id = device_data.get("id", "")
            raw_schedules = device_data.get("scheduled_events", [])
            if not raw_schedules:
                continue

            info = device_info.get(device_id, {})
            settings = device_data.get("settings", [])
            pause_map = _parse_pause_settings(settings)
            device_valve_names = _parse_valve_names(settings)

            schedules: list[Schedule] = []
            for s in raw_schedules:
                schedule = Schedule.from_api(s)
                schedule.paused_until = pause_map.get(schedule.valve_id)
                schedules.append(schedule)

            result[device_id] = DeviceScheduleData(
                device_id=device_id,
                serial=info.get("serial", ""),
                name=info.get("name", ""),
                model=info.get("model", ""),
                schedules=schedules,
                valve_names=device_valve_names,
            )
        return result
