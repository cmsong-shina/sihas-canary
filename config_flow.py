"""Config flow for sihas_canary integration."""
from __future__ import annotations

import logging
from typing import Any, List

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
from .sihas_base import SihasBase
from .util import MacConv

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for sihas_canary."""

    VERSION = 1

    def __init__(self) -> None:
        self.sihas: SihasBase
        self.data: map = {}

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

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input:
            # TODO: may need to confirm user input and check communicate with device.
            self.data["ip"] = user_input["ip"]
            self.data["mac"] = user_input["mac"]
            self.data["type"] = user_input["type"]
            self.data["cfg"] = user_input["cfg"]
            self.data["nickname"] = user_input["nickname"]
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
                vol.Required("nickname"): str,
            }
        )

        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
