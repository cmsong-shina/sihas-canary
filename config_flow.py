"""Config flow for sihas_canary integration."""
from __future__ import annotations

import logging
import time
import asyncio
from typing import Any, Dict, List, cast

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import (
    CONF_CFG,
    CONF_HOST,
    CONF_HOSTNAME,
    CONF_NAME,
    CONF_PROP,
    DOMAIN,
    MAC_OUI,
    SUPPORT_DEVICE,
)
from .packet_builder import packet_builder as pb
from .sender import scan, send
from .sihas_base import SihasBase
from .util import MacConv, parse_scan_message

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for sihas_canary."""

    VERSION = 1

    def __init__(self) -> None:
        self.sihas: SihasBase
        self.data: Dict[str, Any] = {}

    async def async_step_zeroconf(self, discovery_info: DiscoveryInfoType) -> FlowResult:
        _LOGGER.debug("device found by zeroconf: %s", discovery_info)

        # {
        #     "host": "192.168.3.17",
        #     "hostname": "sihas_acm_0a2998.local.",
        #     "properties": {
        #         "version": "1.35",
        #         "type": "acm",
        #         "cfg": "0"
        #     }
        # }

        # ['sihas', 'acm', '0a2998']
        hostname_parts: List[str] = discovery_info[CONF_HOSTNAME].split(".")[0].split("_")

        self.data["ip"] = discovery_info[CONF_HOST]
        self.data["mac"] = MacConv.insert_colon(MAC_OUI + hostname_parts[2]).lower()
        self.data["type"] = hostname_parts[1].upper()
        self.data["cfg"] = int(discovery_info[CONF_PROP][CONF_CFG], 16)

        if self.data["type"] not in SUPPORT_DEVICE:
            return self.async_abort(reason=f"not supported device type: {self.data['type']}")

        await self.async_set_unique_id(self.data["mac"])
        self._abort_if_unique_id_configured()

        # display device on integrations page to advertise to user
        self.context.update(
            {
                "title_placeholders": {
                    "type": self.data["type"],
                    "mac": self.data["mac"],
                }
            }
        )

        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:

        if user_input:
            self.data["name"] = user_input["name"]
            return self.async_create_entry(
                title=self.data["type"],
                data=self.data,
            )

        return self.async_show_form(
            step_id="zeroconf_confirm",
            # data_schema will used to obtain data from user
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME, default=self.data["type"] + self.data["mac"]
                    ): cv.string,
                }
            ),
            # description_placeholders will used to format string
            description_placeholders={
                "mac": self.data["mac"],
                "type": self.data["type"],
            },
        )

    # NOTE:
    #   DHCP discovery assumed does not work in develop environment(via VSC debugpy).
    #   On release enviornment(such as rpi HAOS), works well.
    #   It may associated about permission(which scapy or aiodiscover use), IMO.
    async def async_step_dhcp(self, discovery_info: DiscoveryInfoType):
        # data will come like
        #   {'ip': '192.168.xxx.xxx', 'hostname': 'esp[-_][0-9a-f]{12}', 'macaddress': '123456abcdef'}
        _LOGGER.warn(f"sihas device found via dhcp: {discovery_info}")

        # wait for device
        time.sleep(10)

        ip = cast(str, discovery_info.get("ip"))
        mac = cast(str, discovery_info.get("macaddress"))

        await self.async_set_unique_id(MacConv.insert_colon(mac))
        self._abort_if_unique_id_configured()

        # SiHAS Scan
        if resp := scan(pb.scan(), ip):
            scan_info = parse_scan_message(resp)
            _LOGGER.debug(f"sihas device scanned: {scan_info}")

            if not scan_info["mac"] == MacConv.insert_colon(mac):
                _LOGGER.debug(
                    f"device scanned but ip does not match: found={MacConv.insert_colon(mac)}, scanned={scan_info['mac']}"
                )
                return self.async_abort(reason="device scanned but ip does not match")

            self.data["ip"] = scan_info["ip"]
            self.data["mac"] = scan_info["mac"].lower()
            self.data["type"] = scan_info["type"]
            self.data["cfg"] = scan_info["cfg"]

            if self.data["type"] not in SUPPORT_DEVICE:
                return self.async_abort(reason=f"not supported device type: {self.data['type']}")

            self.context.update(
                {
                    "title_placeholders": {
                        "type": self.data["type"],
                        "mac": self.data["mac"],
                    }
                }
            )

            return await self.async_step_zeroconf_confirm()

        else:
            # if not match, abort
            _LOGGER.warn(f"found device but did not response about scan: {discovery_info}")
            return self.async_abort(reason="can not scan found device")

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input:
            # TODO: may need to confirm user input and check communicate with device.
            self.data["ip"] = user_input["ip"]
            self.data["mac"] = user_input["mac"]
            self.data["type"] = user_input["type"]
            self.data["cfg"] = user_input["cfg"]
            self.data["name"] = user_input["name"]
            return self.async_create_entry(
                title=self.data["type"],
                data=self.data,
            )

        DATA_SCHEMA = vol.Schema(
            {
                vol.Required("ip"): str,
                vol.Required("mac"): str,
                vol.Required("type"): vol.In(SUPPORT_DEVICE),
                vol.Required("cfg"): int,
                vol.Required("name"): str,
            }
        )

        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
