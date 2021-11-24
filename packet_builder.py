import logging
from typing import Final, List

from .const import ENDIAN
from .errors import ModbusNotEnabledError, PacketSizeError

_LOGGER = logging.getLogger(__name__)


_FUNCTION_CODE_POLL: Final = (0x03).to_bytes(1, ENDIAN)
_FUNCTION_CODE_COMMAND: Final = (0x06).to_bytes(1, ENDIAN)

POS_FUNCTION_CODE: Final = 7

POLL_RESPONSE_LENGTH: Final = 137
HEADER_LENGTH: Final = 7


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
