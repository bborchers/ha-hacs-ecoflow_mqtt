from __future__ import annotations

import asyncio
import json
import logging
import random

import paho.mqtt.client as mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (CONF_BROKER, CONF_CLIENT_ID, CONF_DEVICES, CONF_MQTT_PASSWORD,
                    CONF_MQTT_USERNAME, CONF_PORT, CONF_USER_ID, DOMAIN, SENSORS)
from .protobuf import (decode_pstream, decode_stream, encode_pstream_command,
                       encode_pstream_get, encode_stream_command)

_LOGGER = logging.getLogger(__name__)


class EcoFlowCoordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=None)
        self.entry = entry
        self.values: dict[str, dict[str, float | bool | str]] = {d: {} for d in entry.data[CONF_DEVICES]}
        self.online: dict[str, bool] = {d: False for d in entry.data[CONF_DEVICES]}
        self._client: mqtt.Client | None = None
        self._loop = asyncio.get_running_loop()
        self._connected = asyncio.Event()

    @property
    def devices(self) -> list[str]:
        return list(self.values)

    def device_type(self, serial: str) -> str:
        return self.entry.data.get("device_types", {}).get(serial, "")

    async def async_start(self) -> None:
        await self.hass.async_add_executor_job(self._connect)

    async def async_stop(self) -> None:
        if self._client:
            await self.hass.async_add_executor_job(self._client.disconnect)
            self._client = None

    def value(self, serial: str, key: str):
        return self.values.get(serial, {}).get(key)

    def available(self, serial: str) -> bool:
        return self.online.get(serial, False)

    def _connect(self) -> None:
        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=self.entry.data[CONF_CLIENT_ID])
        self._client.username_pw_set(self.entry.data[CONF_MQTT_USERNAME], self.entry.data[CONF_MQTT_PASSWORD])
        self._client.tls_set()
        self._client.reconnect_delay_set(5, 60)
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.on_disconnect = self._on_disconnect
        self._client.connect_async(self.entry.data[CONF_BROKER], self.entry.data[CONF_PORT], 60)
        self._client.loop_start()

    def _on_connect(self, client, userdata, flags, reason_code, properties=None) -> None:
        if reason_code != 0:
            _LOGGER.error("EcoFlow MQTT connection failed: %s", reason_code)
            return
        uid = self.entry.data[CONF_USER_ID]
        for serial in self.devices:
            for topic in (
                f"/app/{uid}/{serial}/thing/property/set",
                f"/app/{uid}/{serial}/thing/property/set_reply",
                f"/app/{uid}/{serial}/thing/property/get_reply",
                f"/app/device/property/{serial}",
            ):
                client.subscribe(topic)
            self._publish_get(serial)

    def _on_disconnect(self, client, userdata, flags, reason_code, properties=None) -> None:
        self._loop.call_soon_threadsafe(self._mark_unavailable)

    def _mark_unavailable(self) -> None:
        for serial in self.devices:
            self.online[serial] = False
        self.async_set_updated_data(self.values)

    def _on_message(self, client, userdata, message) -> None:
        serial = next((d for d in self.devices if f"/{d}/" in message.topic or message.topic.endswith(f"/{d}")), None)
        if serial is None:
            return
        try:
            payload = json.loads(message.payload.decode())
        except (UnicodeDecodeError, json.JSONDecodeError):
            if self.device_type(serial).startswith("stream_"):
                decoder = decode_stream
            elif self.device_type(serial).startswith("pstream"):
                decoder = decode_pstream
            else:
                decoder = None
            if decoder:
                try:
                    parsed = decoder(message.payload)
                except ValueError as err:
                    _LOGGER.debug("Could not decode protobuf message for %s: %s", serial, err)
                    return
                if parsed:
                    self._loop.call_soon_threadsafe(self._update, serial, parsed)
                return
            _LOGGER.debug("Ignoring non-JSON message for %s", serial)
            return
        params = payload.get("params") or payload.get("data", {}).get("quotaMap") or {}
        if not params:
            if payload.get("data", {}).get("online") == 0:
                self._loop.call_soon_threadsafe(self._set_online, serial, False)
            return
        parsed = {}
        for raw_key, raw_value in params.items():
            key = raw_key.rsplit(".", 1)[-1]
            if key not in SENSORS and key not in {"cfgAcEnabled", "dcOutState", "carState", "cfgAcXboost", "cfgChgWatts"}:
                continue
            parsed[key] = self._convert(key, raw_value)
        self._loop.call_soon_threadsafe(self._update, serial, parsed)

    @staticmethod
    def _convert(key: str, value):
        if key in ("cfgAcEnabled", "dcOutState", "carState", "cfgAcXboost"):
            return bool(value)
        scale = SENSORS.get(key, ("", "", "", 1))[3]
        try:
            return round(float(value) * scale, 3)
        except (TypeError, ValueError):
            return value

    def _update(self, serial: str, values: dict) -> None:
        self.values[serial].update(values)
        self.online[serial] = True
        self.async_set_updated_data(self.values)

    def _set_online(self, serial: str, value: bool) -> None:
        self.online[serial] = value
        self.async_set_updated_data(self.values)

    def _publish_get(self, serial: str) -> None:
        if self._client:
            uid = self.entry.data[CONF_USER_ID]
            topic = f"/app/{uid}/{serial}/thing/property/get"
            if self.device_type(serial).startswith(("pstream", "stream_")):
                self._client.publish(topic, encode_pstream_get(serial), qos=1)
                return
            payload = {"from": "Android", "lang": "en-us", "id": str(random.randint(100000000, 900000000)), "moduleType": 1, "operateType": "latestQuotas", "version": "1.0", "params": {}, "moduleSn": serial}
            self._client.publish(topic, json.dumps(payload), qos=1)

    def publish_command(self, serial: str, key: str, value) -> None:
        if not self._client:
            return
        if self.device_type(serial).startswith("pstream"):
            try:
                payload = encode_pstream_command(serial, key, value)
            except ValueError as err:
                _LOGGER.warning("%s", err)
                return
            uid = self.entry.data[CONF_USER_ID]
            self._client.publish(f"/app/{uid}/{serial}/thing/property/set", payload, qos=1)
            return
        if self.device_type(serial).startswith("stream_"):
            try:
                payload = encode_stream_command(serial, key, value)
            except ValueError as err:
                _LOGGER.warning("%s", err)
                return
            uid = self.entry.data[CONF_USER_ID]
            self._client.publish(f"/app/{uid}/{serial}/thing/property/set", payload, qos=1)
            return
        uid = self.entry.data[CONF_USER_ID]
        if key == "cfgAcEnabled":
            params = {"out_voltage": -1, "out_freq": 255, "xboost": 255, "enabled": int(value)}
        elif key == "cfgAcXboost":
            params = {"xboost": int(value)}
        elif key in {"dcOutState", "carState"}:
            params = {"enabled": int(value)}
        elif key == "maxChgSoc":
            params = {"maxChgSoc": int(value)}
        elif key == "minDsgSoc":
            params = {"minDsgSoc": int(value)}
        elif key == "cfgChgWatts":
            params = {"chgWatts": int(value), "chgPauseFlag": 255}
        else:
            params = {key: value}
        operation = {"cfgAcEnabled": "acOutCfg", "dcOutState": "dcOutCfg", "carState": "mpptCar", "cfgAcXboost": "acOutCfg", "maxChgSoc": "upsConfig", "minDsgSoc": "dsgCfg", "cfgChgWatts": "acChgCfg"}.get(key, key)
        payload = {"from": "Android", "lang": "en-us", "id": str(random.randint(100000000, 900000000)), "moduleType": 5 if key.startswith("cfg") or key in {"carState", "cfgAcEnabled"} else 2, "operateType": operation, "version": "1.0", "moduleSn": serial, "params": params}
        self._client.publish(f"/app/{uid}/{serial}/thing/property/set", json.dumps(payload), qos=1)
