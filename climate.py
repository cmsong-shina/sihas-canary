"""Platform for light integration."""
from __future__ import annotations

import logging
import math
from abc import abstractmethod
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from typing import Dict, List, Optional, cast

from homeassistant.components.switch import SwitchEntity
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    CURRENT_HVAC_FAN,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_AUTO,
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
from homeassistant.components.select import SelectEntity
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

        except (ModbusNotEnabledError, PacketSizeError) as e:
            raise e

        except Exception as e:
            _LOGGER.error(
                "failed to add device <%s, %s>, be sure IP is correct and restart HA to load HCM: %s",
                entry.data[CONF_TYPE],
                entry.data[CONF_IP],
                e,
            )
    elif entry.data[CONF_TYPE] == "BCM":
        async_add_entities(
            [
                Bcm300(
                    entry.data[CONF_IP],
                    entry.data[CONF_MAC],
                    entry.data[CONF_TYPE],
                    entry.data[CONF_CFG],
                    entry.data[CONF_NAME],
                ),
            ],
        )
    return


class Hcm300(SihasProxy):
    def __init__(
        self,
        ip: str,
        mac: str,
        device_type: str,
        config: int,
        name: Optional[str] = None,
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
    _attr_max_temp = 65
    _attr_min_temp: Final = 0
    _attr_supported_features: Final = SUPPORT_TARGET_TEMPERATURE
    _attr_target_temperature_step = 0.5
    _attr_temperature_unit: Final = TEMP_CELSIUS

    def __init__(self, proxy: Hcm300, number_of_room: int, name: Optional[str] = None) -> None:
        super().__init__()
        uid = f"{proxy.device_type}-{proxy.mac}-{number_of_room}"

        # proxy attr
        self._proxy = proxy
        self._attr_available = self._proxy._attr_available
        self._room_register_index = HCM_REG_STATE_START + number_of_room
        self._attr_unique_id = uid
        self._attr_name = f"{name} #{number_of_room + 1}" if name else self._attr_unique_id

    def set_hvac_mode(self, hvac_mode: str):
        self._proxy.command(
            self._room_register_index,
            self._apply_hvac_mode_on_cache(hvac_mode),
        )

    def set_temperature(self, **kwargs):
        tmp = cast(float, kwargs.get(ATTR_TEMPERATURE))
        self._proxy.command(
            self._room_register_index,
            self._apply_target_temperature_on_cache(tmp),
        )

    def update(self):
        self._proxy.update()
        self._attr_available = self._proxy._attr_available
        self._register_cache = self._proxy.registers[self._room_register_index]

        # 최대 온도/온도 단위 가변 설정
        self._attr_max_temp = 65 if self.temperature_magnification == 0 else (65 / 2)
        self._attr_target_temperature_step = self.temperature_magnification

        summary = self.parse_room_summary(self._register_cache)
        self._attr_hvac_mode = summary.hvac_mode
        self._attr_current_temperature = summary.current_temperature
        self._attr_target_temperature = summary.target_temperature
        self._attr_hvac_action = summary.hvac_action

    @property
    def temperature_magnification(self) -> float:
        """room summary의 온도 배율을 반환"""
        return 0.5 if self._proxy.registers[HCM_REG_ROOM_TEMP_UNIT] != 0 else 1

    def parse_room_summary(self, reg: int) -> RoomSummaryData:
        return RoomSummaryData(
            ((reg & HCM_MASK_CURTMP) >> 4) * self.temperature_magnification,
            CURRENT_HVAC_IDLE if (((reg & HCM_MASK_VALVE) >> 3) == 0) else CURRENT_HVAC_HEAT,
            HVAC_MODE_HEAT if ((reg & HCM_MASK_ONOFF) == 1) else HVAC_MODE_OFF,
            ((reg & HCM_MASK_SETTMP) >> 10) * self.temperature_magnification,
        )

    def _apply_hvac_mode_on_cache(self, onoff: str) -> int:
        mask = 1 if onoff == HVAC_MODE_HEAT else 0
        return (self._register_cache & ~HCM_MASK_ONOFF) | mask

    def _apply_target_temperature_on_cache(self, t: float) -> int:
        t = t / self.temperature_magnification
        mask = int(t)
        return (self._register_cache & ~HCM_MASK_SETTMP) | (mask << 10)


@dataclass
class RoomSummaryData:
    current_temperature: float
    hvac_action: str
    hvac_mode: str
    target_temperature: float


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
        name: Optional[str] = None,
    ):
        super().__init__(
            ip=ip,
            mac=mac,
            device_type=device_type,
            config=config,
            name=name,
        )

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
        tmp = cast(float, kwargs.get(ATTR_TEMPERATURE))
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


class OutModeEntity(SelectEntity):
    OUT_MODE: Final[str] = "OUT"  # 외출
    OCCUPY_MODE: Final[str] = "OCCUPY"  # 재실

    def __init__(self) -> None:
        SelectEntity.__init__(self)
        self._attr_options = [OutModeEntity.OUT_MODE, OutModeEntity.OCCUPY_MODE]
        self._attr_current_option = None

    @abstractmethod
    def select_option(self, option: str) -> None:
        """Change the selected option."""


class BcmHeatMode(Enum):
    Room: Final = 0
    Ondol: Final = 1


@dataclass
class BcmOpMode:
    isOnsuOn: bool
    isHeatOn: bool
    heatMode: BcmHeatMode


