"""Platform for light integration."""
from __future__ import annotations

import logging
import math
from abc import abstractmethod
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from typing import Dict, List, Optional, cast

from homeassistant.components.cover import (
    ATTR_POSITION,
    SUPPORT_CLOSE,
    SUPPORT_CLOSE_TILT,
    SUPPORT_OPEN,
    SUPPORT_OPEN_TILT,
    SUPPORT_SET_POSITION,
    SUPPORT_SET_TILT_POSITION,
    SUPPORT_STOP,
    SUPPORT_STOP_TILT,
    CoverEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from typing_extensions import Final

from .const import (
    CONF_CFG,
    CONF_IP,
    CONF_MAC,
    CONF_NAME,
    CONF_TYPE,
    DEFAULT_PARALLEL_UPDATES,
    ICON_CURTAIN,
    SIHAS_PLATFORM_SCHEMA,
)
from .errors import ModbusNotEnabledError, PacketSizeError
from .packet_builder import packet_builder as pb
from .sender import send
from .sihas_base import SihasEntity, SihasProxy

SCAN_INTERVAL: Final = timedelta(seconds=5)

HCM_REG_ONOFF: Final = 0
HCM_REG_SET_TMP: Final = 1
HCM_REG_CUR_TMP: Final = 4
HCM_REG_CUR_VALVE: Final = 5
HCM_REG_NUMBER_OF_ROOMS: Final = 18
HCM_REG_STATE_START: Final = 52
HCM_REG_ROOM_TEMP_UNIT: Final = 59

# HCM room register mask
HCM_MASK_ONOFF: Final = 0b_0000_0000_0000_0001
HCM_MASK_OPMOD: Final = 0b_0000_0000_0000_0110
HCM_MASK_VALVE: Final = 0b_0000_0000_0000_1000
HCM_MASK_CURTMP: Final = 0b0000_0011_1111_0000
HCM_MASK_SETTMP: Final = 0b1111_1100_0000_0000

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES: Final = DEFAULT_PARALLEL_UPDATES
PLATFORM_SCHEMA: Final = SIHAS_PLATFORM_SCHEMA


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    if entry.data[CONF_TYPE] == "RBM":
        async_add_entities(
            [
                Rbm300(
                    entry.data[CONF_IP],
                    entry.data[CONF_MAC],
                    entry.data[CONF_TYPE],
                    entry.data[CONF_CFG],
                    entry.data[CONF_NAME],
                ),
            ],
        )
    return


REG_RBM_STAT_CMD: Final = 0  # 상태 제어 레지스터     (0=닫힘, 1=열림, 2=정지)
REG_RBM_PCT_CMD: Final = 1  # 백분률 제어 레지스터   (0-100%)
REG_RBM_STAT_CUR: Final = 2  # 현재 상태 레지스터     (0=닫힘, 1=열림, 2=정지, 3=닫힘중, 4=열림중)
REG_RBM_PCT_CUR: Final = 3  # 현재 백분률 레지스터   (0-100%)


class Rbm300(SihasEntity, CoverEntity):
    _attr_icon = ICON_CURTAIN
    _attr_supported_features: Final = (
        SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_STOP | SUPPORT_SET_POSITION
    )

    def __init__(
        self,
        ip: str,
        mac: str,
        device_type: str,
        config: int,
        name: str | None = None,
    ) -> None:
        super().__init__(
            ip=ip,
            mac=mac,
            device_type=device_type,
            config=config,
            name=name,
        )

    def close_cover(self, **kwargs):
        self.command(REG_RBM_STAT_CMD, 0)

    def open_cover(self, **kwargs):
        self.command(REG_RBM_STAT_CMD, 1)

    def stop_cover(self, **kwargs):
        self.command(REG_RBM_STAT_CMD, 2)

    def set_cover_position(self, **kwargs):
        self.command(REG_RBM_PCT_CMD, kwargs[ATTR_POSITION])

    def update(self):
        if regs := self.poll():
            self._attr_is_closed = regs[REG_RBM_STAT_CUR] == 0
            self._attr_is_closing = regs[REG_RBM_STAT_CUR] == 3
            self._attr_is_opening = regs[REG_RBM_STAT_CUR] == 4
            self._attr_current_cover_position = regs[REG_RBM_PCT_CUR]
