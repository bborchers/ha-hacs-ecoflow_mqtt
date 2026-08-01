from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PROTO_SENSORS, SENSORS, STREAM_SENSORS
from .entity import EcoFlowEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    all_sensors = {**SENSORS, **PROTO_SENSORS, **STREAM_SENSORS}
    async_add_entities([EcoFlowSensor(coordinator, serial, key) for serial in coordinator.devices for key in all_sensors])


class EcoFlowSensor(EcoFlowEntity, SensorEntity):
    def __init__(self, coordinator, serial, key):
        EcoFlowEntity.__init__(self, coordinator, serial, key)
        name, unit, device_class, _ = {**SENSORS, **PROTO_SENSORS, **STREAM_SENSORS}[key]
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        if unit == "%":
            self._attr_native_unit_of_measurement = PERCENTAGE
