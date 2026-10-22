"""Platform for light integration."""

from __future__ import annotations

import logging
import time
from abc import abstractmethod
from dataclasses import dataclass
from datetime import timedelta
from enum import IntEnum
from typing import Final, cast

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_VERTICAL,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .bcm import TARGET_REGISTERS, BcmCoordinator, BcmEntity, Register, get_coordinator
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
from .sihas_base import SihasEntity, SihasProxy, SihasSubEntity

SCAN_INTERVAL: Final = timedelta(seconds=5)

HCM_REG_ONOFF: Final = 0
HCM_REG_SET_TMP: Final = 1
HCM_REG_CUR_TMP: Final = 4
HCM_REG_CUR_VALVE: Final = 5
HCM_REG_NUMBER_OF_ROOMS: Final = 18
HVM_REG_NUMBER_OF_ROOMS: Final = 21
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
    elif entry.data[CONF_TYPE] in ["HCM", "HVM"]:
        try:
            async_add_entities(
                HcmHvm300(
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
                "failed to add device <%s, %s>, be sure IP is correct and restart HA to load HCM/HVM: %s",
                entry.data[CONF_TYPE],
                entry.data[CONF_IP],
                e,
            )

    elif entry.data[CONF_TYPE] in ["HQM"]:
        try:
            async_add_entities(
                Hqm300(
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
                "failed to add device <%s, %s>, be sure IP is correct and restart HA to load HQM: %s",
                entry.data[CONF_TYPE],
                entry.data[CONF_IP],
                e,
            )

    elif entry.data[CONF_TYPE] == "BCM":
        async_add_entities([Bcm300(get_coordinator(hass, entry))])
    elif entry.data[CONF_TYPE] == "TCM":
        async_add_entities(
            [
                Tcm300(
                    entry.data[CONF_IP],
                    entry.data[CONF_MAC],
                    entry.data[CONF_TYPE],
                    entry.data[CONF_CFG],
                    entry.data[CONF_NAME],
                ),
            ],
        )


HCM_SUPPORTED_FEATURES: Final = (
    ClimateEntityFeature.TARGET_TEMPERATURE
    | ClimateEntityFeature.TURN_ON
    | ClimateEntityFeature.TURN_OFF
)


class HcmHvm300(SihasProxy):
    def __init__(
        self,
        ip: str,
        mac: str,
        device_type: str,
        config: int,
        name: str | None = None,
    ) -> None:
        super().__init__(
            ip,
            mac,
            device_type,
            config,
        )
        self.name = name

    def get_sub_entities(self) -> list[Entity]:
        req = pb.poll()
        resp = send(req, self.ip)
        self.registers = pb.extract_registers(resp)
        reg_num_rooms: Final[int] = (
            HCM_REG_NUMBER_OF_ROOMS
            if self.device_type == "HCM"
            else HVM_REG_NUMBER_OF_ROOMS
        )
        number_of_room = self.registers[reg_num_rooms]
        return [
            HcmHvmVirtualThermostat(self, i, self.name)
            for i in range(number_of_room)
        ]


class HcmHvmVirtualThermostat(SihasSubEntity, ClimateEntity):
    _attr_icon = ICON_HEATER

    _attr_hvac_modes: Final = [HVACMode.OFF, HVACMode.HEAT]
    _attr_max_temp = 65
    _attr_min_temp: Final = 0
    _attr_supported_features: Final = HCM_SUPPORTED_FEATURES
    _attr_target_temperature_step = 0.5
    _attr_temperature_unit: Final = UnitOfTemperature.CELSIUS

    def __init__(
        self, proxy: HcmHvm300, number_of_room: int, name: str | None = None
    ) -> None:
        super().__init__(proxy)
        uid = f"{proxy.device_type}-{proxy.mac}-{number_of_room}"

        # proxy attr
        self._proxy = proxy
        self._attr_available = self._proxy._attr_available
        self._room_register_index = HCM_REG_STATE_START + number_of_room
        self._attr_unique_id = uid
        self._attr_name = (
            f"{name} #{number_of_room + 1}" if name else self._attr_unique_id
        )

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
            (
                HVACAction.IDLE
                if (((reg & HCM_MASK_VALVE) >> 3) == 0)
                else HVACAction.HEATING
            ),
            HVACMode.HEAT if ((reg & HCM_MASK_ONOFF) == 1) else HVACMode.OFF,
            ((reg & HCM_MASK_SETTMP) >> 10) * self.temperature_magnification,
        )

    def _apply_hvac_mode_on_cache(self, onoff: str) -> int:
        mask = 1 if onoff == HVACMode.HEAT else 0
        return (self._register_cache & ~HCM_MASK_ONOFF) | mask

    def _apply_target_temperature_on_cache(self, t: float) -> int:
        t = t / self.temperature_magnification
        mask = int(t)
        return (self._register_cache & ~HCM_MASK_SETTMP) | (mask << 10)


@dataclass
class RoomSummaryData:
    current_temperature: float
    hvac_action: HVACAction
    hvac_mode: HVACMode
    target_temperature: float


HQM_REG_ONOFF: Final = 0
HQM_REG_SET_TMP: Final = 1
HQM_REG_MODE: Final = 2
HQM_REG_CUR_TMP: Final = 4
HQM_REG_CUR_VALVE: Final = 5
HQM_REG_CUR_HUMID: Final = 7
HQM_REG_NUMBER_OF_ROOMS: Final = 16
HQM_REG_STATE_START: Final = 23


class Hqm300(SihasProxy):
    def __init__(
        self,
        ip: str,
        mac: str,
        device_type: str,
        config: int,
        name: str | None = None,
    ) -> None:
        super().__init__(
            ip,
            mac,
            device_type,
            config,
        )
        self.name = name

    def get_sub_entities(self) -> list[Entity]:
        req = pb.poll()
        resp = send(req, self.ip, retry=3)
        self.registers = pb.extract_registers(resp)
        is_wv = self.config == 0
        is_slave = self.registers[9] != 0

        if is_wv or is_slave:
            return [HqmStandaloneThermostat(self, self.name)]
        else:
            number_of_room = self.registers[HQM_REG_NUMBER_OF_ROOMS]
            return [
                HqmVirtualThermostat(self, i, self.name)
                for i in range(number_of_room)
            ]


class HqmVirtualThermostat(SihasSubEntity, ClimateEntity):
    _attr_icon = ICON_HEATER

    _attr_hvac_modes: Final = [HVACMode.OFF, HVACMode.HEAT]
    _attr_max_temp = 65
    _attr_min_temp: Final = 0
    _attr_supported_features: Final = HCM_SUPPORTED_FEATURES
    _attr_target_temperature_step = 0.5
    _attr_temperature_unit: Final = UnitOfTemperature.CELSIUS

    def __init__(
        self, proxy: Hqm300, number_of_room: int, name: str | None = None
    ) -> None:
        super().__init__(proxy)
        uid = f"{proxy.device_type}-{proxy.mac}-{number_of_room}"

        # proxy attr
        self._proxy = proxy
        self._attr_available = self._proxy._attr_available
        self._room_register_index = HQM_REG_STATE_START + number_of_room
        self._attr_unique_id = uid
        self._attr_name = (
            f"{name} #{number_of_room + 1}" if name else self._attr_unique_id
        )

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
        return 0.5  # always fixed to 0.5

    def parse_room_summary(self, reg: int) -> RoomSummaryData:
        return RoomSummaryData(
            ((reg & HCM_MASK_CURTMP) >> 4) * self.temperature_magnification,
            (
                HVACAction.IDLE
                if (((reg & HCM_MASK_VALVE) >> 3) == 0)
                else HVACAction.HEATING
            ),
            HVACMode.HEAT if ((reg & HCM_MASK_ONOFF) == 1) else HVACMode.OFF,
            ((reg & HCM_MASK_SETTMP) >> 10) * self.temperature_magnification,
        )

    def _apply_hvac_mode_on_cache(self, onoff: str) -> int:
        mask = 1 if onoff == HVACMode.HEAT else 0
        return (self._register_cache & ~HCM_MASK_ONOFF) | mask

    def _apply_target_temperature_on_cache(self, t: float) -> int:
        t = t / self.temperature_magnification
        mask = int(t)
        return (self._register_cache & ~HCM_MASK_SETTMP) | (mask << 10)


class HqmStandaloneThermostat(SihasSubEntity, ClimateEntity):
    _attr_icon = ICON_HEATER

    _attr_hvac_modes: Final = [HVACMode.OFF, HVACMode.HEAT]
    _attr_max_temp = 65
    _attr_min_temp: Final = 0
    _attr_supported_features: Final = HCM_SUPPORTED_FEATURES
    _attr_target_temperature_step = 0.1
    _attr_temperature_unit: Final = UnitOfTemperature.CELSIUS

    def __init__(self, proxy: Hqm300, name: str | None = None) -> None:
        super().__init__(proxy)
        uid = f"{proxy.device_type}-{proxy.mac}"

        # proxy attr
        self._proxy = proxy
        self._attr_available = self._proxy._attr_available
        self._attr_unique_id = uid
        self._attr_name = name if name else self._attr_unique_id

    def set_hvac_mode(self, hvac_mode: HVACMode):
        is_on: bool | None = None

        match hvac_mode:
            case HVACMode.OFF:
                is_on = False

            case HVACMode.HEAT:
                is_on = True

        if is_on is None:
            _LOGGER.error(f"Not supported HVACMode for HQM-300: {hvac_mode}")
            return

        self._proxy.command(HQM_REG_ONOFF, 1 if is_on else 0)

    def set_temperature(self, **kwargs):
        tmp = cast(float, kwargs.get(ATTR_TEMPERATURE))
        self._proxy.command(
            HQM_REG_SET_TMP,
            int(tmp * 10),
        )

    def update(self):
        self._proxy.update()
        self._attr_available = self._proxy._attr_available
        registers = self._proxy.registers

        if registers[HQM_REG_ONOFF] == 0:
            self._attr_hvac_mode = HVACMode.OFF
        else:
            self._attr_hvac_mode = HVACMode.HEAT

        self._attr_current_temperature = registers[HQM_REG_CUR_TMP] / 10
        self._attr_target_temperature = registers[HQM_REG_SET_TMP] / 10

        match (
            registers[HQM_REG_ONOFF],
            registers[HQM_REG_CUR_VALVE],
        ):
            case (0, _):
                self._attr_hvac_action = HVACAction.OFF
            case (_, 0):
                self._attr_hvac_action = HVACAction.IDLE
            case (_, 1):
                self._attr_hvac_action = HVACAction.HEATING
            case _:
                _LOGGER.warning(
                    f"Not implemented HVAC actions ({registers[HQM_REG_ONOFF]}, {registers[HQM_REG_CUR_VALVE]})"
                )


class Acm300(SihasEntity, ClimateEntity):
    # base attribute
    _attr_icon = ICON_COOLER

    # entity attribute
    _attr_hvac_modes = [
        HVACMode.OFF,
        HVACMode.COOL,
        HVACMode.DRY,
        HVACMode.FAN_ONLY,
        HVACMode.AUTO,
        HVACMode.HEAT,
    ]
    _attr_max_temp = 30
    _attr_min_temp = 18
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_target_temperature_step = 1
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_swing_modes = [
        SWING_OFF,
        SWING_VERTICAL,
        SWING_HORIZONTAL,
        SWING_BOTH,
    ]
    _attr_fan_modes = [FAN_LOW, FAN_MEDIUM, FAN_HIGH, FAN_AUTO]

    # static final
    REG_ON_OFF: Final = 0
    REG_SET_POINT: Final = 1
    REG_MODE: Final = 2
    REG_FAN: Final = 3
    REG_SWING: Final = 4
    REG_EXEC_UCR: Final = 5
    REG_AC_TEMP: Final = 6
    REG_LIST_UCR1: Final = 54
    REG_LIST_UCR2: Final = 55

    HVAC_MODE_TABLE: Final = [
        HVACMode.COOL,
        HVACMode.DRY,
        HVACMode.FAN_ONLY,
        HVACMode.AUTO,
        HVACMode.HEAT,
    ]
    SWING_MODE_TABLE: Final = [
        SWING_OFF,
        SWING_VERTICAL,
        SWING_HORIZONTAL,
        SWING_BOTH,
    ]
    FAN_TABLE: Final = [FAN_LOW, FAN_MEDIUM, FAN_HIGH, FAN_AUTO]

    def __init__(
        self,
        ip: str,
        mac: str,
        device_type: str,
        config: int,
        name: str | None = None,
    ):
        super().__init__(
            ip=ip,
            mac=mac,
            device_type=device_type,
            config=config,
            name=name,
        )

    # TODO: async fuction raise excaption. why?
    def set_hvac_mode(self, hvac_mode: HVACMode):
        """
        Set the HVAC mode for the AC unit.

        This method handles the setting of HVAC mode for the AC unit, considering
        the differences between how Home Assistant (HA) and the AC unit treat on/off
        states and HVAC modes. In HA, there is no explicit ON command, so this method
        ensures the correct sequence of commands is sent to the AC unit.

        Args:
            hvac_mode (str): The desired HVAC mode to set. This should be one of the
                             modes defined in HVACMode.

        Behavior:
            - If the command is OFF, the AC unit is turned off.
            - If the command is not OFF, the mode is changed first, followed by a delay
              to prevent IR conflict, and then the AC unit is turned on.

        Note:
            - A delay of 0.5 seconds is introduced between changing the mode and turning
              the unit on to prevent IR signal conflicts.
        """

        if hvac_mode == HVACMode.OFF:
            self.command(Acm300.REG_ON_OFF, 0)
            return

        # Change mode first
        if self.hvac_mode != hvac_mode:
            self.command(
                self.REG_MODE,
                self.HVAC_MODE_TABLE.index(hvac_mode),
            )
            time.sleep(0.5)  # Delay to prevent IR conflict

        if self.hvac_mode == HVACMode.OFF:
            self.command(Acm300.REG_ON_OFF, 1)

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
                HVACMode.OFF
                if regs[Acm300.REG_ON_OFF] == 0
                else Acm300.HVAC_MODE_TABLE[regs[Acm300.REG_MODE]]
            )
            self._attr_swing_mode = Acm300.SWING_MODE_TABLE[regs[Acm300.REG_SWING]]
            self._attr_fan_mode = Acm300.FAN_TABLE[regs[Acm300.REG_FAN]]
            if self.config >= 1:
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


