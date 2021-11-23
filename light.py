"""Platform for light integration."""
from __future__ import annotations
from datetime import timedelta

from typing import List

from homeassistant.components.light import COLOR_MODE_BRIGHTNESS, COLOR_MODE_COLOR_TEMP, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    CONF_CFG,
    CONF_IP,
    CONF_MAC,
    CONF_NAME,
    CONF_TYPE,
    DEFAULT_PARALLEL_UPDATES,
    ICON_LIGHT_BULB,
    SIHAS_PLATFORM_SCHEMA,
)
from .sihas_base import SihasProxy

SCAN_INTERVAL = timedelta(seconds=5)

PARALLEL_UPDATES = DEFAULT_PARALLEL_UPDATES
PLATFORM_SCHEMA = SIHAS_PLATFORM_SCHEMA


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    if entry.data[CONF_TYPE] in ["STM", "SBM"]:
        stm_sbm = StmSbm300(
            ip=entry.data[CONF_IP],
            mac=entry.data[CONF_MAC],
            device_type=entry.data[CONF_TYPE],
            config=entry.data[CONF_CFG],
            name=entry.data[CONF_NAME],
        )
        async_add_entities(stm_sbm.get_sub_entities())

    if entry.data[CONF_TYPE] == "SDM":
        sdm = Sdm300(
            ip=entry.data[CONF_IP],
            mac=entry.data[CONF_MAC],
            device_type=entry.data[CONF_TYPE],
            config=entry.data[CONF_CFG],
            name=entry.data[CONF_NAME],
        )
        async_add_entities(sdm.get_sub_entities())


class StmSbm300(SihasProxy):
    """Representation of an STM-300 and SBM-300"""

    def __init__(
        self,
        ip: str,
        mac: str,
        device_type: str,
        config: int,
        name: str = None,
    ):
        super().__init__(
            ip=ip,
            mac=mac,
            device_type=device_type,
            config=config,
        )
        self.name = name

    def get_sub_entities(self) -> List[Entity]:
        return [StmSbmVirtualLight(self, i, self.name) for i in range(0, self.config)]


class StmSbmVirtualLight(LightEntity):
    _attr_icon = ICON_LIGHT_BULB

    def __init__(self, stbm: StmSbm300, number_of_switch: int, name: str = None):
        super().__init__()

        uid = f"{stbm.device_type}-{stbm.mac}-{number_of_switch}"

        self._proxy = stbm
        self._attr_available = self._proxy._attr_available
        self._state = None
        self._number_of_switch = number_of_switch
        self._attr_unique_id = uid
        self._attr_name = f"{name}-{number_of_switch}" if name else uid

    @property
    def is_on(self):
        return self._state

    def update(self):
        self._proxy.update()
        self._state = self._proxy.registers[self._number_of_switch] == 1
        self._attr_available = self._proxy._attr_available

    def turn_on(self, **kwargs):
        self._set_switch(True)

    def turn_off(self, **kwargs):
        self._set_switch(False)

    def _set_switch(self, onoff: bool):
        val = 1 if onoff else 0
        self._proxy.command(self._number_of_switch, val)


class Sdm300(SihasProxy):
    """Representation of an STM-300 and SBM-300"""

    def __init__(
        self,
        ip: str,
        mac: str,
        device_type: str,
        config: int,
        name: str = None,
    ):
        super().__init__(
            ip=ip,
            mac=mac,
            device_type=device_type,
            config=config,
        )
        self.name = name

    def get_sub_entities(self) -> List[Entity]:
        return [SdmVirtualLight(self, i, self.name) for i in range(0, self.config % 8)]

    @property
    def is_colortemperature_changable(self) -> bool:
        return self.config > 0x08


class SdmVirtualLight(LightEntity):
    _attr_icon = ICON_LIGHT_BULB

    def __init__(
        self,
        sdm: Sdm300,
        number_of_switch: int,
        name: str = None,
    ):
        super().__init__()

        uid = f"{sdm.device_type}-{sdm.mac}-{number_of_switch}"

        self._proxy = sdm
        self._attr_available = self._proxy._attr_available
        self._state = None
        self._number_of_switch = number_of_switch
        self._attr_unique_id = uid
        self._attr_name = f"{name} #{number_of_switch}" if name else uid

        # set Supported Color Modes
        scm = {COLOR_MODE_BRIGHTNESS}
        if self._proxy.is_colortemperature_changable:
            scm.add(COLOR_MODE_COLOR_TEMP)
        self._attr_supported_color_modes = scm

    # TODO: 레지스터 맞게 설정, 메서드 작성
    @property
    def is_on(self):
        return self._state

    def update(self):
        self._proxy.update()
        self._state = self._proxy.registers[self._number_of_switch] == 1
        self._attr_available = self._proxy._attr_available

    def turn_on(self, **kwargs):
        self._set_switch(True)

    def turn_off(self, **kwargs):
        self._set_switch(False)

    def _set_switch(self, onoff: bool):
        val = 1 if onoff else 0
        self._proxy.command(self._number_of_switch, val)
