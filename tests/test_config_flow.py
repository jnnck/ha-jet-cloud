"""Tests for the config flow."""

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.jet_cloud.const import CONF_PASSWORD_HASH, DOMAIN

from .common import fixture, url


async def test_user_flow_creates_entry_with_hashed_password(hass: HomeAssistant, mock_api):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"email": "User@Example.com", "password": "secret"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_PASSWORD_HASH] == "5ebe2294ecd0e0f08eab7690d2a6ee69"
    assert "password" not in result["data"]
    assert result["result"].unique_id == "user@example.com"


async def test_user_flow_invalid_auth(hass: HomeAssistant, aioclient_mock):
    aioclient_mock.post(url("/user/login"), json=fixture("login_bad_password"))
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"email": "user@example.com", "password": "wrong"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_cannot_connect(hass: HomeAssistant, aioclient_mock):
    aioclient_mock.post(url("/user/login"), status=502)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"email": "user@example.com", "password": "secret"}
    )
    assert result["errors"] == {"base": "cannot_connect"}


async def test_duplicate_account_aborts(hass: HomeAssistant, mock_api, config_entry):
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"email": "user@example.com", "password": "secret"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_updates_hash(hass: HomeAssistant, mock_api, config_entry):
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"password": "new-password"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data[CONF_PASSWORD_HASH] != "5ebe2294ecd0e0f08eab7690d2a6ee69"
