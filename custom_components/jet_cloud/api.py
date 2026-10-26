"""Minimal async client for the JET Cloud API (server-jy.ai-ec.cloud).

Reverse-engineered from the JET Cloud mobile app. See API.md for details.
This module has no Home Assistant imports so it can be reused elsewhere.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import aiohttp

DEFAULT_HOST = "https://server-jy.ai-ec.cloud:8443"
DEFAULT_PROJECT_TYPE = 10
# The server rejects logins without an app version; this is the version the
# official app sent when the API was documented.
APP_VERSION = "1.260828.2"

RESULT_OK = 0
RESULT_SESSION_EXPIRED = 10000

_NUMBER_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*[^\d\s]*\s*$")


class JetCloudError(Exception):
    """Generic API error."""


class JetCloudAuthError(JetCloudError):
    """Credentials were rejected."""


class JetCloudConnectionError(JetCloudError):
    """The API could not be reached."""


def hash_password(password: str) -> str:
    """Return the password the way the app sends it: unsalted MD5 hex."""
    return hashlib.md5(password.encode()).hexdigest()


def parse_value(raw: Any) -> float | str | None:
    """Turn API strings like '234.1V' or '0.005kWH' into numbers.

    Values without a number ('Normal') are returned as-is, '--' and empty
    strings become None.
    """
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw).strip()
    if text in ("", "--"):
        return None
    if match := _NUMBER_RE.match(text):
        return float(match.group(1))
    return text


@dataclass
class Plant:
    """A plant (installation) in the account."""

    id: int
    name: str
    power: float | None
    today_energy: float | None
    total_energy: float | None
    total_revenue: float | None
    currency: str | None


@dataclass
class Device:
    """A device (inverter) with its latest readings."""

    sn: str
    name: str
    device_type: int
    plant_id: int
    online: bool
    today_energy: float | None = None
    total_energy: float | None = None
    wifi_signal: float | None = None
    work_mode: str | None = None
    battery_soc: float | None = None
    has_battery: bool = False
    # English label from the API (e.g. "PV1 Power") -> parsed value
    values: dict[str, float | str | None] = field(default_factory=dict)


class JetCloudClient:
    """Talks to the JET Cloud backend with a logged-in token."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        email: str,
        password_hash: str,
        host: str = DEFAULT_HOST,
        project_type: int = DEFAULT_PROJECT_TYPE,
    ) -> None:
        self._session = session
        self._email = email
        self._password_hash = password_hash
        self._host = host.rstrip("/")
        self._project_type = project_type
        self._token: str | None = None

    def _headers(self) -> dict[str, str]:
        headers = {
            "InterfaceType": "2",
            "projectType": str(self._project_type),
            "appVersion": APP_VERSION,
            # Labels in device data follow this header; always ask for English.
            "Accept-Language": "en-US",
        }
        if self._token:
            headers["token"] = self._token
        return headers

    async def _call(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            async with self._session.request(
                method,
                f"{self._host}{path}",
                headers=self._headers(),
                timeout=aiohttp.ClientTimeout(total=30),
                **kwargs,
            ) as resp:
                resp.raise_for_status()
                return await resp.json(content_type=None)
        except (TimeoutError, aiohttp.ClientError) as err:
            raise JetCloudConnectionError(str(err)) from err

    async def login(self) -> None:
        """Log in and store the session token."""
        self._token = None
        body = await self._call(
            "POST",
            "/user/login",
            json={
                "email": self._email,
                "password": self._password_hash,
                "phoneOs": "2",
                "phoneModel": "homeassistant",
                "appVersion": APP_VERSION,
            },
        )
        token = (body.get("obj") or {}).get("token")
        if body.get("result") != RESULT_OK or not token:
            raise JetCloudAuthError(body.get("msg") or "Login failed")
        self._token = token

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Call an authenticated endpoint, logging in again once if needed."""
        if self._token is None:
            await self.login()
        body = await self._call(method, path, **kwargs)
        if body.get("result") == RESULT_SESSION_EXPIRED:
            await self.login()
            body = await self._call(method, path, **kwargs)
        if body.get("result") == RESULT_SESSION_EXPIRED:
            raise JetCloudAuthError(body.get("msg") or "Session expired")
        if body.get("result") != RESULT_OK:
            raise JetCloudError(f"{path}: {body.get('msg')}")
        return body.get("obj")

    async def get_plants(self) -> list[Plant]:
        obj = await self._request(
            "POST", "/plant/getPlantPage", json={"pageNow": 1, "pageSize": 100}
        )
        return [
            Plant(
                id=item["id"],
                name=item.get("plantName") or str(item["id"]),
                power=parse_value(item.get("pvPower")),
                today_energy=parse_value(item.get("todayEnergy")),
                total_energy=parse_value(item.get("totalEnergy")),
                total_revenue=parse_value(item.get("totalRevenue")),
                currency=item.get("incomeUnitText") or item.get("currencySymbol"),
            )
            for item in (obj or {}).get("dataList") or []
        ]

    async def get_devices(self, plant_id: int) -> list[Device]:
        obj = await self._request(
            "POST",
            "/device/getDevicePage",
            json={
                "pageNow": 1,
                "pageSize": 100,
                "map": {"searchField": "", "type": 1, "plantId": plant_id, "statusType": -1},
            },
        )
        return [
            Device(
                sn=item["deviceSn"],
                name=item.get("deviceName") or item["deviceSn"],
                device_type=item["deviceType"],
                plant_id=plant_id,
                online=item.get("deviceStatus") == 1,
                today_energy=parse_value(item.get("todayEnergy")),
                total_energy=parse_value(item.get("totalEnergy")),
                wifi_signal=parse_value(item.get("wifiSignal")),
            )
            for item in (obj or {}).get("dataList") or []
        ]

    async def update_device_detail(self, device: Device, day: date) -> None:
        """Fill in live readings (per-PV values, grid, battery) on a device."""
        obj = await self._request(
            "POST",
            "/device/getDeviceBySn",
            data={
                "deviceType": device.device_type,
                "sn": device.sn,
                "time": day.isoformat(),
            },
        )
        obj = obj or {}
        device.values = {
            label: parse_value(raw)
            for label, raw in (obj.get("displayMap") or {}).items()
            if label != "datalog sn"
        }
        mode = obj.get("devicePowerWorkModeText")
        device.work_mode = None if mode in (None, "", "--") else mode
        info = obj.get("deviceDetailInfoVo") or {}
        capacity = parse_value(info.get("batTotalCapacity"))
        device.has_battery = isinstance(capacity, float) and capacity > 0
        device.battery_soc = parse_value(info.get("soc")) if device.has_battery else None
