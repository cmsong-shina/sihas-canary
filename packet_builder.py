from __future__ import annotations  # For hoisting


from dataclasses import dataclass
import logging
from typing import Final, List, Union, Optional
import socket

from .const import ENDIAN, device_type_from_enum
from .errors import ModbusNotEnabledError, PacketSizeError
from .util import BytesConv

_LOGGER = logging.getLogger(__name__)


_FUNCTION_CODE_POLL: Final = (0x03).to_bytes(1, ENDIAN)
_FUNCTION_CODE_COMMAND: Final = (0x06).to_bytes(1, ENDIAN)
_FUNCTION_CODE_SET_SERVER_ADDRESS: Final = (0x35).to_bytes(1, ENDIAN)

POS_FUNCTION_CODE: Final = 7

POLL_RESPONSE_LENGTH: Final = 137
HEADER_LENGTH: Final = 7

FC_EVENT: Final = 0x2E
FC_PERIODIC: Final = 0x24

# 푸시 패킷
VER_OFFSET = 54
VER_SIZE = 2
REG_NUM_OFFSET = 56
REG_IDX_OFFSET = 57
REG_IDX_SIZE = 2
REG_VAL_OFFSET = 59
REG_VAL_SIZE = 128

# 이벤트 패킷
NUMBER_OF_EVENTS_OFFSET = 54
EVT_REG_IDX_OFFSET = 55
EVT_REG_VAL_OFFSET = 57

SSID_OFFSET = 14
SSID_SIZE = 32
MAC_OFFSET = 46
MAC_SIZE = 6
DEVICE_TYPE_OFFSET = 52
CFG_OFFSET = 53


@dataclass
class Header:
    pass


@dataclass
class Meta:
    ssid: str
    mac: bytes
    type: str
    cfg: int

    def __init__(self, p: bytes) -> None:
        self.ssid = self._to_null_terminate_string(p[SSID_OFFSET : SSID_OFFSET + SSID_SIZE])
        self.mac = p[MAC_OFFSET : MAC_OFFSET + MAC_SIZE]
        self.type = device_type_from_enum(p[DEVICE_TYPE_OFFSET])
        self.cfg = p[CFG_OFFSET]

    @staticmethod
    def _to_null_terminate_string(p: bytes) -> str:
        for i in range(len(p)):
            if p[i] == 0:
                return p[:i].decode("utf-8")

        # When SSID taking full length of SSID(32 bytes)
        return p.decode("utf-8")


@dataclass
class PeriodicUpdatePacket:
    meta: Meta
    version: int
    reg_num: int
    reg_idx: int
    registers: List[int]
    # checksum: int

    def __init__(self, p: bytes):
        self.meta = Meta(p)
        self.version = int.from_bytes(p[VER_OFFSET : VER_OFFSET + VER_SIZE], ENDIAN)
        self.reg_num = p[REG_NUM_OFFSET]
        self.reg_idx = int.from_bytes(p[REG_IDX_OFFSET : REG_IDX_OFFSET + REG_IDX_SIZE], ENDIAN)
        self.registers = BytesConv.ball_u16(
            p[REG_VAL_OFFSET : REG_VAL_OFFSET + REG_VAL_SIZE], ENDIAN
        )


@dataclass
class EventPacketPacket:
    meta: Meta
    number_of_events: int
    events: List[EventData] = []
    # checksum: int

    def __init__(self, p: bytes):
        self.meta = Meta(p)
        self.number_of_events = p[NUMBER_OF_EVENTS_OFFSET]

        # Extract EventData
        # TODO: Add support SGW
        for i in range(self.number_of_events):
            idx_offset = EVT_REG_IDX_OFFSET + (i - 1) * 4
            val_offset = EVT_REG_VAL_OFFSET + (i - 1) * 4

            idx = int.from_bytes(p[idx_offset : idx_offset + 2], ENDIAN)
            val = int.from_bytes(p[val_offset : val_offset + 2], ENDIAN)

            self.events.append(EventData(idx, val))


