from __future__ import annotations

from datetime import timedelta

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_CFG,
    CONF_IP,
    CONF_MAC,
    CONF_NAME,
    CONF_TYPE,
    DEFAULT_PARALLEL_UPDATES,
    SIHAS_PLATFORM_SCHEMA,
)
from .sihas_base import SihasEntity
from .gcm import GcmCoordinator, GcmEntity, get_coordinator

SCAN_INTERVAL = timedelta(seconds=10)

PARALLEL_UPDATES = DEFAULT_PARALLEL_UPDATES
PLATFORM_SCHEMA = SIHAS_PLATFORM_SCHEMA


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    if entry.data[CONF_TYPE] == "GCM":
        coordinator = get_coordinator(hass, entry)
        async_add_entities([GcmValveSensor(coordinator), GcmFireSensor(coordinator)])
    elif entry.data[CONF_TYPE] == "ACM":
        async_add_entities(
            [
                AcmVibrationSensor(
                    entry.data[CONF_IP],
                    entry.data[CONF_MAC],
                    entry.data[CONF_TYPE],
                    entry.data[CONF_CFG],
                    entry.data[CONF_NAME],
                ),
            ],
        )

class AcmVibrationSensor(SihasEntity, BinarySensorEntity):
    def __init__(
        self,
        ip: str,
        mac: str,
        device_type: str,
        config: int,
        name: str | None = None,
    ):
        super().__init__(
            ip=ip,
            mac=mac,
            device_type=device_type,
            config=config,
            name=f"{name} 진동 상태",
        )
        self._attr_device_class = BinarySensorDeviceClass.VIBRATION
        
    
    def update(self):
        if regs := self.poll():            
            self._attr_is_on = regs[7] != 0


class GcmValveSensor(GcmEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.OPENING

    def __init__(self, coordinator: GcmCoordinator) -> None:
        super().__init__(coordinator, "valve_open")

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.valve_open


class GcmFireSensor(GcmEntity, BinarySensorEntity):
    _attr_icon = "mdi:fire-alert"

    def __init__(self, coordinator: GcmCoordinator) -> None:
        super().__init__(coordinator, "fire_alarm")

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.fire_alarm
