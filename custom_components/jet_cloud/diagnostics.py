"""Diagnostics with personal data removed."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_EMAIL
from homeassistant.core import HomeAssistant

from .const import CONF_PASSWORD_HASH
from .coordinator import JetCloudConfigEntry

TO_REDACT = {CONF_EMAIL, CONF_PASSWORD_HASH, "id", "sn", "name"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: JetCloudConfigEntry
) -> dict[str, Any]:
    data = entry.runtime_data.data
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "plants": [async_redact_data(asdict(p), TO_REDACT) for p in data.plants.values()],
        "devices": [async_redact_data(asdict(d), TO_REDACT) for d in data.devices.values()],
    }
