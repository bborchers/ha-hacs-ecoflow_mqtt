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


class EcoFlowConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._credentials = None
        self._devices = []
        self._discovery_error = False

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
                try:
                    self._devices = await client.discover_devices(credentials)
                except EcoFlowApiError:
                    self._discovery_error = True
                    self._devices = []
                if self._devices:
                    return await self.async_step_select_devices()
                return await self.async_step_manual_devices()

        schema = vol.Schema(
            {
                vol.Required(CONF_ACCOUNT_EMAIL): str,
                vol.Required(CONF_ACCOUNT_PASSWORD): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.PASSWORD
                    )
                ),
                vol.Optional(CONF_API_HOST, default=DEFAULT_API_HOST): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_select_devices(self, user_input=None):
        if user_input is not None:
            selected = set(user_input[CONF_DEVICES])
            devices = [device for device in self._devices if device.serial in selected]
            if not devices:
                return self.async_show_form(
                    step_id="select_devices",
                    data_schema=self._device_selector_schema(),
                    errors={CONF_DEVICES: "no_devices"},
                )
            return self._create_entry(devices)

        return self.async_show_form(
            step_id="select_devices", data_schema=self._device_selector_schema()
        )

    def _device_selector_schema(self):
        options = [
            {
                "value": device.serial,
                "label": f"{device.name} ({device.product_name})",
            }
            for device in self._devices
        ]
        return vol.Schema(
            {
                vol.Required(CONF_DEVICES): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options, multiple=True, mode=selector.SelectSelectorMode.LIST
                    )
                )
            }
        )

    async def async_step_manual_devices(self, user_input=None):
        errors: dict[str, str] = {}
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
                else:
                    serial = item
                if serial:
                    devices.append(serial)
            if not devices:
                errors[CONF_DEVICES] = "no_devices"
            else:
                return self._create_entry(
                    devices,
                    device_types=device_types,
                    discovery_error=self._discovery_error,
                )

        description_placeholders = {
            "reason": "Die automatische Geräteerkennung war nicht verfügbar."
            if self._discovery_error
            else "Für dieses Konto wurden keine Geräte zurückgegeben."
        }
        return self.async_show_form(
            step_id="manual_devices",
            data_schema=vol.Schema({vol.Required(CONF_DEVICES): str}),
            errors=errors,
            description_placeholders=description_placeholders,
        )

    def _create_entry(self, devices, *, device_types=None, discovery_error=False):
        credentials = self._credentials
        data = {
            CONF_USER_ID: credentials.user_id,
            CONF_MQTT_USERNAME: credentials.mqtt_username,
            CONF_MQTT_PASSWORD: credentials.mqtt_password,
            CONF_CLIENT_ID: credentials.client_id,
            CONF_BROKER: credentials.broker,
            CONF_PORT: credentials.port,
            CONF_DEVICES: [device.serial for device in devices]
            if devices and not isinstance(devices[0], str)
            else devices,
            "device_types": device_types
            or {
                device.serial: device.device_type
                for device in devices
                if not isinstance(device, str)
            },
        }
        if discovery_error:
            data["device_discovery_fallback"] = True
        return self.async_create_entry(title=f"EcoFlow ({credentials.user_id})", data=data)
