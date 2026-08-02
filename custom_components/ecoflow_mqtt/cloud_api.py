"""Small client for the EcoFlow private account API."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import threading
import uuid
from dataclasses import dataclass
from typing import Any

import aiohttp
import paho.mqtt.client as mqtt

from .const import DEFAULT_API_HOST, DEFAULT_BROKER, DEFAULT_PORT
from .protobuf import decode_pstream, decode_stream

_LOGGER = logging.getLogger(__name__)
_MQTT_DISCOVERY_TIMEOUT = 15


class EcoFlowApiError(Exception):
    """Raised when EcoFlow rejects an API request or returns invalid data."""


@dataclass(frozen=True)
class EcoFlowCredentials:
    """Credentials returned by the account certification endpoint."""

    user_id: str
    mqtt_username: str
    mqtt_password: str
    client_id: str
    broker: str = DEFAULT_BROKER
    port: int = DEFAULT_PORT


@dataclass(frozen=True)
class DiscoveredDevice:
    """A device discovered from an EcoFlow MQTT property message."""

    serial: str
    name: str
    product_name: str
    device_type: str


class EcoFlowAccountClient:
    """Authenticate an EcoFlow account and discover its devices."""

    def __init__(self, api_host: str = DEFAULT_API_HOST) -> None:
        self._base_url = f"https://{api_host.strip().rstrip('/')}"
        self._token: str | None = None
        self._user_id: str | None = None

    async def _request_json(
        self,
        session: aiohttp.ClientSession,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            async with session.request(
                method,
                f"{self._base_url}{path}",
                headers=headers,
                params=params,
                json=json,
            ) as response:
                payload = await response.json(content_type=None)
        except (aiohttp.ClientError, ValueError) as err:
            raise EcoFlowApiError("EcoFlow API is unavailable") from err

        if response.status >= 400 or not isinstance(payload, dict):
            raise EcoFlowApiError(f"EcoFlow API returned HTTP {response.status}")
        code = payload.get("code")
        if code not in (None, 0, "0", "200"):
            raise EcoFlowApiError("EcoFlow API rejected the request")
        return payload

    async def login(self, email: str, password: str) -> EcoFlowCredentials:
        """Obtain MQTT credentials from an EcoFlow account login."""

        timeout = aiohttp.ClientTimeout(total=25)
        headers = {
            "lang": "en_US",
            "platform": "android",
            "content-type": "application/json",
            "user-agent": "okhttp/3.14.9",
        }
        payload = {
            "email": email,
            "password": base64.b64encode(password.encode()).decode(),
            "scene": "IOT_APP",
            "userType": "ECOFLOW",
        }
        async with aiohttp.ClientSession(timeout=timeout) as session:
            login_response = await self._request_json(
                session, "POST", "/auth/login", headers=headers, json=payload
            )
            login_data = login_response.get("data")
            if not isinstance(login_data, dict):
                raise EcoFlowApiError("EcoFlow login response is incomplete")
            token = login_data.get("token")
            user = login_data.get("user")
            user_id = user.get("userId") if isinstance(user, dict) else None
            if not isinstance(token, str) or not isinstance(user_id, str):
                raise EcoFlowApiError("EcoFlow login response is incomplete")

            certificate = await self._request_json(
                session,
                "GET",
                "/iot-auth/app/certification",
                headers={**headers, "authorization": f"Bearer {token}"},
                params={"userId": user_id},
            )
            cert_data = certificate.get("data")
            if not isinstance(cert_data, dict):
                raise EcoFlowApiError("EcoFlow MQTT certification is incomplete")

        username = cert_data.get("certificateAccount")
        mqtt_password = cert_data.get("certificatePassword")
        if not isinstance(username, str) or not isinstance(mqtt_password, str):
            raise EcoFlowApiError("EcoFlow MQTT certification is incomplete")
        broker = str(cert_data.get("url") or DEFAULT_BROKER)
        for prefix in ("mqtts://", "mqtt://"):
            if broker.startswith(prefix):
                broker = broker[len(prefix) :]
        broker = broker.rstrip("/")
        try:
            port = int(cert_data.get("port") or DEFAULT_PORT)
        except (TypeError, ValueError):
            port = DEFAULT_PORT
        client_id = f"ANDROID_{uuid.uuid4()}_{user_id}"
        self._token = token
        self._user_id = user_id
        return EcoFlowCredentials(
            user_id=user_id,
            mqtt_username=username,
            mqtt_password=mqtt_password,
            client_id=client_id,
            broker=broker,
            port=port,
        )

    async def discover_devices(
        self, credentials: EcoFlowCredentials
    ) -> list[DiscoveredDevice]:
        """Discover devices through the private MQTT account connection.

        EcoFlow's private account API does not expose the device list. The app
        and the tolwi integration therefore configure private devices manually.
        The MQTT account does, however, receive property messages on the
        account-wide device topic. Their serial numbers can be discovered from
        that topic without requiring developer API keys.
        """

        return await asyncio.to_thread(self._discover_mqtt, credentials)

    @staticmethod
    def _infer_device_type(payload: bytes) -> str:
        try:
            json.loads(payload.decode())
            return "json"
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass

        try:
            stream_values = decode_stream(payload)
        except (ValueError, IndexError):
            stream_values = {}
        if stream_values:
            if "powGetPv3" in stream_values or "powGetPv4" in stream_values:
                return "stream_ultra"
            return "stream_ac_pro"

        try:
            if decode_pstream(payload):
                return "pstream"
        except (ValueError, IndexError):
            pass
        return "json"

    def _discover_mqtt(self, credentials: EcoFlowCredentials) -> list[DiscoveredDevice]:
        found: dict[str, str] = {}
        finished = threading.Event()
        prefix = "/app/device/property/"
        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2, client_id=credentials.client_id
        )
        client.username_pw_set(credentials.mqtt_username, credentials.mqtt_password)
        client.tls_set()

        def on_connect(client, userdata, flags, reason_code, properties=None):
            if reason_code != 0:
                _LOGGER.warning("EcoFlow MQTT discovery connection failed: %s", reason_code)
                finished.set()
                return
            client.subscribe(f"{prefix}+")

        def on_message(client, userdata, message):
            if not message.topic.startswith(prefix):
                return
            serial = message.topic[len(prefix) :].split("/", 1)[0]
            if serial:
                inferred = self._infer_device_type(message.payload)
                if serial not in found or inferred != "json":
                    found[serial] = inferred

        client.on_connect = on_connect
        client.on_message = on_message
        try:
            client.connect(credentials.broker, credentials.port, 60)
            client.loop_start()
            finished.wait(_MQTT_DISCOVERY_TIMEOUT)
        except (OSError, mqtt.MQTTException) as err:
            raise EcoFlowApiError("EcoFlow MQTT discovery is unavailable") from err
        finally:
            client.disconnect()
            client.loop_stop()

        devices = [
            DiscoveredDevice(
                serial=serial,
                name=serial,
                product_name=device_type,
                device_type=device_type,
            )
            for serial, device_type in sorted(found.items())
        ]
        _LOGGER.info("EcoFlow MQTT discovery found %d device(s)", len(devices))
        return devices