class Bcm300(BcmEntity, ClimateEntity):
    """BCM power and the selected mode's target; room measurement in all modes."""

    _attr_icon = ICON_HEATER
    _attr_hvac_modes: Final = [HVACMode.OFF, HVACMode.HEAT]
    _attr_target_temperature_step = 1
    _attr_precision = 0.1
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator: BcmCoordinator) -> None:
        super().__init__(coordinator)

    @property
    def hvac_mode(self) -> HVACMode:
        return HVACMode.HEAT if self.coordinator.data[Register.POWER] else HVACMode.OFF

    @property
    def hvac_action(self) -> HVACAction:
        if self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        return (
            HVACAction.HEATING if self.coordinator.data[Register.FLAME]
            else HVACAction.IDLE
        )

    @property
    def current_temperature(self) -> float:
        return self.coordinator.data.current_temperature

    @property
    def _limits(self) -> tuple[int, int] | None:
        state = self.coordinator.data
        return self.coordinator.temperature_limits(state, state.operation_mode)

    @property
    def supported_features(self) -> ClimateEntityFeature:
        features = ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
        if self._limits is not None:
            features |= ClimateEntityFeature.TARGET_TEMPERATURE
        return features

    @property
    def target_temperature(self) -> float | None:
        if self._limits is None:
            return None
        state = self.coordinator.data
        return state[TARGET_REGISTERS[state.operation_mode]]

    @property
    def min_temp(self) -> float:
        return self._limits[0] if self._limits else 0

    @property
    def max_temp(self) -> float:
        return self._limits[1] if self._limits else 0

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode not in self.hvac_modes:
            raise ServiceValidationError(f"Unsupported BCM HVAC mode: {hvac_mode}")
        await self.coordinator.async_set_power(hvac_mode == HVACMode.HEAT)

    async def async_turn_on(self) -> None:
        await self.coordinator.async_set_power(True)

    async def async_turn_off(self) -> None:
        await self.coordinator.async_set_power(False)

    async def async_set_temperature(self, **kwargs) -> None:
        # Do not apply a supplied hvac_mode: set points never change power.
        await self.coordinator.async_set_temperature(kwargs.get(ATTR_TEMPERATURE))


