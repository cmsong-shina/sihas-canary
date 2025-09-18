"""Config flow for sihas integration."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, cast

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.service_info import dhcp, zeroconf
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_CFG,
    CONF_HOST,
    CONF_HOSTNAME,
    CONF_IP,
    CONF_MAC,
    CONF_NAME,
    CONF_PROP,
    CONF_TYPE,
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
    """Handle a config flow for sihas."""

    VERSION = 1

    def __init__(self) -> None:
        self.sihas: SihasBase
        self.data: Dict[str, Any] = {}

    async def async_step_zeroconf(self, discovery_info: zeroconf.ZeroconfServiceInfo) -> ConfigFlowResult:
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
        hostname_parts: List[str] = discovery_info.hostname.split(".")[0].split("_")

        self.data[CONF_IP] = discovery_info.host
        self.data[CONF_MAC] = MacConv.insert_colon(MAC_OUI + hostname_parts[2]).lower()
        self.data[CONF_TYPE] = hostname_parts[1].upper()
        self.data[CONF_CFG] = int(discovery_info.properties[CONF_CFG], 16)

        if self.data[CONF_TYPE] not in SUPPORT_DEVICE:
            return self.async_abort(reason=f"not supported device type: {self.data[CONF_TYPE]}")

        await self.async_set_unique_id(self.data[CONF_MAC])
        self._abort_if_unique_id_configured(updates={CONF_IP: discovery_info.host})

        # display device on integrations page to advertise to user
        self.context.update(
            {
                "title_placeholders": {
                    CONF_TYPE: self.data[CONF_TYPE],
                    CONF_MAC: self.data[CONF_MAC],
                }
            }
        )

        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:

        if user_input:
            self.data[CONF_NAME] = user_input[CONF_NAME]
            return self.async_create_entry(
                title=self.data[CONF_TYPE],
                data=self.data,
            )

        return self.async_show_form(
            step_id="zeroconf_confirm",
            # data_schema will used to obtain data from user
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME, default=self.data[CONF_TYPE] + self.data[CONF_MAC]
                    ): cv.string,
                }
            ),
            # description_placeholders will used to format string
            description_placeholders={
                CONF_MAC: self.data[CONF_MAC],
                CONF_TYPE: self.data[CONF_TYPE],
            },
        )

    # NOTE:
    #   DHCP discovery assumed does not work in develop environment(via VSC debugpy).
    #   On release enviornment(such as rpi HAOS), works well.
    #   It may associated about permission(which scapy or aiodiscover use), IMO.
    async def async_step_dhcp(self, discovery_info: dhcp.DhcpServiceInfo):
        # data will come like
        #   {'ip': '192.168.xxx.xxx', 'hostname': 'esp[-_][0-9a-f]{12}', 'macaddress': '123456abcdef'}
        _LOGGER.info(f"sihas device found via dhcp: {discovery_info}")

        # wait for device
        await asyncio.sleep(10)

        ip = cast(str, discovery_info.ip)
        mac = cast(str, discovery_info.macaddress)

        await self.async_set_unique_id(MacConv.insert_colon(mac))
        self._abort_if_unique_id_configured(updates={CONF_IP: ip})

        # SiHAS Scan
        if resp := scan(pb.scan(), ip):
            scan_info = parse_scan_message(resp)
            _LOGGER.debug(f"sihas device scanned: {scan_info}")

            if not scan_info[CONF_MAC] == MacConv.insert_colon(mac):
                _LOGGER.debug(
                    f"device scanned but ip does not match: found={MacConv.insert_colon(mac)}, scanned={scan_info[CONF_MAC]}"
                )
                return self.async_abort(reason="device scanned but ip does not match")

            self.data[CONF_IP] = scan_info[CONF_IP]
            self.data[CONF_MAC] = scan_info[CONF_MAC].lower()
            self.data[CONF_TYPE] = scan_info[CONF_TYPE]
            self.data[CONF_CFG] = scan_info[CONF_CFG]

            if self.data[CONF_TYPE] not in SUPPORT_DEVICE:
                return self.async_abort(reason=f"not supported device type: {self.data[CONF_TYPE]}")

            self.context.update(
                {
                    "title_placeholders": {
                        CONF_TYPE: self.data[CONF_TYPE],
                        CONF_MAC: self.data[CONF_MAC],
                    }
                }
            )

            return await self.async_step_zeroconf_confirm()

        else:
            # if not match, abort
            _LOGGER.warning(f"found device but did not response about scan: {discovery_info}")
            return self.async_abort(reason="can not scan found device")

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input:
            # TODO: may need to confirm user input and check communicate with device.
            self.data[CONF_IP] = user_input[CONF_IP]
            self.data[CONF_MAC] = user_input[CONF_MAC]
            self.data[CONF_TYPE] = user_input[CONF_TYPE]
            self.data[CONF_CFG] = user_input[CONF_CFG]
            self.data[CONF_NAME] = user_input[CONF_NAME]
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data=self.data,
            )

        DATA_SCHEMA = vol.Schema(
            {
                vol.Required(CONF_IP): str,
                vol.Required(CONF_MAC): str,
                vol.Required(CONF_TYPE): vol.In(SUPPORT_DEVICE),
                vol.Required(CONF_CFG): int,
                vol.Required(CONF_NAME): str,
            }
        )

        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