@dataclass
class EventData:
    register_index: int
    register_value: int

    sensor_id: Optional[bytes] = None


class packet_builder:
    _pid = 0

    @staticmethod
    def scan(type: str = "XXX", mac: str = "???") -> bytes:
        return f"SiHAS_{type}_{mac}".encode()

    @staticmethod
    def pid() -> int:
        if packet_builder._pid >= 0xFF:
            packet_builder._pid = 0
        packet_builder._pid += 1
        return packet_builder._pid

    @staticmethod
    def poll() -> bytes:
        p = (
            packet_builder._build_header(6)
            + _FUNCTION_CODE_POLL
            + (0).to_bytes(2, ENDIAN)
            + (64).to_bytes(2, ENDIAN)
        )
        return p

    @staticmethod
    def command(reg_idx: int, reg_val: int) -> bytes:
        _LOGGER.debug(f"setting register {reg_idx} as {reg_val}")

        p = (
            packet_builder._build_header(6)
            + _FUNCTION_CODE_COMMAND
            + reg_idx.to_bytes(2, ENDIAN)
            + reg_val.to_bytes(2, ENDIAN)
        )
        return p

    @staticmethod
    def advertise(ip: str, port: int):
        """Assamble a packet which adverting server's address to a device.

        Parameters
        ----------
        ip
            Server's local ip e.g. "192.168.2.8"

        port
            Server's listening port
        """

        p: bytes = (
            packet_builder._build_header(6)
            + _FUNCTION_CODE_SET_SERVER_ADDRESS
            + port.to_bytes(2, ENDIAN)
            + socket.inet_aton(ip)
            + b"\xbc\x16"
        )
        return p

    @staticmethod
    def _build_header(dlen: int) -> bytes:
        def _calc_checksum(b: bytes) -> bytes:
            return (sum(b) & 0xFF).to_bytes(1, ENDIAN)

        h = (
            packet_builder.pid().to_bytes(2, ENDIAN)
            + (0x00).to_bytes(1, ENDIAN)
            + (0x00).to_bytes(1, ENDIAN)
            + dlen.to_bytes(2, ENDIAN)
        )

        h += _calc_checksum(h)

        assert len(h) == HEADER_LENGTH

        return h

    @staticmethod
    def extract_registers(p: bytes) -> List[int]:
        """
        Raise
        -----
            ModbusNotEnabledError
                Raise when dose not enabled modbus feature.
                Should capture this exception and rethrow with IP addr.

            PacketSizeError
                Raise when packet length dose not match.
                It could occur when modbus feature dose not enabled.
        """

        def isModbusEnabled(p: bytes) -> bool:
            """If Function Code of response packet returned with bitwised OR by 0x08, NAK"""
            return not (p[POS_FUNCTION_CODE] & 0x08 != 0)

        def hasValidSize(p: bytes) -> bool:
            return len(p) == POLL_RESPONSE_LENGTH

        def bytesToU16Arry(p: bytes) -> List[int]:
            registers = list()
            for i in range(64):
                offset = 9 + i * 2
                registers.append(int.from_bytes(p[offset : offset + 2], ENDIAN))
            return registers

        if not isModbusEnabled(p):
            raise ModbusNotEnabledError()

        if not hasValidSize(p):
            raise PacketSizeError(expect=POLL_RESPONSE_LENGTH, actual=len(p))

        return bytesToU16Arry(p)

    @staticmethod
    def parse_server_recv(p: bytes) -> Union[PeriodicUpdatePacket, EventPacketPacket, None]:
        if len(p) < 55:
            return None

        fc = p[POS_FUNCTION_CODE]

        if fc == FC_EVENT:
            return EventPacketPacket(p)
        elif fc == FC_PERIODIC:
            return PeriodicUpdatePacket(p)

        return None