# Register index
class TcmRegister(IntEnum):
    POWER = 0
    DESIRED_TEMPERATURE = 1
    OUT_MODE = 2
    CURRENT_TEMPERATURE = 3
    VALVE = 4
    ALARM = 5
    FAN_POWER = 6
    RUN_MODE = 7
    LOCK = 8


# Out mode
class TcmOutMode(IntEnum):
    IN_DOOR = 0
    OUT_DOOR = 1


# Run mode
class TcmRunMode(IntEnum):
    HEATING = 0
    COOLING = 1

    def to_hvac_mode(self) -> HVACMode:
        return HVACMode.HEAT if self is TcmRunMode.HEATING else HVACMode.COOL

    @staticmethod
    def from_hvac_mode(hvac_mode: HVACMode) -> TcmRunMode:
        return TcmRunMode.HEATING if hvac_mode == HVACMode.HEAT else TcmRunMode.COOLING


# Fan power
class TcmFanPower(IntEnum):
    AUTO = 0
    LOW = 1
    MIDDLE = 2
    HIGH = 3


class Tcm300(SihasEntity, ClimateEntity):
    _attr_icon = ICON_HEATER
    _attr_hvac_modes: Final = [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL]
    _attr_max_temp: Final = 80
    _attr_min_temp: Final = 0
    _attr_supported_features: Final = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_target_temperature_step: Final = 0.1
    _attr_temperature_unit: Final = UnitOfTemperature.CELSIUS

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

    def set_hvac_mode(self, hvac_mode: HVACMode):
        if hvac_mode == HVACMode.OFF:
            self.command(TcmRegister.POWER, 0)
        else:
            self.command(TcmRegister.POWER, 1)
            self.command(TcmRegister.RUN_MODE, TcmRunMode.from_hvac_mode(hvac_mode))

    def set_temperature(self, **kwargs):
        tmp = cast(float, kwargs.get(ATTR_TEMPERATURE))
        self.command(TcmRegister.DESIRED_TEMPERATURE, int(tmp * 10))

    def update(self):
        if regs := self.poll():
            is_off = regs[TcmRegister.POWER] == 0
            cur_tmp = regs[TcmRegister.CURRENT_TEMPERATURE] / 10
            set_tmp = regs[TcmRegister.DESIRED_TEMPERATURE] / 10
            run_mode = TcmRunMode(regs[TcmRegister.RUN_MODE])

            ## reserved
            # out_mode = TcmOutMode(regs[TcmRegister.OUT_MODE])
            # fan_power = TcmFanPower(regs[TcmRegister.FAN_POWER])

            self._attr_hvac_mode = HVACMode.OFF if is_off else run_mode.to_hvac_mode()
            self._attr_current_temperature = cur_tmp
            self._attr_target_temperature = set_tmp
