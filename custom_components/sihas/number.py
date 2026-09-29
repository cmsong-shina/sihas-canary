"""BCM temperature set points independent of power and operation mode."""

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .bcm import (
    HOT_WATER,
    ONDOL,
    ROOM,
    TARGET_REGISTERS,
    BcmCoordinator,
    BcmEntity,
    get_coordinator,
)
from .const import CONF_TYPE

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    if entry.data[CONF_TYPE] != "BCM":
        return
    coordinator = get_coordinator(hass, entry)
    entities = [
        BcmTemperature(coordinator, "room_temperature", ROOM),
        BcmTemperature(coordinator, "ondol_temperature", ONDOL),
    ]
    if coordinator.hot_water_kind == "linear":
        entities.append(BcmTemperature(coordinator, "hot_water_temperature", HOT_WATER))
    async_add_entities(entities)


class BcmTemperature(BcmEntity, NumberEntity):
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: BcmCoordinator, key: str, mode: str) -> None:
        super().__init__(coordinator, key)
        self.mode_name = mode

    @property
    def available(self) -> bool:
        return super().available and self._limits is not None

    @property
    def _limits(self) -> tuple[int, int] | None:
        return self.coordinator.temperature_limits(
            self.coordinator.data, self.mode_name
        )

    @property
    def native_min_value(self) -> float:
        return self._limits[0] if self._limits else 0

    @property
    def native_max_value(self) -> float:
        return self._limits[1] if self._limits else 0

    @property
    def native_value(self) -> float:
        return self.coordinator.data[TARGET_REGISTERS[self.mode_name]]

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_temperature(value, self.mode_name)
