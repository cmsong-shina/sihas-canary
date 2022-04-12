"""Constants for the sihas_canary integration."""
from typing import Final, List, final

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.climate import PLATFORM_SCHEMA

DOMAIN: Final = "sihas_canary"
ATTRIBUTION: Final = "SiHAS IoT Device"
ENDIAN: Final = "big"

DEVICE_TYPE: Final = {
    "WAP": 0,
    "RXM": 1,
    "TCM": 2,
    "OCM": 3,
    "STM": 4,
    "CCM": 5,
    "DCM": 6,
    "ACM": 7,
    "GCM": 8,
    "SDM": 9,
    "SCM": 10,
    "HCM": 11,
    "AQM": 12,
    "BCM": 13,
    "HVM": 14,
    "SGW": 15,
    "LCM": 16,
    "PMM": 17,
    "PIM": 18,
    "RBM": 19,
    "HGW": 20,
    "SBM": 21,
}

SUPPORT_DEVICE: Final[List[str]] = [
    "ACM",
    "BCM",
    "AQM",
    "CCM",
    "HCM",
    "SBM",
    "PMM",
    "STM",
]

DEFAULT_TIMEOUT: Final = 0.5
PORT: Final = 502
BUF_SIZE: Final = 1024

MAC_OUI: Final = "a82bd6"

REG_LENG: Final = 64

# configuration variables
CONF_NAME: Final = "name"
CONF_IP: Final = "ip"
CONF_MAC: Final = "mac"
CONF_TYPE: Final = "type"
CONF_SSID: Final = "ssid"
CONF_CFG: Final = "cfg"

# for config flow
CONF_PROP: Final = "properties"
CONF_HOST: Final = "host"
CONF_HOSTNAME: Final = "hostname"


# icons
ICON_COOLER: Final = "mdi:air-conditioner"
ICON_HEATER: Final = "mdi:thermostat"
ICON_LIGHT_BULB: Final = "mdi:lightbulb-variant"
ICON_POWER_METER: Final = "mdi:transmission-tower"
ICON_POWER_SOCKET: Final = "mdi:power-socket-de"

DEFAULT_DEBOUNCE_DURATION: Final = 3
DEFAULT_PARALLEL_UPDATES: Final = 5


SIHAS_PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_IP): cv.string,
        vol.Required(CONF_MAC): cv.string,
        vol.Required(CONF_TYPE): cv.string,
        vol.Required(CONF_CFG): cv.positive_int,
    }
)
