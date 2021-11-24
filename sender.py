import logging
import socket
import typing

from .const import BUF_SIZE, DEFAULT_TIMEOUT, PORT
from .errors import ModbusNotEnabledError

_LOGGER = logging.getLogger(__name__)


def send(data: bytes, ip: str, port: int = PORT, retry: int = 1) -> bytes:
    """Send packet to device

    Raise ModbusNotEnabledError, socket.timeout and others
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    while retry:
        try:
            sock.sendto(data, (ip, port))
            sock.settimeout(DEFAULT_TIMEOUT)
            resp = sock.recv(BUF_SIZE)
            if (resp[7] & 0x08) != 0:
                raise ModbusNotEnabledError(ip)
            return resp

        except socket.timeout:
            retry -= 1

    raise socket.timeout


def scan(data: bytes, ip: str) -> typing.Optional[bytes]:
    retry = 3
    while retry:
        try:
            _LOGGER.debug(f"scanning device, {ip=} {data=}")
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.sendto(data, (ip, 502))
            sock.settimeout(2)
            return sock.recv(BUF_SIZE)
        except socket.timeout:
            retry -= 1
        except Exception as e:
            _LOGGER.error(f"failed to scan device: , {e}")
            break
    _LOGGER.warn(f"failed to scan device: timeout")
    return None
