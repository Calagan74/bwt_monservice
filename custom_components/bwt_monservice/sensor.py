"""Sensor platform for BWT MyService."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPressure, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import BWTDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass
class BWTSensorEntityDescription(SensorEntityDescription):
    """Describes BWT sensor entity."""

    value_fn: Callable[[dict[str, Any]], Any] = lambda data: None


SENSORS: tuple[BWTSensorEntityDescription, ...] = (
    BWTSensorEntityDescription(
        key="water_consumption",
        translation_key="water_consumption",
        native_unit_of_measurement=UnitOfVolume.LITERS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:water",
        value_fn=lambda data: data.get("water_use"),
    ),
    BWTSensorEntityDescription(
        key="regenerations_today",
        translation_key="regenerations_today",
        icon="mdi:refresh",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.get("regen_count"),
    ),
    BWTSensorEntityDescription(
        key="hardness_in",
        translation_key="hardness_in",
        native_unit_of_measurement="°f",
        icon="mdi:water-opacity",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("hardness_in"),
    ),
    BWTSensorEntityDescription(
        key="hardness_out",
        translation_key="hardness_out",
        native_unit_of_measurement="°f",
        icon="mdi:water-check",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("hardness_out"),
    ),
    BWTSensorEntityDescription(
        key="water_pressure",
        translation_key="water_pressure",
        native_unit_of_measurement=UnitOfPressure.BAR,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:gauge",
        value_fn=lambda data: data.get("water_pressure"),
    ),
    BWTSensorEntityDescription(
        key="last_seen",
        translation_key="last_seen",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-outline",
        value_fn=lambda data: _parse_timestamp(data.get("last_seen")),
    ),
    BWTSensorEntityDescription(
        key="serial_number",
        translation_key="serial_number",
        icon="mdi:identifier",
        value_fn=lambda data: data.get("serial_number"),
    ),
    BWTSensorEntityDescription(
        key="service_date",
        translation_key="service_date",
        device_class=SensorDeviceClass.DATE,
        icon="mdi:calendar",
        value_fn=lambda data: _parse_date(data.get("service_date")),
    ),
    BWTSensorEntityDescription(
        key="holiday_mode",
        translation_key="holiday_mode",
        icon="mdi:airplane",
        value_fn=lambda data: data.get("holiday_mode"),
    ),
    BWTSensorEntityDescription(
        key="salt_type",
        translation_key="salt_type",
        icon="mdi:shaker",
        value_fn=lambda data: data.get("salt_type"),
    ),
    BWTSensorEntityDescription(
        key="regen_start_hour",
        translation_key="regen_start_hour",
        icon="mdi:clock-start",
        value_fn=lambda data: data.get("regen_start_hour"),
    ),
    BWTSensorEntityDescription(
        key="wifi_signal",
        translation_key="wifi_signal",
        native_unit_of_measurement="dBm",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:wifi",
        value_fn=lambda data: data.get("wifi_signal"),
    ),
)


def _parse_timestamp(value: str | None) -> datetime | None:
    """Parse timestamp string to datetime object."""
    if not value:
        return None

    try:
        # Try to parse ISO format
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        _LOGGER.debug("Failed to parse timestamp: %s", value)
        return None


def _parse_date(value: str | None) -> date | None:
    """Parse date string to date object."""
    if not value:
        return None

    try:
        # Try to parse ISO format (YYYY-MM-DD)
        return date.fromisoformat(value)
    except (ValueError, AttributeError):
        _LOGGER.debug("Failed to parse date: %s", value)
        return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BWT sensors from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: BWTDataUpdateCoordinator = data["coordinator"]

    # Create device info
    device_info = _get_device_info(coordinator)

    # Create sensor entities
    entities = [
        BWTSensor(coordinator, description, device_info)
        for description in SENSORS
    ]

    async_add_entities(entities)


def _get_device_info(coordinator: BWTDataUpdateCoordinator) -> dict[str, Any]:
    """Get device info from coordinator data."""
    data = coordinator.data
    device_name = data.get("device_name", "BWT Device")
    serial_number = data.get("serial_number", "unknown")

    # Extract model from device name if possible
    model = None
    if "MY PERLA" in device_name.upper():
        model = "MY PERLA OPTIMUM"
    elif device_name:
        # Use device name as model if it's not the default
        model = device_name if device_name != "BWT Device" else None

    return {
        "identifiers": {(DOMAIN, serial_number)},
        "name": device_name,
        "manufacturer": MANUFACTURER,
        "model": model,
        "serial_number": serial_number,
    }


class BWTSensor(CoordinatorEntity[BWTDataUpdateCoordinator], SensorEntity):
    """Representation of a BWT sensor."""

    entity_description: BWTSensorEntityDescription

    def __init__(
        self,
        coordinator: BWTDataUpdateCoordinator,
        description: BWTSensorEntityDescription,
        device_info: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_device_info = device_info

        # Set unique ID
        serial_number = device_info.get("serial_number", "unknown")
        self._attr_unique_id = f"{serial_number}_{description.key}"

        # Set entity ID
        self._attr_has_entity_name = True

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success:
            return False

        # Check if the value exists in coordinator data
        value = self.entity_description.value_fn(self.coordinator.data)
        return value is not None
