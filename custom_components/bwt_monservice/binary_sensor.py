"""Binary sensor platform for BWT MyService."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import BWTDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass
class BWTBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes BWT binary sensor entity."""

    value_fn: Callable[[dict[str, Any]], bool | None] = lambda data: None


BINARY_SENSORS: tuple[BWTBinarySensorEntityDescription, ...] = (
    BWTBinarySensorEntityDescription(
        key="connected",
        translation_key="connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        icon="mdi:wifi",
        value_fn=lambda data: data.get("connected"),
    ),
    BWTBinarySensorEntityDescription(
        key="online",
        translation_key="online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        icon="mdi:check-network",
        value_fn=lambda data: data.get("online"),
    ),
    BWTBinarySensorEntityDescription(
        key="connectable",
        translation_key="connectable",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        icon="mdi:network",
        value_fn=lambda data: data.get("connectable"),
    ),
    BWTBinarySensorEntityDescription(
        key="power_outage",
        translation_key="power_outage",
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:power-plug-off",
        value_fn=lambda data: data.get("power_outage"),
    ),
    BWTBinarySensorEntityDescription(
        key="salt_alarm",
        translation_key="salt_alarm",
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:alert",
        value_fn=lambda data: data.get("salt_alarm"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BWT binary sensors from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: BWTDataUpdateCoordinator = data["coordinator"]

    # Create device info
    device_info = _get_device_info(coordinator, entry)

    # Create binary sensor entities
    entities = [
        BWTBinarySensor(coordinator, description, device_info)
        for description in BINARY_SENSORS
    ]

    async_add_entities(entities)


def _get_device_info(coordinator: BWTDataUpdateCoordinator, entry: ConfigEntry) -> dict[str, Any]:
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

    # Get optional host for configuration_url
    host = entry.data.get(CONF_HOST)

    device_info = {
        "identifiers": {(DOMAIN, serial_number)},
        "name": device_name,
        "manufacturer": MANUFACTURER,
        "model": model,
        "serial_number": serial_number,
    }

    # Add configuration_url if host is provided
    if host:
        device_info["configuration_url"] = f"http://{host}"

    return device_info


class BWTBinarySensor(CoordinatorEntity[BWTDataUpdateCoordinator], BinarySensorEntity):
    """Representation of a BWT binary sensor."""

    entity_description: BWTBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: BWTDataUpdateCoordinator,
        description: BWTBinarySensorEntityDescription,
        device_info: dict[str, Any],
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_device_info = device_info

        # Set unique ID
        serial_number = device_info.get("serial_number", "unknown")
        self._attr_unique_id = f"{serial_number}_{description.key}"

        # Set entity ID
        self._attr_has_entity_name = True

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success:
            return False

        # Check if the value exists in coordinator data
        value = self.entity_description.value_fn(self.coordinator.data)
        return value is not None
