from __future__ import annotations
from dataclasses import dataclass

import logging
from datetime import timedelta
from typing import Callable, Dict, List, Optional
import asyncio

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL,
    STATE_CLASS_TOTAL_INCREASING,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    ENERGY_KILO_WATT_HOUR,
    LIGHT_LUX,
    PERCENTAGE,
    POWER_WATT,
    TEMP_CELSIUS,
    ELECTRIC_POTENTIAL_VOLT,
    ELECTRIC_CURRENT_AMPERE,
    FREQUENCY_HERTZ,
    ENERGY_WATT_HOUR,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_VOLTAGE,
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_POWER_FACTOR,
    DEVICE_CLASS_FREQUENCY,
    DEVICE_CLASS_ENERGY
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from typing_extensions import Final

from .const import (
    CONF_CFG,
    CONF_IP,
    CONF_MAC,
    CONF_TYPE,
    DEFAULT_PARALLEL_UPDATES,
    ICON_POWER_METER,
    SIHAS_PLATFORM_SCHEMA,
)
from .sihas_base import SihasEntity, SihasProxy
from .util import register_put_u32

SCAN_INTERVAL = timedelta(seconds=10)

PARALLEL_UPDATES = DEFAULT_PARALLEL_UPDATES
PLATFORM_SCHEMA = SIHAS_PLATFORM_SCHEMA

AQM_GENERIC_SENSOR_DEFINE: Final = {
    "humidity": {
        "uom": PERCENTAGE,
        "value_handler": lambda r: round(r[1] / 10, 1),
        "device_class": SensorDeviceClass.HUMIDITY,
        "state_class": STATE_CLASS_MEASUREMENT,
        "sub_id": "humidity",
    },
    "temperature": {
        "uom": TEMP_CELSIUS,
        "value_handler": lambda r: round(r[0] / 10, 1),
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": STATE_CLASS_MEASUREMENT,
        "sub_id": "temperature",
    },
    "illuminance": {
        "uom": LIGHT_LUX,
        "value_handler": lambda r: r[6],
        "device_class": SensorDeviceClass.ILLUMINANCE,
        "state_class": STATE_CLASS_MEASUREMENT,
        "sub_id": "illuminance",
    },
    "co2": {
        "uom": CONCENTRATION_PARTS_PER_MILLION,
        "value_handler": lambda r: r[2],
        "device_class": SensorDeviceClass.CO2,
        "state_class": STATE_CLASS_MEASUREMENT,
        "sub_id": "co2",
    },
    "pm25": {
        "uom": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        "value_handler": lambda r: r[3],
        "device_class": SensorDeviceClass.PM25,
        "state_class": STATE_CLASS_MEASUREMENT,
        "sub_id": "pm25",
    },
    "pm10": {
        "uom": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        "value_handler": lambda r: r[4],
        "device_class": SensorDeviceClass.PM10,
        "state_class": STATE_CLASS_MEASUREMENT,
        "sub_id": "pm10",
    },
    "tvoc": {
        "uom": CONCENTRATION_PARTS_PER_BILLION,
        "value_handler": lambda r: r[5],
        "device_class": None,
        "state_class": STATE_CLASS_MEASUREMENT,
        "sub_id": "tvoc",
    },
}

