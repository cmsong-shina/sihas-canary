from datetime import datetime
from logging import StringTemplateStyle
from typing import Callable, Dict

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
        if ":" in s:
            return s

        # ['AB', 'CD', 'EF', '12', '34', '56']
        mac_parts = [s[2 * i : 2 + 2 * i] for i in range(6)]
        return ":".join(mac_parts)

    @staticmethod
    def remove_colon(s: str):
        return s.replace(":", "")


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
