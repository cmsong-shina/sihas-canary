"""Platform for light integration."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, Final, List, cast

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_COLOR_TEMP,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

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
        """
        self._state {
            "onoff": bool,
            ATTR_BRIGHTNESS: int(0~255),
            ATTR_COLOR_TEMP: int(154~500),
        }
        """
        self._state: Dict[str, Any] = {}
        self._number_of_switch: Final = number_of_switch
        self._attr_unique_id = uid
        self._attr_name = f"{name} #{number_of_switch}" if name else uid

        # set Supported Color Modes
        self._attr_supported_color_modes = {COLOR_MODE_BRIGHTNESS}
        if self._proxy.is_colortemperature_changable:
            self._attr_supported_color_modes.add(COLOR_MODE_COLOR_TEMP)

    @property
    def register_offset(self):
        return self._number_of_switch * 2

    @property
    def is_on(self):
        return self._state["onoff"]

    @property
    def brightness(self):
        return self._state[ATTR_BRIGHTNESS]

    @property
    def color_temp(self):
        return self._state[ATTR_COLOR_TEMP]

    def update(self):
        self._proxy.update()
        self._state["onoff"] = self._proxy.registers[self.register_offset] != 0
        self._state[ATTR_BRIGHTNESS] = int(self._proxy.registers[self.register_offset] / 100 * 255)
        color_temp = self._proxy.registers[self.register_offset + 1]
        self._state[ATTR_COLOR_TEMP] = int(346 - (color_temp / 100 * 346)) + 154
        self._attr_available = self._proxy._attr_available

    def turn_on(self, **kwargs):
        opt = {ATTR_BRIGHTNESS: 101}
        if ATTR_BRIGHTNESS in kwargs:
            brightness = cast(int, kwargs.get(ATTR_BRIGHTNESS))
            opt[ATTR_BRIGHTNESS] = int(brightness / 255 * 100)

        if ATTR_COLOR_TEMP in kwargs:
            # 색온도는 154-500의 범위 안에서 변환한다
            color_temp = cast(int, kwargs.get(ATTR_COLOR_TEMP))
            opt[ATTR_COLOR_TEMP] = int((346 - (color_temp - 154)) / 346 * 100)

        self._set_switch(opt)

    def turn_off(self, **kwargs):
        self._set_switch({ATTR_BRIGHTNESS: 0})

    def _set_switch(self, option: Dict):
        """
        option {
            ATTR_BRIGHTNESS?: int, // 밝기, 0~100
            ATTR_COLOR_TEMP?: int, // 색온도
        }
        """
        if ATTR_BRIGHTNESS in option:
            self._proxy.command(self.register_offset, option[ATTR_BRIGHTNESS])
        if ATTR_COLOR_TEMP in option:
            self._proxy.command(self.register_offset + 1, option[ATTR_COLOR_TEMP])
