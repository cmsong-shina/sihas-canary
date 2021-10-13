import socket

from .const import BUF_SIZE, DEFAULT_TIMEOUT, PORT
from .errors import ModbusNotEnabledError


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
