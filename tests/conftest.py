"""Fixtures for JET Cloud tests."""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.jet_cloud.api import DEFAULT_HOST, DEFAULT_PROJECT_TYPE
from custom_components.jet_cloud.const import (
    CONF_HOST,
    CONF_PASSWORD_HASH,
    CONF_PROJECT_TYPE,
    DOMAIN,
)

from .common import fixture, url


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def mock_api(aioclient_mock):
    aioclient_mock.post(url("/user/login"), json=fixture("login"))
    aioclient_mock.post(url("/plant/getPlantPage"), json=fixture("plant_page"))
    aioclient_mock.post(url("/device/getDevicePage"), json=fixture("device_page"))
    aioclient_mock.post(url("/device/getDeviceBySn"), json=fixture("device_detail"))
    return aioclient_mock


@pytest.fixture
def config_entry():
    return MockConfigEntry(
        domain=DOMAIN,
        title="user@example.com",
        unique_id="user@example.com",
        data={
            "email": "user@example.com",
            CONF_PASSWORD_HASH: "5ebe2294ecd0e0f08eab7690d2a6ee69",
            CONF_HOST: DEFAULT_HOST,
            CONF_PROJECT_TYPE: DEFAULT_PROJECT_TYPE,
        },
    )
