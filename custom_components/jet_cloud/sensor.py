"""Sensors for JET Cloud plants and devices."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import Device, Plant
from .const import DOMAIN
from .coordinator import JetCloudConfigEntry, JetCloudCoordinator

PARALLEL_UPDATES = 0

_PV_LABEL = re.compile(r"^PV(\d+) (Power|Voltage|Current)$")


@dataclass(frozen=True, kw_only=True)
class DeviceSensorDescription(SensorEntityDescription):
    value_fn: Callable[[Device], float | str | None]


@dataclass(frozen=True, kw_only=True)
class PlantSensorDescription(SensorEntityDescription):
    value_fn: Callable[[Plant], float | str | None]


def _label(label: str) -> Callable[[Device], float | str | None]:
    return lambda device: device.values.get(label)


POWER = {
    "device_class": SensorDeviceClass.POWER,
    "native_unit_of_measurement": UnitOfPower.WATT,
    "state_class": SensorStateClass.MEASUREMENT,
}
VOLTAGE = {
    "device_class": SensorDeviceClass.VOLTAGE,
    "native_unit_of_measurement": UnitOfElectricPotential.VOLT,
    "state_class": SensorStateClass.MEASUREMENT,
}
CURRENT = {
    "device_class": SensorDeviceClass.CURRENT,
    "native_unit_of_measurement": UnitOfElectricCurrent.AMPERE,
    "state_class": SensorStateClass.MEASUREMENT,
}
ENERGY = {
    "device_class": SensorDeviceClass.ENERGY,
    "native_unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
    "state_class": SensorStateClass.TOTAL_INCREASING,
}

# Readings keyed by the English label the API returns in displayMap.
LABEL_SENSORS: dict[str, DeviceSensorDescription] = {
    "Power": DeviceSensorDescription(
        key="grid_power", translation_key="grid_power", value_fn=_label("Power"), **POWER
    ),
    "Voltage": DeviceSensorDescription(
        key="grid_voltage", translation_key="grid_voltage", value_fn=_label("Voltage"), **VOLTAGE
    ),
    "Current": DeviceSensorDescription(
        key="grid_current", translation_key="grid_current", value_fn=_label("Current"), **CURRENT
    ),
    "AC Frequency": DeviceSensorDescription(
        key="grid_frequency",
        translation_key="grid_frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_label("AC Frequency"),
    ),
    "Temperature 1": DeviceSensorDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_label("Temperature 1"),
    ),
}

DEVICE_SENSORS: tuple[DeviceSensorDescription, ...] = (
    DeviceSensorDescription(
        key="energy_today",
        translation_key="energy_today",
        value_fn=lambda d: d.today_energy,
        **ENERGY,
    ),
    DeviceSensorDescription(
        key="energy_total",
        translation_key="energy_total",
        value_fn=lambda d: d.total_energy,
        **ENERGY,
    ),
    DeviceSensorDescription(
        key="work_mode",
        translation_key="work_mode",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.work_mode,
    ),
    DeviceSensorDescription(
        key="wifi_signal",
        translation_key="wifi_signal",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.wifi_signal,
    ),
)

BATTERY_SENSOR = DeviceSensorDescription(
    key="battery_soc",
    device_class=SensorDeviceClass.BATTERY,
    native_unit_of_measurement=PERCENTAGE,
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda d: d.battery_soc,
)

PLANT_SENSORS: tuple[PlantSensorDescription, ...] = (
    PlantSensorDescription(
        key="plant_power", translation_key="plant_power", value_fn=lambda p: p.power, **POWER
    ),
    PlantSensorDescription(
        key="plant_energy_today",
        translation_key="energy_today",
        value_fn=lambda p: p.today_energy,
        **ENERGY,
    ),
    PlantSensorDescription(
        key="plant_energy_total",
        translation_key="energy_total",
        value_fn=lambda p: p.total_energy,
        **ENERGY,
    ),
)

PV_UNITS = {"Power": POWER, "Voltage": VOLTAGE, "Current": CURRENT}


def _pv_description(label: str) -> DeviceSensorDescription | None:
    """Build a description for 'PV<n> Power|Voltage|Current' labels."""
    if not (match := _PV_LABEL.match(label)):
        return None
    number, kind = match.groups()
    return DeviceSensorDescription(
        key=f"pv{number}_{kind.lower()}",
        translation_key=f"pv_{kind.lower()}",
        translation_placeholders={"pv": number},
        value_fn=_label(label),
        **PV_UNITS[kind],
    )


def _device_descriptions(device: Device) -> list[DeviceSensorDescription]:
    descriptions = list(DEVICE_SENSORS)
    for label in device.values:
        if label in LABEL_SENSORS:
            descriptions.append(LABEL_SENSORS[label])
        elif pv := _pv_description(label):
            descriptions.append(pv)
    if device.has_battery:
        descriptions.append(BATTERY_SENSOR)
    return descriptions


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JetCloudConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def add_new_entities() -> None:
        entities: list[SensorEntity] = []
        for plant in coordinator.data.plants.values():
            for description in PLANT_SENSORS:
                entity = PlantSensor(coordinator, plant.id, description)
                if entity.unique_id not in known:
                    known.add(entity.unique_id)
                    entities.append(entity)
        for device in coordinator.data.devices.values():
            for description in _device_descriptions(device):
                entity = DeviceSensor(coordinator, device.sn, description)
                if entity.unique_id not in known:
                    known.add(entity.unique_id)
                    entities.append(entity)
        if entities:
            async_add_entities(entities)

    add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(add_new_entities))


class PlantSensor(CoordinatorEntity[JetCloudCoordinator], SensorEntity):
    """A plant-level total."""

    _attr_has_entity_name = True
    entity_description: PlantSensorDescription

    def __init__(
        self,
        coordinator: JetCloudCoordinator,
        plant_id: int,
        description: PlantSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._plant_id = plant_id
        self._attr_unique_id = f"plant_{plant_id}_{description.key}"
        plant = coordinator.data.plants[plant_id]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"plant_{plant_id}")},
            name=plant.name,
            manufacturer="JET Cloud",
            model="Plant",
        )

    @property
    def available(self) -> bool:
        return super().available and self._plant_id in self.coordinator.data.plants

    @property
    def native_value(self) -> float | str | None:
        return self.entity_description.value_fn(self.coordinator.data.plants[self._plant_id])


class DeviceSensor(CoordinatorEntity[JetCloudCoordinator], SensorEntity):
    """A reading of a single inverter."""

    _attr_has_entity_name = True
    entity_description: DeviceSensorDescription

    def __init__(
        self,
        coordinator: JetCloudCoordinator,
        sn: str,
        description: DeviceSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._sn = sn
        self._attr_unique_id = f"{sn}_{description.key}"
        device = coordinator.data.devices[sn]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, sn)},
            name=device.name,
            manufacturer="JET Cloud",
            serial_number=sn,
            sw_version=_str(device.values.get("Monitoring Software Version Number")),
            hw_version=_str(device.values.get("Monitoring Hardware Version Number")),
            via_device=(DOMAIN, f"plant_{device.plant_id}"),
        )

    @property
    def available(self) -> bool:
        return super().available and self._sn in self.coordinator.data.devices

    @property
    def native_value(self) -> float | str | None:
        value = self.entity_description.value_fn(self.coordinator.data.devices[self._sn])
        # A numeric sensor must never get a text state from the API.
        if self.entity_description.native_unit_of_measurement and isinstance(value, str):
            return None
        return value


def _str(value: float | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)
