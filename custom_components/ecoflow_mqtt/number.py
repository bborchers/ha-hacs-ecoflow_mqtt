from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, NUMBERS, PROTO_NUMBERS, STREAM_NUMBERS
from .entity import EcoFlowEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for serial in coordinator.devices:
        device_type = coordinator.device_type(serial)
        if device_type.startswith("stream_"):
            definitions = STREAM_NUMBERS
        elif device_type.startswith("pstream"):
            definitions = PROTO_NUMBERS
        else:
            definitions = NUMBERS
        entities.extend(EcoFlowNumber(coordinator, serial, key) for key in definitions)
    async_add_entities(entities)


class EcoFlowNumber(EcoFlowEntity, NumberEntity):
    def __init__(self, coordinator, serial, key):
        super().__init__(coordinator, serial, key)
        definitions = {**NUMBERS, **PROTO_NUMBERS, **STREAM_NUMBERS}
        name, unit, minimum, maximum, step, _ = definitions[key]
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_native_min_value = minimum
        self._attr_native_max_value = maximum
        self._attr_native_step = step

    @property
    def native_value(self):
        value = self.coordinator.value(self.serial, self.key)
        return float(value) if value is not None else None

    async def async_set_native_value(self, value: float) -> None:
        self.coordinator.publish_command(self.serial, self.key, value)
