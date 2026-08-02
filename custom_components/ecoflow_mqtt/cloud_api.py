"""Small client for the EcoFlow private account API."""

from __future__ import annotations

import base64
import uuid
from dataclasses import dataclass
from typing import Any

import aiohttp

from .const import DEFAULT_API_HOST, DEFAULT_BROKER, DEFAULT_PORT


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
    """A device returned by EcoFlow's private device list endpoint."""

    serial: str
    name: str
    product_name: str
    device_type: str


def _device_type(product_name: str, device_name: str) -> str:
    """Map EcoFlow product labels to the decoder families used by this integration."""

    label = f"{product_name} {device_name}".lower().replace("-", " ")
    if "stream ultra" in label:
        return "stream_ultra"
    if "stream ac pro" in label:
        return "stream_ac_pro"
    if "stream ac" in label:
        return "stream_ac"
    if "powerstream" in label:
        return "pstream"
    return "json"


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

    async def discover_devices(self) -> list[DiscoveredDevice]:
        """Read all devices visible to the authenticated EcoFlow account."""

        if not self._token or not self._user_id:
            raise EcoFlowApiError("EcoFlow account is not authenticated")
        timeout = aiohttp.ClientTimeout(total=25)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            response = await self._request_json(
                session,
                "GET",
                "/device/list",
                headers={"authorization": f"Bearer {self._token}", "lang": "en_US"},
                params={"userId": self._user_id},
            )
        raw_devices = response.get("data")
        if isinstance(raw_devices, dict):
            raw_devices = raw_devices.get("list")
        if not isinstance(raw_devices, list):
            raise EcoFlowApiError("EcoFlow device list is incomplete")

        devices: list[DiscoveredDevice] = []
        for raw in raw_devices:
            if not isinstance(raw, dict) or not isinstance(raw.get("sn"), str):
                continue
            product_name = str(raw.get("productName") or "EcoFlow device")
            name = str(raw.get("deviceName") or f"{product_name}-{raw['sn']}")
            devices.append(
                DiscoveredDevice(
                    serial=raw["sn"],
                    name=name,
                    product_name=product_name,
                    device_type=_device_type(product_name, name),
                )
            )
        return devices
