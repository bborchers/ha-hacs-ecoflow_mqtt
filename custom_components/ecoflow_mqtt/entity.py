from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


class EcoFlowEntity(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, serial: str, key: str) -> None:
        super().__init__(coordinator)
        self.serial = serial
        self.key = key
        self._attr_unique_id = f"{serial}_{key}"
        self._attr_device_info = {"identifiers": {(DOMAIN, serial)}, "name": f"EcoFlow {serial}", "manufacturer": "EcoFlow"}

    @property
    def available(self) -> bool:
        return self.coordinator.available(self.serial)

    @property
    def native_value(self):
        return self.coordinator.value(self.serial, self.key)
