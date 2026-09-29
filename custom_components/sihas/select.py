"""BCM operation mode, presence and model-specific hot water levels."""

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .bcm import (
    OPERATION_MODES,
    PRESENCE_OPTIONS,
    BcmCoordinator,
    BcmEntity,
    Register,
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
    entities = [BcmOperationMode(coordinator), BcmPresence(coordinator)]
    if coordinator.hot_water_options:
        entities.append(BcmHotWaterLevel(coordinator))
    async_add_entities(entities)


class BcmOperationMode(BcmEntity, SelectEntity):
    _attr_options = OPERATION_MODES

    def __init__(self, coordinator: BcmCoordinator) -> None:
        super().__init__(coordinator, "operation_mode")

    @property
    def current_option(self) -> str | None:
        return self.coordinator.data.operation_mode

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_operation_mode(option)


class BcmPresence(BcmEntity, SelectEntity):
    _attr_options = PRESENCE_OPTIONS

    def __init__(self, coordinator: BcmCoordinator) -> None:
        super().__init__(coordinator, "presence")

    @property
    def current_option(self) -> str | None:
        value = self.coordinator.data[Register.AWAY]
        return PRESENCE_OPTIONS[value] if value in (0, 1) else None

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_presence(option)


class BcmHotWaterLevel(BcmEntity, SelectEntity):
    def __init__(self, coordinator: BcmCoordinator) -> None:
        super().__init__(coordinator, "hot_water_level")
        self._attr_options = coordinator.hot_water_options

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.coordinator.data.hot_water_kind == self.coordinator.hot_water_kind
        )

    @property
    def current_option(self) -> str | None:
        value = self.coordinator.data[Register.HOT_WATER_TARGET]
        return self.options[value] if 0 <= value < len(self.options) else None

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_hot_water_level(option)
