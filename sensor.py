from __future__ import annotations
from dataclasses import dataclass

from datetime import timedelta
from typing import Callable, Dict, List, Optional

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    DEVICE_CLASS_CO2,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_PM10,
    DEVICE_CLASS_PM25,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_VOLATILE_ORGANIC_COMPOUNDS,
    ENERGY_WATT_HOUR,
    LIGHT_LUX,
    PERCENTAGE,
    POWER_WATT,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
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
from .sihas_base import SihasProxy
from .util import register_put_u32

SCAN_INTERVAL = timedelta(seconds=5)

PARALLEL_UPDATES = DEFAULT_PARALLEL_UPDATES
PLATFORM_SCHEMA = SIHAS_PLATFORM_SCHEMA

AQM_GENERIC_SENSOR_DEFINE: Final = {
    "humidity": {
        "uom": PERCENTAGE,
        "value_handler": lambda r: round(r[1] / 10, 1),
        "device_class": DEVICE_CLASS_HUMIDITY,
        "state_class": STATE_CLASS_MEASUREMENT,
        "sub_id": "humidity",
    },
    "temperature": {
        "uom": TEMP_CELSIUS,
        "value_handler": lambda r: round(r[0] / 10, 1),
        "device_class": DEVICE_CLASS_TEMPERATURE,
        "state_class": STATE_CLASS_MEASUREMENT,
        "sub_id": "temperature",
    },
    "illuminance": {
        "uom": LIGHT_LUX,
        "value_handler": lambda r: r[6],
        "device_class": DEVICE_CLASS_ILLUMINANCE,
        "state_class": STATE_CLASS_MEASUREMENT,
        "sub_id": "illuminance",
    },
    "co2": {
        "uom": CONCENTRATION_PARTS_PER_MILLION,
        "value_handler": lambda r: r[2],
        "device_class": DEVICE_CLASS_CO2,
        "state_class": STATE_CLASS_MEASUREMENT,
        "sub_id": "co2",
    },
    "pm25": {
        "uom": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        "value_handler": lambda r: r[3],
        "device_class": DEVICE_CLASS_PM25,
        "state_class": STATE_CLASS_MEASUREMENT,
        "sub_id": "pm25",
    },
    "pm10": {
        "uom": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        "value_handler": lambda r: r[4],
        "device_class": DEVICE_CLASS_PM10,
        "state_class": STATE_CLASS_MEASUREMENT,
        "sub_id": "pm10",
    },
    "tvoc": {
        "uom": CONCENTRATION_PARTS_PER_BILLION,
        "value_handler": lambda r: r[5],
        "device_class": DEVICE_CLASS_VOLATILE_ORGANIC_COMPOUNDS,
        "state_class": STATE_CLASS_MEASUREMENT,
        "sub_id": "tvoc",
    },
}

PMM_KEY_POWER: Final = "power"
PMM_KEY_THIS_MONTH_ENERGY: Final = "this_month_energy"
PMM_KEY_THIS_DAY_ENERGY: Final = "this_day_energy"
PMM_KEY_TOTAL: Final = "total_energy"


@dataclass
class PmmConfig:
    nuom: str
    value_handler: Callable
    device_class: str
    state_class: str
    sub_id: str


PMM_GENERIC_SENSOR_DEFINE: Final = {
    PMM_KEY_POWER: PmmConfig(
        nuom=POWER_WATT,
        value_handler=lambda r: r[2],
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
        sub_id=PMM_KEY_POWER,
    ),
    PMM_KEY_THIS_MONTH_ENERGY: PmmConfig(
        nuom=ENERGY_WATT_HOUR,
        value_handler=lambda r: r[10] * 10,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL,
        sub_id=PMM_KEY_THIS_MONTH_ENERGY,
    ),
    PMM_KEY_THIS_DAY_ENERGY: PmmConfig(
        nuom=ENERGY_WATT_HOUR,
        value_handler=lambda r: r[8] * 10,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL,
        sub_id=PMM_KEY_THIS_DAY_ENERGY,
    ),
    PMM_KEY_TOTAL: PmmConfig(
        nuom=ENERGY_WATT_HOUR,
        value_handler=lambda r: register_put_u32(r[40], r[41]),
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        sub_id=PMM_KEY_TOTAL,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    if entry.data[CONF_TYPE] == "PMM":
        pmm = Pmm300(
            ip=entry.data[CONF_IP],
            mac=entry.data[CONF_MAC],
            device_type=entry.data[CONF_TYPE],
            config=entry.data[CONF_CFG],
        )
        async_add_entities(pmm.get_sub_entities())

    elif entry.data[CONF_TYPE] == "AQM":
        aqm = Aqm300(
            ip=entry.data[CONF_IP],
            mac=entry.data[CONF_MAC],
            device_type=entry.data[CONF_TYPE],
            config=entry.data[CONF_CFG],
        )
        async_add_entities(aqm.get_sub_entities())


class Pmm300(SihasProxy):
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
            PmmVirtualSensor(self, PMM_GENERIC_SENSOR_DEFINE[PMM_KEY_POWER]),
            PmmVirtualSensor(self, PMM_GENERIC_SENSOR_DEFINE[PMM_KEY_THIS_MONTH_ENERGY]),
            PmmVirtualSensor(self, PMM_GENERIC_SENSOR_DEFINE[PMM_KEY_THIS_DAY_ENERGY]),
            PmmVirtualSensor(self, PMM_GENERIC_SENSOR_DEFINE[PMM_KEY_TOTAL]),
        ]


class PmmVirtualSensor(SensorEntity):
    _attr_icon = ICON_POWER_METER

    def __init__(self, proxy: Pmm300, conf: PmmConfig) -> None:
        super().__init__()
        self._proxy = proxy
        self._attr_available = self._proxy._attr_available
        self._attr_unique_id = f"{proxy.device_type}-{proxy.mac}-{conf.sub_id}"
        self._attr_native_unit_of_measurement = conf.nuom
        self._attr_name = f"{proxy.name} #{conf.sub_id}" if proxy.name else self._attr_unique_id
        self._attr_device_class = conf.device_class
        self._attr_state_class = conf.state_class

        self.value_handler: Callable = conf.value_handler

    def update(self):
        self._proxy.update()
        self._attr_native_value = self.value_handler(self._proxy.registers)
        self._attr_available = self._proxy._attr_available


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
