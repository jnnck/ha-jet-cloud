"""Tests for the API client (no Home Assistant involved)."""

from datetime import date

import aiohttp
import pytest
from aioresponses import aioresponses

from custom_components.jet_cloud.api import (
    JetCloudAuthError,
    JetCloudClient,
    JetCloudConnectionError,
    hash_password,
    parse_value,
)

from .common import fixture, url


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("234.1V", 234.1),
        ("0.005kWH", 0.005),
        ("21.2℃", 21.2),
        ("-73", -73.0),
        (7, 7.0),
        ("--", None),
        ("", None),
        (None, None),
        ("Normal", "Normal"),
        ("1.3.2.1.6", "1.3.2.1.6"),
    ],
)
def test_parse_value(raw, expected):
    assert parse_value(raw) == expected


def test_hash_password_is_md5_hex():
    assert hash_password("secret") == "5ebe2294ecd0e0f08eab7690d2a6ee69"


async def test_full_read():
    async with aiohttp.ClientSession() as session:
        client = JetCloudClient(session, "user@example.com", "hash")
        with aioresponses() as mock:
            mock.post(url("/user/login"), payload=fixture("login"))
            mock.post(url("/plant/getPlantPage"), payload=fixture("plant_page"))
            mock.post(url("/device/getDevicePage"), payload=fixture("device_page"))
            mock.post(url("/device/getDeviceBySn"), payload=fixture("device_detail"))

            plants = await client.get_plants()
            devices = await client.get_devices(plants[0].id)
            await client.update_device_detail(devices[0], date(2026, 10, 26))

            login_call = mock.requests[("POST", aiohttp.client.URL(url("/user/login")))][0]
            detail_call = mock.requests[("POST", aiohttp.client.URL(url("/device/getDeviceBySn")))][0]

    assert login_call.kwargs["json"]["password"] == "hash"
    assert login_call.kwargs["headers"]["Accept-Language"] == "en-US"
    assert detail_call.kwargs["headers"]["token"] == "test-token-1"
    assert detail_call.kwargs["data"] == {
        "deviceType": 57,
        "sn": "JM0000000TEST0001",
        "time": "2026-10-26",
    }

    assert plants[0].id == 12345
    assert plants[0].total_energy == 500.4
    device = devices[0]
    assert device.name == "South facade"
    assert device.online is True
    assert device.total_energy == 500.391
    assert device.wifi_signal == -73
    assert device.values["PV1 Power"] == 80.0
    assert device.values["PV2 Voltage"] == 28.0
    assert device.values["Power"] == 150.0
    assert device.values["Fault Indicator 1"] == "Normal"
    assert "datalog sn" not in device.values
    assert device.work_mode == "Charging"
    assert device.has_battery is False
    assert device.battery_soc is None


async def test_relogin_on_expired_session():
    async with aiohttp.ClientSession() as session:
        client = JetCloudClient(session, "user@example.com", "hash")
        with aioresponses() as mock:
            mock.post(url("/user/login"), payload=fixture("login"), repeat=True)
            mock.post(url("/plant/getPlantPage"), payload=fixture("session_expired"))
            mock.post(url("/plant/getPlantPage"), payload=fixture("plant_page"))
            plants = await client.get_plants()
            logins = len(mock.requests[("POST", aiohttp.client.URL(url("/user/login")))])

    assert plants[0].name == "Home"
    assert logins == 2


async def test_bad_password_raises_auth_error():
    async with aiohttp.ClientSession() as session:
        client = JetCloudClient(session, "user@example.com", "wrong")
        with aioresponses() as mock:
            mock.post(url("/user/login"), payload=fixture("login_bad_password"))
            with pytest.raises(JetCloudAuthError, match="password is incorrect"):
                await client.login()


async def test_connection_error():
    async with aiohttp.ClientSession() as session:
        client = JetCloudClient(session, "user@example.com", "hash")
        with aioresponses() as mock:
            mock.post(url("/user/login"), exception=aiohttp.ClientConnectionError("down"))
            with pytest.raises(JetCloudConnectionError):
                await client.login()
