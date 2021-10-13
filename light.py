"""Platform for light integration."""
from __future__ import annotations

from typing import List

from homeassistant.components.light import LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_CFG, CONF_IP, CONF_MAC, CONF_TYPE, ICON_LIGHT_BULB, SIHAS_PLATFORM_SCHEMA
from .sihas_base import SihasProxy

PLATFORM_SCHEMA = SIHAS_PLATFORM_SCHEMA


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    if config[CONF_TYPE] in ["STM", "SBM"]:
        stm_sbm = StmSbm300(
            ip=config[CONF_IP],
            mac=config[CONF_MAC],
            device_type=config[CONF_TYPE],
            config=config[CONF_CFG],
        )
        add_entities(stm_sbm.get_sub_entities())
    else:
        raise NotImplementedError("not implemented device type: {config[CONF_TYPE]}")


class StmSbm300(SihasProxy):
    """Representation of an STM-300 and SBM-300"""

    def __init__(
        self,
        ip: str,
        mac: str,
        device_type: str,
        config: int,
    ):
        super().__init__(
            ip=ip,
            mac=mac,
            device_type=device_type,
            config=config,
        )

    def get_sub_entities(self) -> List[Entity]:
        return [StmSbmVirtualLight(self, i) for i in range(0, self.config)]


class StmSbmVirtualLight(LightEntity):
    _attr_icon = ICON_LIGHT_BULB

    def __init__(self, stbm: StmSbm300, number_of_switch: int):
        super().__init__()

        uid = f"{stbm.device_type}-{stbm.mac}-{number_of_switch}"

        self._proxy = stbm
        self._attr_available = self._proxy._attr_available
        self._state = None
        self._number_of_switch = number_of_switch
        self._attr_name = uid
        self._attr_unique_id = uid

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