PMM_GENERIC_SENSOR_DEFINE: Final = {
    "cur_energy": {
        "nuom": POWER_WATT,
        "value_handler": lambda r: r[2],
        "device_class": DEVICE_CLASS_POWER,
        "state_class": STATE_CLASS_MEASUREMENT,
        "sub_id": "power",
    },
    "this_month_energy": {
        "nuom": ENERGY_KILO_WATT_HOUR,
        "value_handler": lambda r: r[10] / 100 + r[16] / 1000,
        "device_class": DEVICE_CLASS_ENERGY,
        "state_class": STATE_CLASS_TOTAL,
        "sub_id": "this_month_energy",
    },
    "this_day_energy": {
        "nuom": ENERGY_KILO_WATT_HOUR,
        "value_handler": lambda r: r[8] / 100 + r[16] / 1000,
        "device_class": DEVICE_CLASS_ENERGY,
        "state_class": STATE_CLASS_TOTAL,
        "sub_id": "this_day_energy",
    },
    "voltage": {
        "nuom": ELECTRIC_POTENTIAL_VOLT,
        "value_handler": lambda r: r[0] / 10,
        "device_class": DEVICE_CLASS_VOLTAGE,
        "state_class": STATE_CLASS_MEASUREMENT,
        "sub_id": "voltage",
    },
    "current": {
        "nuom": ELECTRIC_CURRENT_AMPERE,
        "value_handler": lambda r: r[1] / 100,
        "device_class": DEVICE_CLASS_CURRENT,
        "state_class": STATE_CLASS_MEASUREMENT,
        "sub_id": "current",
    },
    "power_factor": {
        "nuom": PERCENTAGE,
        "value_handler": lambda r: r[3] / 10,
        "device_class": DEVICE_CLASS_POWER_FACTOR,
        "state_class": STATE_CLASS_MEASUREMENT,
        "sub_id": "power_factor",
    },
    "frequency": {
        "nuom": FREQUENCY_HERTZ,
        "value_handler": lambda r: r[4] / 10,
        "device_class": DEVICE_CLASS_FREQUENCY,
        "state_class": STATE_CLASS_MEASUREMENT,
        "sub_id": "frequency",
    },
    "total_energy": {
        "nuom": ENERGY_KILO_WATT_HOUR,
        "value_handler": lambda r: (r[41] * 65536 + r[40] + r[16]) / 1000,
        "device_class": DEVICE_CLASS_ENERGY,
        "state_class": STATE_CLASS_TOTAL,
        "sub_id": "total_energy",
    },
    "this_hour_energy": {
        "nuom": ENERGY_KILO_WATT_HOUR,
        "value_handler": lambda r: r[6] / 100 + r[16] / 1000,
        "device_class": DEVICE_CLASS_ENERGY,
        "state_class": STATE_CLASS_TOTAL,
        "sub_id": "this_hour_energy",
    },
    "before_hour_energy": {
        "nuom": ENERGY_KILO_WATT_HOUR,
        "value_handler": lambda r: r[7] / 100,
        "device_class": DEVICE_CLASS_ENERGY,
        "state_class": STATE_CLASS_TOTAL,
        "sub_id": "before_hour_energy",
    },
    "yesterday_energy": {
        "nuom": ENERGY_KILO_WATT_HOUR,
        "value_handler": lambda r: r[9] / 100,
        "device_class": DEVICE_CLASS_ENERGY,
        "state_class": STATE_CLASS_TOTAL,
        "sub_id": "yesterday_energy",
    },
    "last_month_energy": {
        "nuom": ENERGY_KILO_WATT_HOUR,
        "value_handler": lambda r: r[11] / 100,
        "device_class": DEVICE_CLASS_ENERGY,
        "state_class": STATE_CLASS_TOTAL,
        "sub_id": "last_month_energy",
    },
    "two_months_ago_energy": {
        "nuom": ENERGY_KILO_WATT_HOUR,
        "value_handler": lambda r: r[12] / 100,
        "device_class": DEVICE_CLASS_ENERGY,
        "state_class": STATE_CLASS_TOTAL,
        "sub_id": "two_months_ago_energy",
    },
    "this_month_forecast_energy": {
        "nuom": ENERGY_KILO_WATT_HOUR,
        "value_handler": lambda r: r[13] / 100,
        "device_class": DEVICE_CLASS_ENERGY,
        "state_class": STATE_CLASS_TOTAL,
        "sub_id": "this_month_forecast_energy",
    },
}

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_devices: AddEntitiesCallback
) -> None:
    if entry.data[CONF_TYPE] == "PMM":
        device = Device("PMM300", entry)

        pmm = Pmm300(device,
            ip=entry.data[CONF_IP],
            mac=entry.data[CONF_MAC],
            device_type=entry.data[CONF_TYPE],
            config=entry.data[CONF_CFG],
        )
        async_add_devices(pmm.get_sub_entities())

    elif entry.data[CONF_TYPE] == "AQM":
        aqm = Aqm300(
            ip=entry.data[CONF_IP],
            mac=entry.data[CONF_MAC],
            device_type=entry.data[CONF_TYPE],
            config=entry.data[CONF_CFG],
        )
        async_add_devices(aqm.get_sub_entities())


class Device:
    """Dummy roller (device for HA) for Hello World example."""

    def __init__(self, name, config):
        """Init dummy roller."""
        self._id = f"{name}_{config.entry_id}"
        self._name = name
        self._callbacks = set()
        self._loop = asyncio.get_event_loop()
        # Reports if the roller is moving up or down.
        # >0 is up, <0 is down. This very much just for demonstration.

        # Some static information about this device
        self.firmware_version = "1.0"
        self.model = "PMM300"
        self.manufacturer = "sihas"

    @property
    def name(self):
        return self._name

    @property
    def device_id(self):
        """Return ID for roller."""
        return self._id

    def register_callback(self, callback):
        """Register callback, called when Roller changes state."""
        self._callbacks.add(callback)

    def remove_callback(self, callback):
        """Remove previously registered callback."""
        self._callbacks.discard(callback)

    # In a real implementation, this library would call it's call backs when it was
    # notified of any state changeds for the relevant device.
    async def publish_updates(self):
        """Schedule call all registered callbacks."""
        for callback in self._callbacks:
            callback()

    def publish_updates(self):
        """Schedule call all registered callbacks."""
        for callback in self._callbacks:
            callback()

