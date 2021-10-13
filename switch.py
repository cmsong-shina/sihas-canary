from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import (
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_POWER_FACTOR,
    DEVICE_CLASS_VOLTAGE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from typing_extensions import Final

from .const import CONF_CFG, CONF_IP, CONF_MAC, CONF_TYPE, ICON_POWER_SOCKET, SIHAS_PLATFORM_SCHEMA
from .packet_builder import packet_builder
from .sender import send
from .sihas_base import SihasEntity

CCM_REG_POWER: Final = 0
CCM_REG_CUR_V: Final = 1  # voltage
CCM_REG_CUR_A: Final = 2  # current
CCM_REG_CUR_W: Final = 3  # power
CCM_REG_CUR_PF: Final = 4  # power_factor


PLATFORM_SCHEMA = SIHAS_PLATFORM_SCHEMA


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    if config[CONF_TYPE] == "CCM":
        add_entities(
            [
                Ccm300(
                    ip=config[CONF_IP],
                    mac=config[CONF_MAC],
                    device_type=config[CONF_TYPE],
                    config=config[CONF_CFG],
                ),
            ],
        )

    else:
        raise NotImplementedError("not implemented device type: {config[CONF_TYPE]}")


class Ccm300(SihasEntity, SwitchEntity):
    _attr_icon = ICON_POWER_SOCKET

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

    @property
    def is_on(self):
        return self._state

    def turn_on(self, **kwargs) -> None:
        req = packet_builder.command(0, 1)
        send(req, self.ip)

    def turn_off(self, **kwargs):
        req = packet_builder.command(0, 0)
        send(req, self.ip)

    def update(self):
        if regs := self.poll():
            self._state = regs[CCM_REG_POWER] == 1
            self._attributes[DEVICE_CLASS_VOLTAGE] = round(regs[CCM_REG_CUR_V] * 0.01, 3)
            self._attributes[DEVICE_CLASS_CURRENT] = round(regs[CCM_REG_CUR_A] * 0.001, 3)
            self._attributes[DEVICE_CLASS_POWER] = round(regs[CCM_REG_CUR_W] * 0.1, 3)
            self._attributes[DEVICE_CLASS_POWER_FACTOR] = round(regs[CCM_REG_CUR_PF] * 0.1, 3)
