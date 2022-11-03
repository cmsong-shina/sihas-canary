from __future__ import annotations
import logging
import math
from abc import abstractmethod
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from typing import Dict, List, Optional, cast
import asyncio
import socket
from xml.dom.minidom import Entity

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_CFG,
    CONF_IP,
    CONF_MAC,
    CONF_NAME,
    CONF_TYPE,
    DEFAULT_PARALLEL_UPDATES,
    DOMAIN,
    ICON_COOLER,
    ICON_HEATER,
    SIHAS_PLATFORM_SCHEMA,
)
from .errors import ModbusNotEnabledError, PacketSizeError
from .packet_builder import packet_builder as pb, EventData, EventPacketPacket, PeriodicUpdatePacket
from .sender import send
from .util import MacConv
from .sihas_base import SihasEntity, SihasProxy

_LOGGER = logging.getLogger(__name__)


class SiHASCoordinator(DataUpdateCoordinator, asyncio.DatagramProtocol):
    """Coordinator to listen event or periodical update packet

    To use this coordinator,

        # listen socket
        addr = ("", 0)  # any addr any port
        self.sock = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
        self.sock.bind(addr)

        # add to event loop
        loop = asyncio.get_running_loop()
        await loop.create_datagram_endpoint(lambda: self, sock=self.sock)

    """

    async def __init__(self, hass):
        super().__init__(
            hass,
            _LOGGER,
            name="SiHAS Coordinator",
        )
        self.hass = hass

    def datagram_received(self, data, addr):
        """Handle incoming datagram messages."""

        host_ip = addr[0]
        _LOGGER.info(f"Server recv message from {host_ip}: ", data.hex())

        # parse
        pkt = pb.parse_server_recv(data)
        if not pkt:
            return

        mac = MacConv.to_string(pkt.meta.mac)

        # check wether device is known
        uid = f""

        device = self.hass.data[DOMAIN][mac]
        if not device:
            return

        # update device
        if isinstance(pkt, EventPacketPacket):
            device.handle_event(pkt)  # FIXME:
        elif isinstance(pkt, PeriodicUpdatePacket):
            device.handle_update(pkt)  # FIXME:
        return

    def _is_exist() -> bool:
        pass

    def get_uid(meta):
        pass
