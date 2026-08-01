from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import (CONF_BROKER, CONF_CLIENT_ID, CONF_DEVICES, CONF_MQTT_PASSWORD,
                    CONF_MQTT_USERNAME, CONF_PORT, CONF_USER_ID, DEFAULT_BROKER,
                    DEFAULT_PORT, DOMAIN)


class EcoFlowConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            devices = []
            device_types = {}
            for item in user_input[CONF_DEVICES].split(","):
                item = item.strip()
                if not item:
                    continue
                if "=" in item:
                    serial, device_type = (part.strip() for part in item.split("=", 1))
                    device_types[serial] = device_type.lower()
                    devices.append(serial)
                else:
                    devices.append(item)
            if not devices:
                errors[CONF_DEVICES] = "no_devices"
            else:
                await self.async_set_unique_id(user_input[CONF_USER_ID])
                self._abort_if_unique_id_configured()
                data = {**user_input, CONF_DEVICES: devices, "device_types": device_types}
                return self.async_create_entry(title="EcoFlow", data=data)
        schema = vol.Schema({
            vol.Required(CONF_USER_ID): str,
            vol.Required(CONF_MQTT_USERNAME): str,
            vol.Required(CONF_MQTT_PASSWORD): str,
            vol.Required(CONF_CLIENT_ID): str,
            vol.Optional(CONF_BROKER, default=DEFAULT_BROKER): str,
            vol.Optional(CONF_PORT, default=DEFAULT_PORT): vol.Coerce(int),
            vol.Required(CONF_DEVICES): str,
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