# BCM
BCM_REG_ONOFF: Final = 0  # 보일러 운전상태 ON/OFF
BCM_REG_ROOMSETPT: Final = 1  # 보일러 실내난방 설정온도(x1)
BCM_REG_ONDOLSETPT: Final = 2  # 보일러 온돌난방 설정온도(x1)
BCM_REG_ONSUSETPT: Final = 3  # 보일러 온수전용 설정온도(x1)
BCM_REG_OPERMODE: Final = 4  # 보일러 운전모드
BCM_REG_OUTMODE: Final = 5  # 보일러 외출모드(0=재실,1=외출)
BCM_REG_TIMERMODE: Final = 6  # 보일러 예약모드(0=예약없음,1=예약실행)
BCM_REG_TIMERTIME: Final = 7  # 보일러 예약시간(예:1210->12시간마다 10분가동)
BCM_REG_ROOMTEMP: Final = 8  # 보일러 실내온도(x0.1)
BCM_REG_ONDOLTEMP: Final = 9  # 보일러 온돌온도(x1)
BCM_REG_ONSUTEMP: Final = 10  # 보일러 온수온도(x1)
BCM_REG_FIRE_STATE: Final = 11  # 보일러 연소상태(0=정지,1=연소)
BCM_REG_ERRORST: Final = 12  # 보일러 에러상태(0=정상, 그외는 에러)
BCM_REG_WATERST: Final = 13  # 보일러 물보충상태(0=정상, 1=물보충필요)
BCM_REG_ONLINEST: Final = 14  # 보일러 통신상태(0=온라인, 1=오프라인)


class Bcm300(SihasEntity, ClimateEntity):
    _attr_icon = ICON_HEATER
    _attr_hvac_modes: Final = [HVAC_MODE_OFF, HVAC_MODE_HEAT, HVAC_MODE_FAN_ONLY, HVAC_MODE_AUTO]
    _attr_max_temp: Final = 80
    _attr_min_temp: Final = 0
    _attr_supported_features: Final = SUPPORT_TARGET_TEMPERATURE
    _attr_target_temperature_step: Final = 1
    _attr_temperature_unit: Final = TEMP_CELSIUS

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

        self.opmode: Optional[BcmOpMode] = None

    def set_hvac_mode(self, hvac_mode: str):
        if hvac_mode == HVAC_MODE_FAN_ONLY:
            self.command(BCM_REG_OUTMODE, 1)
            self.command(BCM_REG_ONOFF, 1)
        elif hvac_mode == HVAC_MODE_HEAT:
            self.command(BCM_REG_OUTMODE, 0)
            self.command(BCM_REG_ONOFF, 1)
            self.command(BCM_REG_TIMERMODE, 1)
        elif hvac_mode == HVAC_MODE_AUTO:
            self.command(BCM_REG_OUTMODE, 0)
            self.command(BCM_REG_ONOFF, 1)
            self.command(BCM_REG_TIMERMODE, 0)
        elif hvac_mode == HVAC_MODE_OFF:
            self.command(BCM_REG_ONOFF, 0)

    def set_temperature(self, **kwargs):
        tmp = cast(float, kwargs.get(ATTR_TEMPERATURE))

        assert self.opmode != None
        self.command(
            BCM_REG_ROOMSETPT if (self.opmode.heatMode == BcmHeatMode.Room) else BCM_REG_ONDOLSETPT,
            math.floor(tmp),
        )

    def update(self):
        if regs := self.poll():
            self.opmode = self._parse_oper_mode(regs)

            self._attr_hvac_mode = self._resolve_hvac_mode(regs)
            self._attr_hvac_action = self._resolve_hvac_action(regs)

            setpt: Optional[int] = None  # set point
            curpt: Optional[int] = None  # current point

            if self.opmode.heatMode == BcmHeatMode.Room:
                setpt = regs[BCM_REG_ROOMSETPT]
                curpt = math.floor(regs[BCM_REG_ROOMTEMP] / 10)
            else:
                setpt = regs[BCM_REG_ONDOLSETPT]
                curpt = regs[BCM_REG_ONDOLTEMP]

            self._attr_current_temperature = curpt
            self._attr_target_temperature = setpt

    def _resolve_hvac_mode(self, regs):
        if regs[BCM_REG_ONOFF] == 0:
            return HVAC_MODE_OFF
        elif regs[BCM_REG_TIMERMODE] == 1:
            return HVAC_MODE_HEAT
        elif regs[BCM_REG_OUTMODE] == 1:
            return HVAC_MODE_FAN_ONLY
        else:
            return HVAC_MODE_AUTO

    def _resolve_hvac_action(self, regs):
        if regs[BCM_REG_ONOFF] == 0:
            return CURRENT_HVAC_OFF
        # elif regs[BCM_REG_OUTMODE] == 1:
        #     return CURRENT_HVAC_FAN
        elif regs[BCM_REG_FIRE_STATE] == 0:
            return CURRENT_HVAC_IDLE
        else:
            return CURRENT_HVAC_HEAT

    def _parse_oper_mode(self, regs: List[int]) -> BcmOpMode:
        """보일러 운전모드 파싱
        regs[_BCMOPERMODE] = 0b_0000_0000
                                       \\\_온수 ON/OFF Flag
                                        \\_난방 ON/OFF Flag
                                         \_난방 모드 Flag [0=실내, 1=온돌]
        """
        reg = regs[BCM_REG_OPERMODE]

        return BcmOpMode(
            (reg & 1) != 0,
            (reg & (1 << 1)) != 0,
            BcmHeatMode.Ondol if (reg & (1 << 2)) != 0 else BcmHeatMode.Room,
        )
