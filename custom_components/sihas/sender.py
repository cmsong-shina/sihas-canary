import logging
import socket

from .const import BUF_SIZE, DEFAULT_TIMEOUT, PORT
from .errors import ModbusNotEnabledError
from .util import IpConv

_LOGGER = logging.getLogger(__name__)


def send(data: bytes, ip: str, port: int = PORT, retry: int = 1) -> bytes:
    """Send packet to device

    Raise ModbusNotEnabledError, socket.timeout and others
    """

    ip = IpConv.remove_leading_zero(ip)
    last_timeout = None
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(DEFAULT_TIMEOUT)
        for _ in range(retry):
            try:
                sock.sendto(data, (ip, port))
                resp = sock.recv(BUF_SIZE)
                if (resp[7] & 0x08) != 0:
                    raise ModbusNotEnabledError(ip)
                return resp

            except TimeoutError as err:
                last_timeout = err

    raise TimeoutError(
        f"failed to request to {ip}:{port}: timed out."
    ) from last_timeout


def scan(data: bytes, ip: str, retry: int = 10) -> str | None:
    while retry:
        try:
            _LOGGER.debug(f"scanning device, {ip=} {data=}")
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.sendto(data, (ip, 502))
            sock.settimeout(2)
            return sock.recv(BUF_SIZE).decode()
        except TimeoutError:
            retry -= 1
        except Exception as e:
            _LOGGER.error(f"failed to scan device: , {e}")
            break
    _LOGGER.warning("failed to scan device: timeout")
    return None
