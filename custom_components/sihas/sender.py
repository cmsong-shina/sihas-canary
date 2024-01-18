import asyncio
import logging
import socket
import typing

from .const import BUF_SIZE, DEFAULT_TIMEOUT, PORT
from .errors import ModbusNotEnabledError
from .util import IpConv

_LOGGER = logging.getLogger(__name__)


def send(data: bytes, ip: str, port: int = PORT, retry: int = 1) -> bytes:
    """Send packet to device

    Raise ModbusNotEnabledError, socket.timeout and others
    """

    ip = IpConv.remove_leading_zero(ip)
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


def scan(data: bytes, ip: str, retry: int = 10) -> typing.Optional[str]:
    while retry:
        try:
            _LOGGER.debug(f"scanning device, {ip=} {data=}")
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.sendto(data, (ip, 502))
            sock.settimeout(2)
            return sock.recv(BUF_SIZE).decode()
        except socket.timeout:
            retry -= 1
        except Exception as e:
            _LOGGER.error(f"failed to scan device: , {e}")
            break
    _LOGGER.warn(f"failed to scan device: timeout")
    return None

async def _send_message(sock: socket.socket, address: tuple[str, int], message: bytes):
    """
    Just async wrap of socekt.sendto()
    """
    sock.sendto(message, address)

async def _receive_message(loop: asyncio.AbstractEventLoop, sock: socket.socket):
    """
    Just async wrap of eventloop.cock_recv()
    """
    return await loop.sock_recv(sock, 1024)

async def send_async(loop: asyncio.AbstractEventLoop, data: bytes, ip: str, port: int = PORT, retry: int = 1) -> bytes:
    """
    # Example

        ```py
        async def main():
            result = await scan_async(loop, "SiHAS_XXX_???".encode(), "255.255.255.255", 1)
            print(result)

        if __name__ == "__main__":
            loop = asyncio.get_event_loop()
            loop.run_until_complete(main())
        ```
    """
    raddr = (ip, port)

    while retry:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.settimeout(DEFAULT_TIMEOUT)
                send_task = _send_message(sock, raddr, data)
                receive_task = _receive_message(loop, sock)
                _, received_message = await asyncio.gather(send_task, receive_task)
                return received_message

        except socket.timeout:
            retry -= 1

    raise socket.timeout


async def scan_async(loop: asyncio.AbstractEventLoop, data: bytes, ip: str, retry: int = 10) -> typing.Optional[str]:
    """
    # Example

        ```py
        async def main():
            result = await scan_async(loop, "SiHAS_XXX_???".encode(), "255.255.255.255", 1)
            print(result)

        if __name__ == "__main__":
            loop = asyncio.get_event_loop()
            loop.run_until_complete(main())
        ```

    # Note
        If we need sender address, like `recvfrom`, should concider rewrite using `create_datagram_endpoint()`.
    """
    raddr = (ip, 502)

    while retry:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                sock.settimeout(2)
                send_task = _send_message(sock, raddr, data)
                receive_task = _receive_message(loop, sock)
                _, received_message = await asyncio.gather(send_task, receive_task)
                return received_message.decode()

        except socket.timeout:
            retry -= 1

