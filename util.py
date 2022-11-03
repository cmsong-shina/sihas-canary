from datetime import datetime
from typing import Callable, Dict, List, Literal

from .const import DEFAULT_DEBOUNCE_DURATION


class Debouncer:
    """Simple Debouncer.

    Attributes
    ----------
        _duration        interval duration in seconds
        _callback        function which called by debouncer
        _last_excuted    last excuted time
    """

    def __init__(self, callback: Callable, duration: int = DEFAULT_DEBOUNCE_DURATION) -> None:
        self._last_excuted = datetime.now()
        self._duration = duration
        self._callback = callback

    def run(self, force=False) -> bool:
        """
        Try to run callback and return True if success.
        """
        t = datetime.now()
        if force or ((t - self._last_excuted).total_seconds() > self._duration):
            self._last_excuted = t
            self._callback()
            return True
        return False


class IpConv:
    @staticmethod
    def remove_leading_zero(s: str) -> str:
        # ".".join([str(int(i)) for i in ip.split(".")])
        import re

        return re.sub(r"\b0+(\d)", r"\1", s)


class MacConv:
    @staticmethod
    def insert_colon(s: str):
        """

        Example
        -------
        ```
        MacConv.insert_colon('ab2bd6123456') # 'ab:2b:d6:12:34:56'
        ```
        """
        if ":" in s:
            return s

        # ['AB', 'CD', 'EF', '12', '34', '56']
        mac_parts = [s[2 * i : 2 + 2 * i] for i in range(6)]
        return ":".join(mac_parts)

    @staticmethod
    def remove_colon(s: str):
        return s.replace(":", "")

    @staticmethod
    def to_string(b: bytes):
        """Convert bytes to lower hex string, delimited by colon

        Example
        -------
        ```
        MacConv.to_string(b'\xAB\x2B\xD6\x12\x34\x56') # 'ab:2b:d6:12:34:56'
        ```
        """
        return b.hex(":").lower()


def parse_scan_message(msg: str) -> Dict:
    type = msg[6:9]
    version = msg[11:16]
    mac = msg[21:38]
    ip = msg[42:57]
    config = int(msg[62:64], 16)

    return {
        "type": type,
        "mac": mac,
        "ip": IpConv.remove_leading_zero(ip),
        "cfg": config,
    }


class BytesConv:
    @staticmethod
    def ball_u16(p: bytes, endian: Literal["little", "big"]) -> List[int]:
        """Convert list of u8 to list of u16

        [0x12, 0x34, 0x56, 0x78] => [0x1234, 0x5678]
        """

        if p % 2:
            raise ValueError("length of p must be multiple of 2")
        return [int.from_bytes(p[i : i + 2], endian) for i in range(0, len(p), 2)]

    @staticmethod
    def ball_u32(p: bytes, endian: Literal["little", "big"]) -> List[int]:
        """Convert list of u8 to list of u32

        [0x12, 0x34, 0x56, 0x78] => [0x12345678]
        """

        if p % 4:
            raise ValueError("length of p must be multiple of 4")
        return [int.from_bytes(p[i : i + 4], endian) for i in range(0, len(p), 4)]


def register_put_u32(b1: int, b2: int) -> int:
    return b1 | (b2 << 16)
