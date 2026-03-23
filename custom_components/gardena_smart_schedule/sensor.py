"""Sensor platform for Gardena Smart Schedule."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import DeviceScheduleData
from .coordinator import GardenaScheduleConfigEntry, GardenaScheduleCoordinator

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GardenaScheduleConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up schedule sensor entities."""
    coordinator = entry.runtime_data
    known_keys: set[str] = set()

    @callback
    def _async_add_new_entities() -> None:
        new_entities: list[GardenaScheduleSensor] = []
        if coordinator.data is None:
            return
        for device_id, device_data in coordinator.data.items():
            # Check if device has multiple distinct valve zones
            valve_ids = {s.valve_id for s in device_data.schedules if s.valve_id is not None}
            if len(valve_ids) > 1:
                # Multi-valve device (irrigation controller): one sensor per valve
                for valve_id in sorted(valve_ids):
                    key = f"{device_id}_valve_{valve_id}"
                    if key not in known_keys:
                        known_keys.add(key)
                        new_entities.append(
                            GardenaScheduleSensor(
                                coordinator, device_data, valve_id=valve_id
                            )
                        )
            else:
                # Single schedule sensor (mower, power socket, single-valve)
                key = device_id
                if key not in known_keys:
                    known_keys.add(key)
                    new_entities.append(
                        GardenaScheduleSensor(coordinator, device_data)
                    )
        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_entities))
    _async_add_new_entities()


class GardenaScheduleSensor(
    CoordinatorEntity[GardenaScheduleCoordinator], SensorEntity
):
    """Sensor exposing schedule data for a Gardena device."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:calendar-clock"

    def __init__(
        self,
        coordinator: GardenaScheduleCoordinator,
        device_data: DeviceScheduleData,
        valve_id: int | None = None,
    ) -> None:
        """Initialize the schedule sensor."""
        super().__init__(coordinator)
        self._device_id = device_data.device_id
        self._serial = device_data.serial
        self._valve_id = valve_id

        if valve_id is not None:
            self._attr_unique_id = f"{device_data.serial}_schedule_valve_{valve_id}"
            valve_name = device_data.valve_names.get(valve_id)
            self._attr_name = f"Schedule {valve_name}" if valve_name else f"Schedule zone {valve_id}"
        else:
            self._attr_unique_id = f"{device_data.serial}_schedule"
            self._attr_name = "Schedule"

        self._attr_device_info = DeviceInfo(
            identifiers={("gardena_smart_schedule", device_data.serial)},
            name=f"{device_data.name} Schedule",
            manufacturer="Gardena",
            model=device_data.model,
            serial_number=device_data.serial,
        )

    @property
    def _device_data(self) -> DeviceScheduleData | None:
        """Return current device schedule data."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self._device_id)

    @property
    def _schedules(self) -> list:
        """Return the relevant schedules for this sensor."""
        data = self._device_data
        if data is None:
            return []
        if self._valve_id is not None:
            return [s for s in data.schedules if s.valve_id == self._valve_id]
        return data.schedules

    @property
    def native_value(self) -> int | None:
        """Return the total number of schedules."""
        schedules = self._schedules
        if not schedules:
            return None
        return len(schedules)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose schedule data for the card to read."""
        schedules = self._schedules
        if not schedules:
            return None
        attrs: dict[str, Any] = {
            "gardena_device_id": self._device_id,
            "gardena_serial": self._serial,
            "scheduled_events": [s.as_dict() for s in schedules],
        }
        if self._valve_id is not None:
            attrs["valve_id"] = self._valve_id
        return attrs
