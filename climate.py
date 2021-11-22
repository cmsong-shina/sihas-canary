"""Platform for light integration."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Dict, List

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_FAN_MODE,
    SUPPORT_SWING_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_VERTICAL,
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
    ICON_COOLER,
    ICON_HEATER,
    SIHAS_PLATFORM_SCHEMA,
)
from .errors import ModbusNotEnabledError
from .packet_builder import packet_builder as pb
from .sender import send
from .sihas_base import SihasEntity, SihasProxy

SCAN_INTERVAL = timedelta(seconds=5)

HCM_REG_ONOFF: Final = 0
HCM_REG_SET_TMP: Final = 1
HCM_REG_CUR_TMP: Final = 4
HCM_REG_CUR_VALVE: Final = 5
HCM_REG_NUMBER_OF_ROOMS: Final = 18
HCM_REG_STATE_START: Final = 52

# HCM room register mask
HCM_MASK_ONOFF: Final = 0b_0000_0000_0000_0001
HCM_MASK_OPMOD: Final = 0b_0000_0000_0000_0110
HCM_MASK_VALVE: Final = 0b_0000_0000_0000_1000
HCM_MASK_CURTMP: Final = 0b0000_0011_1111_0000
HCM_MASK_SETTMP: Final = 0b1111_1100_0000_0000

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = DEFAULT_PARALLEL_UPDATES
PLATFORM_SCHEMA: Final = SIHAS_PLATFORM_SCHEMA


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    if entry.data[CONF_TYPE] == "ACM":
        async_add_entities(
            [
                Acm300(
                    entry.data[CONF_IP],
                    entry.data[CONF_MAC],
                    entry.data[CONF_TYPE],
                    entry.data[CONF_CFG],
                    entry.data[CONF_NAME],
                ),
            ],
        )
    elif entry.data[CONF_TYPE] == "HCM":
        try:
            async_add_entities(
                Hcm300(
                    entry.data[CONF_IP],
                    entry.data[CONF_MAC],
                    entry.data[CONF_TYPE],
                    entry.data[CONF_CFG],
                    entry.data[CONF_NAME],
                ).get_sub_entities()
            )

        except ModbusNotEnabledError:
            raise ModbusNotEnabledError(entry.data[CONF_IP])

        except Exception as e:
            _LOGGER.error(
                f"failed to add device <{entry.data[CONF_TYPE]}, {entry.data[CONF_IP]}>, be sure IP is correct and restart HA to load HCM: {e}"
            )
    return


class Hcm300(SihasProxy):
    def __init__(
        self,
        ip: str,
        mac: str,
        device_type: str,
        config: int,
        name: str = None,
    ) -> None:
        super().__init__(
            ip,
            mac,
            device_type,
            config,
        )
        self.name = name

    def get_sub_entities(self) -> List[Entity]:
        req = pb.poll()
        resp = send(req, self.ip)
        self.registers = pb.extract_registers(resp)
        number_of_room = self.registers[HCM_REG_NUMBER_OF_ROOMS]
        return [HcmVirtualThermostat(self, i, self.name) for i in range(0, number_of_room)]


class HcmVirtualThermostat(ClimateEntity):
    _attr_icon = ICON_HEATER

    _attr_hvac_modes: Final = [HVAC_MODE_OFF, HVAC_MODE_HEAT]
    _attr_max_temp: Final = 65
    _attr_min_temp: Final = 0
    _attr_supported_features: Final = SUPPORT_TARGET_TEMPERATURE
    _attr_target_temperature_step: Final = 1
    _attr_temperature_unit: Final = TEMP_CELSIUS

    def __init__(self, proxy: Hcm300, number_of_room: int, name: str = None) -> None:
        super().__init__()
        uid = f"{proxy.device_type}-{proxy.mac}-{number_of_room}"

        # proxy attr
        self._proxy = proxy
        self._attr_available = self._proxy._attr_available
        self._room_register_index = HCM_REG_STATE_START + number_of_room
        self._attr_unique_id = uid
        self._attr_name = name + number_of_room if name else self._attr_unique_id

    def set_hvac_mode(self, hvac_mode: str):
        self._proxy.command(
            self._room_register_index,
            self._apply_hvac_mode_on_cache(hvac_mode),
        )

    def set_temperature(self, **kwargs):
        tmp = kwargs.get(ATTR_TEMPERATURE)
        self._proxy.command(
            self._room_register_index,
            self._apply_target_temperature_on_cache(tmp),
        )

    def update(self):
        self._proxy.update()
        self._attr_available = self._proxy._attr_available
        self._register_cache = self._proxy.registers[self._room_register_index]

        data = self.parse_register(self._register_cache)
        self._attr_hvac_mode = data["hvac_mode"]
        self._attr_current_temperature = data["current_temperature"]
        self._attr_target_temperature = data["target_temperature"]
        self._attr_hvac_action = data["hvac_action"]

    def parse_register(self, reg: int) -> Dict:
        return {
            "current_temperature": (reg & HCM_MASK_CURTMP) >> 4,
            "hvac_action": CURRENT_HVAC_IDLE
            if (((reg & HCM_MASK_VALVE) >> 3) == 0)
            else CURRENT_HVAC_HEAT,
            "hvac_mode": HVAC_MODE_HEAT if ((reg & HCM_MASK_ONOFF) == 1) else HVAC_MODE_OFF,
            "target_temperature": (reg & HCM_MASK_SETTMP) >> 10,
        }

    def _apply_hvac_mode_on_cache(self, onoff: str) -> int:
        mask = 1 if onoff == HVAC_MODE_HEAT else 0
        return (self._register_cache & ~HCM_MASK_ONOFF) | mask

    def _apply_target_temperature_on_cache(self, t: float) -> int:
        mask = int(t)
        return (self._register_cache & ~HCM_MASK_SETTMP) | (mask << 10)


class Acm300(SihasEntity, ClimateEntity):
    # base attribute
    _attr_icon = ICON_COOLER

    # entity attribute
    _attr_hvac_modes = [
        HVAC_MODE_OFF,
        HVAC_MODE_COOL,
        HVAC_MODE_DRY,
        HVAC_MODE_FAN_ONLY,
        HVAC_MODE_AUTO,
        HVAC_MODE_HEAT,
    ]
    _attr_max_temp = 30
    _attr_min_temp = 18
    _attr_supported_features = SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE | SUPPORT_SWING_MODE
    _attr_target_temperature_step = 1
    _attr_temperature_unit = TEMP_CELSIUS
    _attr_swing_modes = [
        SWING_OFF,
        SWING_VERTICAL,
        SWING_HORIZONTAL,
        SWING_BOTH,
    ]
    _attr_fan_modes = [FAN_LOW, FAN_MEDIUM, FAN_HIGH]

    # static final
    REG_ON_OFF: Final = 0
    REG_SET_POINT: Final = 1
    REG_MODE: Final = 2
    REG_FAN: Final = 3
    REG_SWING: Final = 4
    REG_AC_TEMP: Final = 6

    HVAC_MODE_TABLE: Final = [
        HVAC_MODE_COOL,
        HVAC_MODE_DRY,
        HVAC_MODE_FAN_ONLY,
        HVAC_MODE_AUTO,
        HVAC_MODE_HEAT,
    ]
    SWING_MODE_TABLE: Final = [
        SWING_OFF,
        SWING_VERTICAL,
        SWING_HORIZONTAL,
        SWING_BOTH,
    ]
    FAN_TABLE: Final = [FAN_LOW, FAN_MEDIUM, FAN_HIGH]

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
            name=name,
        )

        # init hass defined variable
        self._attr_hvac_mode = None
        self._attr_current_temperature = None
        self._attr_target_temperature = None
        self._attr_hvac_action = None
        self._attr_swing_mode = None
        self._attr_fan_mode = None

    def set_hvac_mode(self, hvac_mode: str):
        reg_idx = None
        reg_val = None

        if hvac_mode == HVAC_MODE_OFF:
            reg_idx = Acm300.REG_ON_OFF
            reg_val = 0
        else:
            # if acm turned off, turn on first
            if self.hvac_mode == HVAC_MODE_OFF:
                self.command(Acm300.REG_ON_OFF, 1)

            reg_idx = self.REG_MODE
            reg_val = self.HVAC_MODE_TABLE.index(hvac_mode)

        self.command(reg_idx, reg_val)

    def set_temperature(self, **kwargs):
        tmp = kwargs.get(ATTR_TEMPERATURE)
        self.command(Acm300.REG_SET_POINT, int(tmp))

    def set_swing_mode(self, swing_mode):
        self.command(Acm300.REG_SWING, Acm300.SWING_MODE_TABLE.index(swing_mode))

    def set_fan_mode(self, fan_mode):
        self.command(Acm300.REG_FAN, Acm300.FAN_TABLE.index(fan_mode))

    def update(self):
        if regs := self.poll():
            self._attr_hvac_mode = (
                HVAC_MODE_OFF
                if regs[Acm300.REG_ON_OFF] == 0
                else Acm300.HVAC_MODE_TABLE[regs[Acm300.REG_MODE]]
            )
            self._attr_swing_mode = Acm300.SWING_MODE_TABLE[regs[Acm300.REG_SWING]]
            self._attr_fan_mode = Acm300.FAN_TABLE[regs[Acm300.REG_FAN]]
            if self.config == 1:
                self._attr_current_temperature = regs[Acm300.REG_AC_TEMP] / 10
            self._attr_target_temperature = regs[Acm300.REG_SET_POINT]
