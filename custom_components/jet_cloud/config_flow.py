"""Config flow for JET Cloud."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    DEFAULT_HOST,
    DEFAULT_PROJECT_TYPE,
    JetCloudAuthError,
    JetCloudClient,
    JetCloudConnectionError,
    hash_password,
)
from .const import CONF_HOST, CONF_PASSWORD_HASH, CONF_PROJECT_TYPE, DOMAIN

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Optional(CONF_PROJECT_TYPE, default=DEFAULT_PROJECT_TYPE): int,
    }
)
REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})


class JetCloudConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for JET Cloud."""

    VERSION = 1

    async def _validate(self, data: dict[str, Any]) -> str | None:
        """Try to log in; return an error key or None."""
        client = JetCloudClient(
            async_get_clientsession(self.hass),
            data[CONF_EMAIL],
            data[CONF_PASSWORD_HASH],
            host=data[CONF_HOST],
            project_type=data[CONF_PROJECT_TYPE],
        )
        try:
            await client.login()
        except JetCloudAuthError:
            return "invalid_auth"
        except JetCloudConnectionError:
            return "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected error during login")
            return "unknown"
        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            email = user_input[CONF_EMAIL].strip()
            await self.async_set_unique_id(email.lower())
            self._abort_if_unique_id_configured()
            data = {
                CONF_EMAIL: email,
                CONF_PASSWORD_HASH: hash_password(user_input[CONF_PASSWORD]),
                CONF_HOST: user_input[CONF_HOST],
                CONF_PROJECT_TYPE: user_input[CONF_PROJECT_TYPE],
            }
            if not (error := await self._validate(data)):
                return self.async_create_entry(title=email, data=data)
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {
                **entry.data,
                CONF_PASSWORD_HASH: hash_password(user_input[CONF_PASSWORD]),
            }
            if not (error := await self._validate(data)):
                return self.async_update_reload_and_abort(entry, data=data)
            errors["base"] = error

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            description_placeholders={"email": entry.data[CONF_EMAIL]},
            errors=errors,
        )
