"""The sihas integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .bcm import BcmCoordinator
from .const import CONF_TYPE, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = [
    "binary_sensor",
    "button",
    "climate",
    "cover",
    "light",
    "number",
    "select",
    "sensor",
    "switch",
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    # NOTE: how about checking supported type at here?
    _LOGGER.info(f"entry setuped: {entry.data}")

    # BCM를 여러 엔티티로 구성하기위해 전용 코디네이터를 구성한다.
    if entry.data[CONF_TYPE] == "BCM":
        coordinator = BcmCoordinator(hass, entry)
        await coordinator.async_config_entry_first_refresh()
        coordinator.discover_model()
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    _LOGGER.info(f"entry unloadded: {entry.data}")
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok and entry.data[CONF_TYPE] == "BCM":
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()
    return unload_ok
