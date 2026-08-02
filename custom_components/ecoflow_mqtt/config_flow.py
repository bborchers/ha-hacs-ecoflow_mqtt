from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector

from .cloud_api import EcoFlowAccountClient, EcoFlowApiError
from .const import (
    CONF_ACCOUNT_EMAIL,
    CONF_ACCOUNT_PASSWORD,
    CONF_API_HOST,
    CONF_BROKER,
    CONF_CLIENT_ID,
    CONF_DEVICES,
    CONF_MQTT_PASSWORD,
    CONF_MQTT_USERNAME,
    CONF_PORT,
    CONF_USER_ID,
    DEFAULT_API_HOST,
    DOMAIN,
)

_DEVICE_ROWS = 8
_DEVICE_TYPES = (
    ("json", "JSON-Gerät"),
    ("pstream", "PowerStream"),
    ("stream_ultra", "Stream Ultra"),
    ("stream_ac_pro", "Stream AC Pro"),
    ("stream_ac", "Stream AC"),
    ("delta3", "DELTA 3"),
    ("delta3plus", "DELTA 3 Plus"),
    ("delta3maxplus", "DELTA 3 Max Plus"),
    ("deltapro3", "DELTA Pro 3"),
    ("deltaproultra", "DELTA Pro Ultra"),
    ("river3", "RIVER 3"),
    ("river3plus", "RIVER 3 Plus"),
    ("unknown", "Unbekannt / sonstiges Protobuf-Gerät"),
)


class EcoFlowConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._credentials = None

    async def async_step_user(self, user_input=None):
        errors: dict[str, str] = {}
        if user_input is not None:
            client = EcoFlowAccountClient(user_input[CONF_API_HOST])
            try:
                credentials = await client.login(
                    user_input[CONF_ACCOUNT_EMAIL], user_input[CONF_ACCOUNT_PASSWORD]
                )
            except EcoFlowApiError:
                errors["base"] = "invalid_auth"
            else:
                await self.async_set_unique_id(credentials.user_id)
                self._abort_if_unique_id_configured()
                self._credentials = credentials
                return await self.async_step_devices()

        schema = vol.Schema(
            {
                vol.Required(CONF_ACCOUNT_EMAIL): str,
                vol.Required(CONF_ACCOUNT_PASSWORD): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                ),
                vol.Optional(CONF_API_HOST, default=DEFAULT_API_HOST): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_devices(self, user_input=None):
        errors: dict[str, str] = {}
        if user_input is not None:
            devices: list[str] = []
            device_types: dict[str, str] = {}
            for index in range(1, _DEVICE_ROWS + 1):
                serial = user_input.get(f"serial_{index}", "").strip()
                if not serial:
                    continue
                if serial in devices:
                    errors[f"serial_{index}"] = "duplicate_device"
                    continue
                devices.append(serial)
                device_types[serial] = user_input[f"type_{index}"]
            if not devices:
                errors["serial_1"] = "no_devices"
            elif not errors:
                return self._create_entry(devices, device_types)

        return self.async_show_form(
            step_id="devices", data_schema=self._device_schema(), errors=errors
        )

    @staticmethod
    def _device_schema() -> vol.Schema:
        options = [{"value": value, "label": label} for value, label in _DEVICE_TYPES]
        type_selector = selector.SelectSelector(
            selector.SelectSelectorConfig(options=options, mode=selector.SelectSelectorMode.DROPDOWN)
        )
        fields = {}
        for index in range(1, _DEVICE_ROWS + 1):
            serial_key = f"serial_{index}"
            type_key = f"type_{index}"
            serial_validator = vol.Required if index == 1 else vol.Optional
            fields[serial_validator(serial_key, default="") if index != 1 else serial_validator(serial_key)] = str
            fields[vol.Optional(type_key, default="json")] = type_selector
        return vol.Schema(fields)

    def _create_entry(self, devices: list[str], device_types: dict[str, str]):
        credentials = self._credentials
        data = {
            CONF_USER_ID: credentials.user_id,
            CONF_MQTT_USERNAME: credentials.mqtt_username,
            CONF_MQTT_PASSWORD: credentials.mqtt_password,
            CONF_CLIENT_ID: credentials.client_id,
            CONF_BROKER: credentials.broker,
            CONF_PORT: credentials.port,
            CONF_DEVICES: devices,
            "device_types": device_types,
        }
        return self.async_create_entry(title=f"EcoFlow ({credentials.user_id})", data=data)
