from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import timedelta
from enum import IntEnum

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import ATTRIBUTION, CONF_IP, CONF_MAC, CONF_NAME, DOMAIN
from .packet_builder import POLL_RESPONSE_LENGTH
from .packet_builder import packet_builder as pb
from .sender import send

_LOGGER = logging.getLogger(__name__)
BATTERY_OPTIONS = ["replace", "low", "medium", "full"]


class Register(IntEnum):
    CLOSE = 0
    VALVE = 1
    DEFAULT_TIME = 2
    REMAINING_TIME = 3
    FIRE = 4
    BATTERY = 5


@dataclass(frozen=True)
class GcmState:
    registers: tuple[int, ...]

    @property
    def valve_open(self) -> bool | None:
        return {0: False, 1: True}.get(self.registers[Register.VALVE])

    @property
    def fire_alarm(self) -> bool | None:
        return {0: False, 1: True}.get(self.registers[Register.FIRE])

    @property
    def default_time(self) -> int:
        return self.registers[Register.DEFAULT_TIME]

    @property
    def remaining_time(self) -> int:
        return self.registers[Register.REMAINING_TIME]

    @property
    def battery_state(self) -> str | None:
        value = self.registers[Register.BATTERY]
        return BATTERY_OPTIONS[value] if 0 <= value < len(BATTERY_OPTIONS) else None


class GcmClient:
    """기존 UDP 패킷을 사용하며, 쓰기 동작으로는 닫기 명령만 제공한다."""

    def __init__(self, ip: str) -> None:
        self.ip = ip

    def read(self) -> GcmState:
        response = send(pb.poll(), self.ip, retry=3)
        # 읽기 거부 응답은 정상 레지스터 응답보다 짧다.
        # 단순한 길이 오류로 처리하지 않도록 거부 여부를 먼저 확인한다.
        if len(response) >= 12 or response[7] == 0x83:
            detail = f"0x{response[8]:02x}" if len(response) >= 9 else "missing"
            raise ValueError(
                f"GCM rejected register read (function=0x83, exception={detail}). "
                "Check that Modbus is enabled in the SiHAS app"
            )

        if len(response) != POLL_RESPONSE_LENGTH:
            raise ValueError(
                f"Invalid GCM response length: expected {POLL_RESPONSE_LENGTH}, "
                f"received {len(response)}"
            )

        if response[7] != 3:
            raise ValueError(
                f"Invalid GCM response function: expected 0x03, "
                f"received 0x{response[7]:02x}"
            )

        registers = pb.extract_registers(response)
        return GcmState(tuple(registers))

    def close(self) -> None:
        request = pb.command(Register.CLOSE, 0)
        if send(request, self.ip, retry=3) != request:
            raise ValueError("Invalid GCM write acknowledgement")


class GcmCoordinator(DataUpdateCoordinator[GcmState]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass, _LOGGER, name=f"GCM-{entry.data[CONF_MAC]}",
            config_entry=entry, update_interval=timedelta(seconds=5),
        )
        self.entry = entry
        self.client = GcmClient(entry.data[CONF_IP])
        self._io_lock = asyncio.Lock()

    async def _read(self) -> GcmState:
        try:
            return await self.hass.async_add_executor_job(self.client.read)
        except Exception as err:
            raise UpdateFailed(f"GCM read failed: {err}") from err

    async def _async_update_data(self) -> GcmState:
        async with self._io_lock:
            return await self._read()

    async def async_close(self) -> None:
        async with self._io_lock:
            try:
                # 사전 상태 조회의 성공 여부와 관계없이 닫기 명령을 보낼 수 있어야 한다.
                await self.hass.async_add_executor_job(self.client.close)
            except Exception as err:
                raise HomeAssistantError(f"GCM close command failed: {err}") from err

            try:
                after = await self._read()
            except UpdateFailed as err:
                self.async_set_update_error(err)
                # 쓰기 응답은 정상 수신했지만, 이후 상태 갱신이 실패한 경우다.
                _LOGGER.warning("GCM close acknowledged but refresh failed: %s", err)
            else:
                # 레지스터 0은 쓰기 전용이며, 실제 밸브 상태는 레지스터 1에서 읽는다.
                self.async_set_updated_data(after)


class GcmEntity(CoordinatorEntity[GcmCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: GcmCoordinator, key: str) -> None:
        super().__init__(coordinator)
        data = coordinator.entry.data
        self._attr_unique_id = f"GCM-{data[CONF_MAC]}-{key}"
        self._attr_translation_key = f"gcm_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, data[CONF_MAC])}, manufacturer="SiHAS",
            model="GCM-300", name=data.get(CONF_NAME) or "GCM-300",
        )
        self._attr_extra_state_attributes = {
            ATTR_ATTRIBUTION: ATTRIBUTION, CONF_IP: data[CONF_IP],
            CONF_MAC: data[CONF_MAC], "type": "GCM",
        }


def get_coordinator(hass: HomeAssistant, entry: ConfigEntry) -> GcmCoordinator:
    return hass.data[DOMAIN][entry.entry_id]
