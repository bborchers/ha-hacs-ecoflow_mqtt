from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PROTO_SWITCHES, STREAM_SWITCHES, SWITCHES
from .entity import EcoFlowEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for serial in coordinator.devices:
        device_type = coordinator.device_type(serial)
        if device_type.startswith("stream_"):
            definitions = STREAM_SWITCHES
        elif device_type.startswith("pstream"):
            definitions = PROTO_SWITCHES
        else:
            definitions = SWITCHES
        entities.extend(EcoFlowSwitch(coordinator, serial, key) for key in definitions)
    async_add_entities(entities)


class EcoFlowSwitch(EcoFlowEntity, SwitchEntity):
    def __init__(self, coordinator, serial, key):
        super().__init__(coordinator, serial, key)
        self._attr_name = {**SWITCHES, **PROTO_SWITCHES, **STREAM_SWITCHES}[key][0]

    @property
    def is_on(self):
        return bool(self.native_value)

    async def async_turn_on(self, **kwargs):
        self.coordinator.publish_command(self.serial, self.key, True)

    async def async_turn_off(self, **kwargs):
        self.coordinator.publish_command(self.serial, self.key, False)