class Pmm300(SihasProxy):
    def __init__(
        self,
        device,
        ip: str,
        mac: str,
        device_type: str,
        config: int,
        name: Optional[str] = None,
    ):
        super().__init__(
            ip=ip,
            mac=mac,
            device_type=device_type,
            config=config,
        )
        self.name = name
        self._device = device

    def get_sub_entities(self) -> List[Entity]:
        return [
            PmmVirtualSensor(self, PMM_GENERIC_SENSOR_DEFINE["cur_energy"]),
            PmmVirtualSensor(self, PMM_GENERIC_SENSOR_DEFINE["this_month_energy"]),
            PmmVirtualSensor(self, PMM_GENERIC_SENSOR_DEFINE["this_day_energy"]),
            PmmVirtualSensor(self, PMM_GENERIC_SENSOR_DEFINE["voltage"]),
            PmmVirtualSensor(self, PMM_GENERIC_SENSOR_DEFINE["current"]),
            PmmVirtualSensor(self, PMM_GENERIC_SENSOR_DEFINE["power_factor"]),
            PmmVirtualSensor(self, PMM_GENERIC_SENSOR_DEFINE["frequency"]),
            PmmVirtualSensor(self, PMM_GENERIC_SENSOR_DEFINE["total_energy"]),
            PmmVirtualSensor(self, PMM_GENERIC_SENSOR_DEFINE["this_hour_energy"]),
            PmmVirtualSensor(self, PMM_GENERIC_SENSOR_DEFINE["before_hour_energy"]),
            PmmVirtualSensor(self, PMM_GENERIC_SENSOR_DEFINE["yesterday_energy"]),
            PmmVirtualSensor(self, PMM_GENERIC_SENSOR_DEFINE["last_month_energy"]),
            PmmVirtualSensor(self, PMM_GENERIC_SENSOR_DEFINE["two_months_ago_energy"]),
            PmmVirtualSensor(self, PMM_GENERIC_SENSOR_DEFINE["this_month_forecast_energy"]),
        ]


class PmmVirtualSensor(SensorEntity):
    _attr_icon = ICON_POWER_METER


    def __init__(self, proxy: Pmm300, conf: Dict) -> None:
        super().__init__()
        self._proxy = proxy
        self._device = proxy._device
        self._attr_available = self._proxy._attr_available
        self._attr_unique_id = f"{proxy.device_type}-{proxy.mac}-{conf['sub_id']}"
        self._attr_native_unit_of_measurement = conf["nuom"]
        self._attr_name = f"{proxy.name} #{conf['sub_id']}" if proxy.name else self._attr_unique_id
        self._attr_device_class = conf["device_class"]
        self._attr_state_class = conf["state_class"]
        self._name = conf['sub_id']

        self.value_handler: Callable = conf["value_handler"]

    def update(self):
        self._proxy.update()
        self._attr_native_value = self.value_handler(self._proxy.registers)
        self._attr_available = self._proxy._attr_available

    @property
    def name(self):
        return self._name

    @property
    def device_info(self):
        """Information about this entity/device."""
        return {
            "identifiers": {("PMM300", self._device.device_id)},
            # If desired, the name for the device could be different to the entity
            "name": self._device.name,
            "sw_version": self._device.firmware_version,
            "model": self._device.model,
            "manufacturer": self._device.manufacturer
        }

class Aqm300(SihasProxy):
    """Representation of AQM-300

    offer below measurements:
        - co2
        - humidity
        - illuminance
        - pm10
        - pm25
        - temperature

    and it will appear seperatly as AqmVirtualSensor
    """

    def __init__(
        self,
        ip: str,
        mac: str,
        device_type: str,
        config: int,
        name: Optional[str] = None,
    ):
        super().__init__(
            ip=ip,
            mac=mac,
            device_type=device_type,
            config=config,
        )
        self.name = name

    def get_sub_entities(self) -> List[Entity]:
        return [
            AqmVirtualSensor(self, AQM_GENERIC_SENSOR_DEFINE["co2"]),
            AqmVirtualSensor(self, AQM_GENERIC_SENSOR_DEFINE["pm25"]),
            AqmVirtualSensor(self, AQM_GENERIC_SENSOR_DEFINE["pm10"]),
            AqmVirtualSensor(self, AQM_GENERIC_SENSOR_DEFINE["tvoc"]),
            AqmVirtualSensor(self, AQM_GENERIC_SENSOR_DEFINE["humidity"]),
            AqmVirtualSensor(self, AQM_GENERIC_SENSOR_DEFINE["illuminance"]),
            AqmVirtualSensor(self, AQM_GENERIC_SENSOR_DEFINE["temperature"]),
        ]


class AqmVirtualSensor(SensorEntity):
    def __init__(self, proxy: Aqm300, conf: Dict) -> None:
        super().__init__()

        self._proxy = proxy
        self._attr_available = self._proxy._attr_available
        self._attr_unique_id = f"{proxy.device_type}-{proxy.mac}-{conf['device_class']}"
        self._attr_native_unit_of_measurement = conf["uom"]
        self._attr_name = f"{proxy.name} #{conf['sub_id']}" if proxy.name else self._attr_unique_id
        self._attr_device_class = conf["device_class"]
        self._attr_state_class = conf["state_class"]

        self.value_handler: Callable = conf["value_handler"]

    def update(self):
        self._proxy.update()
        self._attr_native_value = self.value_handler(self._proxy.registers)
        self._attr_available = self._proxy._attr_available
