"""Client for obtaining EcoFlow private-account MQTT credentials."""

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


class EcoFlowAccountClient:
    """Authenticate an EcoFlow account and obtain private MQTT credentials."""

    def __init__(self, api_host: str = DEFAULT_API_HOST) -> None:
        self._base_url = f"https://{api_host.strip().rstrip('/')}"

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
            user = login_data.get("user") if isinstance(login_data, dict) else None
            token = login_data.get("token") if isinstance(login_data, dict) else None
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
        try:
            port = int(cert_data.get("port") or DEFAULT_PORT)
        except (TypeError, ValueError):
            port = DEFAULT_PORT
        return EcoFlowCredentials(
            user_id=user_id,
            mqtt_username=username,
            mqtt_password=mqtt_password,
            client_id=f"ANDROID_{uuid.uuid4()}_{user_id}",
            broker=broker.rstrip("/"),
            port=port,
        )
