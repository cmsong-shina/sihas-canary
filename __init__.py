"""The sihas_canary integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = [
    "climate",
    "light",
    "sensor",
    "switch",
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    # NOTE: how about checking supported type at here?
    _LOGGER.info(f"entry setuped: {entry}")
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    _LOGGER.info(f"entry unloadded: {entry}")
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    return unload_ok
