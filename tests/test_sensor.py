"""Tests for setup and sensors."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import fixture, url


async def _setup(hass, config_entry):
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def test_sensors(hass: HomeAssistant, mock_api, config_entry):
    await _setup(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    expected = {
        "sensor.south_facade_pv1_power": ("80.0", "W"),
        "sensor.south_facade_pv2_power": ("78.0", "W"),
        "sensor.south_facade_pv1_voltage": ("31.9", "V"),
        "sensor.south_facade_pv2_current": ("2.8", "A"),
        "sensor.south_facade_output_power": ("150.0", "W"),
        "sensor.south_facade_grid_voltage": ("234.1", "V"),
        "sensor.south_facade_grid_frequency": ("50.01", "Hz"),
        "sensor.south_facade_temperature": ("21.2", "°C"),
        "sensor.south_facade_energy_today": ("1.234", "kWh"),
        "sensor.south_facade_total_energy": ("500.391", "kWh"),
        "sensor.south_facade_work_mode": ("Charging", None),
        "sensor.home_power": ("150.0", "W"),
        "sensor.home_total_energy": ("500.4", "kWh"),
    }
    for entity_id, (state, unit) in expected.items():
        current = hass.states.get(entity_id)
        assert current is not None, entity_id
        assert current.state == state, entity_id
        assert current.attributes.get("unit_of_measurement") == unit, entity_id

    # No battery in the fixture, so no battery sensor.
    assert hass.states.get("sensor.south_facade_battery") is None
    # Wi-Fi signal exists but is disabled by default.
    entry = er.async_get(hass).async_get("sensor.south_facade_wi_fi_signal")
    assert entry is not None and entry.disabled


async def test_battery_sensor_when_capacity_reported(
    hass: HomeAssistant, aioclient_mock, config_entry
):
    detail = fixture("device_detail")
    detail["obj"]["deviceDetailInfoVo"].update(soc=64, batTotalCapacity="2.0kWh")
    aioclient_mock.post(url("/user/login"), json=fixture("login"))
    aioclient_mock.post(url("/plant/getPlantPage"), json=fixture("plant_page"))
    aioclient_mock.post(url("/device/getDevicePage"), json=fixture("device_page"))
    aioclient_mock.post(url("/device/getDeviceBySn"), json=detail)
    await _setup(hass, config_entry)
    assert hass.states.get("sensor.south_facade_battery").state == "64.0"


async def test_bad_credentials_start_reauth(hass: HomeAssistant, aioclient_mock, config_entry):
    aioclient_mock.post(url("/user/login"), json=fixture("login_bad_password"))
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert any(f["context"]["source"] == "reauth" for f in flows)


async def test_unload(hass: HomeAssistant, mock_api, config_entry):
    await _setup(hass, config_entry)
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED
