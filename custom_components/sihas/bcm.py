"""Shared BCM-300 register model, serialized I/O and entity identity."""

from __future__ import annotations

import asyncio
import logging
import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from enum import IntEnum

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import ATTRIBUTION, CONF_IP, CONF_MAC, CONF_NAME, DOMAIN, REG_LENG
from .packet_builder import POLL_RESPONSE_LENGTH
from .packet_builder import packet_builder as pb
from .sender import send

_LOGGER = logging.getLogger(__name__)


class Register(IntEnum):
    POWER = 0
    ROOM_TARGET = 1
    ONDOL_TARGET = 2
    HOT_WATER_TARGET = 3
    OPERATION_MODE = 4
    AWAY = 5
    TIMER = 6
    ROOM_TEMPERATURE = 8
    FLAME = 11
    MANUFACTURER = 15
    HOT_WATER_MAX = 21
    HOT_WATER_MIN = 22
    ROOM_MAX = 23
    ROOM_MIN = 24
    ONDOL_MAX = 25
    ONDOL_MIN = 26


ROOM = "실내"
ONDOL = "온돌"
HOT_WATER = "온수"
OPERATION_MODES = [ROOM, ONDOL, HOT_WATER]
PRESENCE_OPTIONS = ["재실", "외출"]
HOT_WATER_BIT = 0x01
HEATING_BIT = 0x02
ONDOL_BIT = 0x04
BATH_BIT = 0x08
TARGET_REGISTERS = {
    ROOM: Register.ROOM_TARGET,
    ONDOL: Register.ONDOL_TARGET,
    HOT_WATER: Register.HOT_WATER_TARGET,
}
LIMIT_REGISTERS = {
    ROOM: (Register.ROOM_MIN, Register.ROOM_MAX),
    ONDOL: (Register.ONDOL_MIN, Register.ONDOL_MAX),
    HOT_WATER: (Register.HOT_WATER_MIN, Register.HOT_WATER_MAX),
}


@dataclass(frozen=True)
class BcmState:
    """An immutable, complete register response shared by all entities."""

    registers: tuple[int, ...]

    def __getitem__(self, register: Register) -> int:
        return self.registers[register]

    @property
    def operation_mode(self) -> str | None:
        bits = self[Register.OPERATION_MODE]
        if bits & HEATING_BIT:
            return ONDOL if bits & ONDOL_BIT else ROOM
        return HOT_WATER if bits & HOT_WATER_BIT else None

    @property
    def current_temperature(self) -> float:
        return self[Register.ROOM_TEMPERATURE] / 10

    @property
    def hot_water_kind(self) -> str | None:
        value = self[Register.HOT_WATER_MAX]
        if value == 1:
            return "two_step"
        if value == 2:
            return "three_step"
        if value > 2 and self.limits(HOT_WATER) is not None:
            return "linear"
        return None

    def limits(self, mode: str | None) -> tuple[int, int] | None:
        if mode not in LIMIT_REGISTERS:
            return None
        lower_register, upper_register = LIMIT_REGISTERS[mode]
        lower, upper = self[lower_register], self[upper_register]
        # Zero/uninitialized, reversed and sentinel bounds cannot enable control.
        if not 0 < lower < upper < 0xFFFF:
            return None
        if mode == HOT_WATER and upper <= 2:
            return None
        return lower, upper


class BcmClient:
    """Synchronous transport using the integration's existing packet/sender layer."""

    def __init__(self, ip: str) -> None:
        self.ip = ip

    def read(self) -> BcmState:
        response = send(pb.poll(), self.ip, retry=3)
        if len(response) != POLL_RESPONSE_LENGTH or response[7:9] != bytes(
            (3, REG_LENG * 2)
        ):
            raise ValueError("Invalid BCM register response")
        registers = pb.extract_registers(response)
        return BcmState(tuple(registers))

    def write(self, register: Register, value: int) -> None:
        request = pb.command(register, value)
        response = send(request, self.ip, retry=3)
        # A write response must echo the requested register and value.
        if response != request:
            raise ValueError("Invalid BCM write acknowledgement")


class BcmCoordinator(DataUpdateCoordinator[BcmState]):
    """One polling loop and one transaction lock per BCM config entry."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"BCM-{entry.data[CONF_MAC]}",
            config_entry=entry,
            update_interval=timedelta(seconds=5),
        )
        self.entry = entry
        self.client = BcmClient(entry.data[CONF_IP])
        self._io_lock = asyncio.Lock()
        self._stopping = False
        # Frozen after first successful refresh; rediscovered on reload.
        self.hot_water_kind: str | None = None
        self.has_bath = False

    def discover_model(self) -> None:
        self.hot_water_kind = self.data.hot_water_kind
        self.has_bath = self.data[Register.MANUFACTURER] == 1

    async def async_shutdown(self) -> None:
        """Drain in-flight I/O before a reload can create another coordinator."""
        self._stopping = True
        async with self._io_lock:
            # A finishing command may schedule the next refresh when publishing.
            await super().async_shutdown()

    async def _read(self) -> BcmState:
        try:
            return await self.hass.async_add_executor_job(self.client.read)
        except Exception as err:
            raise UpdateFailed(f"BCM read failed: {err}") from err

    async def _async_update_data(self) -> BcmState:
        async with self._io_lock:
            if self._stopping:
                raise UpdateFailed("BCM coordinator is unloading")
            # Cancellation must not release the lock while executor I/O is running.
            task = asyncio.create_task(self._read())
            try:
                return await asyncio.shield(task)
            except asyncio.CancelledError:
                await task
                raise

    def temperature_limits(
        self, state: BcmState, mode: str | None
    ) -> tuple[int, int] | None:
        if mode == HOT_WATER and (
            self.hot_water_kind != "linear" or state.hot_water_kind != "linear"
        ):
            return None
        return state.limits(mode)

    async def _async_command(
        self, resolve: Callable[[BcmState], tuple[Register, int]]
    ) -> None:
        async def transaction() -> None:
            async with self._io_lock:
                if self._stopping:
                    raise HomeAssistantError("BCM coordinator is unloading")
                try:
                    before = await self._read()
                    try:
                        register, value = resolve(before)
                    except ServiceValidationError:
                        self.async_set_updated_data(before)
                        raise
                    await self.hass.async_add_executor_job(
                        self.client.write, register, value
                    )
                    after = await self._read()
                except ServiceValidationError:
                    raise
                except Exception as err:
                    self.async_set_update_error(UpdateFailed(str(err)))
                    raise HomeAssistantError(f"BCM command failed: {err}") from err
                self.async_set_updated_data(after)
                if after[register] != value:
                    raise HomeAssistantError(
                        f"BCM register {register} did not confirm value {value} "
                        f"(read back {after[register]})"
                    )

        task = asyncio.create_task(transaction())
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            await task
            raise

    async def async_set_power(self, on: bool) -> None:
        await self._async_command(lambda _: (Register.POWER, int(on)))

    async def async_set_operation_mode(self, mode: str) -> None:
        if mode not in OPERATION_MODES:
            raise ServiceValidationError(f"Unsupported BCM operation mode: {mode}")

        def resolve(state: BcmState) -> tuple[Register, int]:
            bits = state[Register.OPERATION_MODE]
            if mode == ROOM:
                bits = (bits | HEATING_BIT) & ~ONDOL_BIT
            elif mode == ONDOL:
                bits |= HEATING_BIT | ONDOL_BIT
            else:
                bits = (bits | HOT_WATER_BIT) & ~HEATING_BIT
            return Register.OPERATION_MODE, bits

        await self._async_command(resolve)

    async def async_set_bath(self, on: bool) -> None:
        def resolve(state: BcmState) -> tuple[Register, int]:
            if not self.has_bath or state[Register.MANUFACTURER] != 1:
                raise ServiceValidationError("Bath mode requires a Kiturami boiler")
            bits = state[Register.OPERATION_MODE]
            return Register.OPERATION_MODE, bits | BATH_BIT if on else bits & ~BATH_BIT

        await self._async_command(resolve)

    async def async_set_presence(self, option: str) -> None:
        if option not in PRESENCE_OPTIONS:
            raise ServiceValidationError(f"Unsupported BCM presence: {option}")
        await self._async_command(
            lambda _: (Register.AWAY, PRESENCE_OPTIONS.index(option))
        )

    async def async_set_timer(self, on: bool) -> None:
        await self._async_command(lambda _: (Register.TIMER, int(on)))

    @property
    def hot_water_options(self) -> list[str]:
        if self.hot_water_kind == "two_step":
            return ["저온", "고온"]
        if self.hot_water_kind == "three_step":
            return ["저온", "중온", "고온"]
        return []

    async def async_set_hot_water_level(self, option: str) -> None:
        def resolve(state: BcmState) -> tuple[Register, int]:
            options = self.hot_water_options
            if state.hot_water_kind != self.hot_water_kind or option not in options:
                raise ServiceValidationError("Unsupported BCM hot water level")
            # Provisional wire mapping: verify 0/1 and 0/1/2 on real boilers.
            return Register.HOT_WATER_TARGET, options.index(option)

        await self._async_command(resolve)

    async def async_set_temperature(
        self, value: float, mode: str | None = None
    ) -> None:
        def resolve(state: BcmState) -> tuple[Register, int]:
            selected_mode = state.operation_mode if mode is None else mode
            limits = self.temperature_limits(state, selected_mode)
            if limits is None:
                raise ServiceValidationError("BCM temperature control is unavailable")
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not float(value).is_integer()
                or not limits[0] <= value <= limits[1]
            ):
                raise ServiceValidationError(
                    f"BCM temperature must be a whole degree within {limits[0]}–{limits[1]}"
                )
            return TARGET_REGISTERS[selected_mode], int(value)

        await self._async_command(resolve)


class BcmEntity(CoordinatorEntity[BcmCoordinator]):
    """Shared identity; retain the legacy climate unique ID without a suffix."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: BcmCoordinator, key: str | None = None) -> None:
        super().__init__(coordinator)
        data = coordinator.entry.data
        self._attr_unique_id = f"BCM-{data[CONF_MAC]}" + (f"-{key}" if key else "")
        name = data.get(CONF_NAME) or "bcm300"
        self._entity_key = key
        if key:
            self._attr_translation_key = f"bcm_{key}"
        else:
            # The primary climate entity uses the user-provided device name.
            self._attr_name = None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, data[CONF_MAC])},
            manufacturer="SiHAS",
            model="BCM-300",
            name=name,
        )
        self._attr_extra_state_attributes = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            CONF_IP: data[CONF_IP],
            CONF_MAC: data[CONF_MAC],
            "type": "BCM",
        }

    @property
    def suggested_object_id(self) -> str | None:
        """Keep the original default ID suffix, independent of display language."""
        return self._entity_key


def get_coordinator(hass: HomeAssistant, entry: ConfigEntry) -> BcmCoordinator:
    return hass.data[DOMAIN][entry.entry_id]
