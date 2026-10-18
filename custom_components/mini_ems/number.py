"""Number platform for Mini EMS - Configurable settings."""
from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MiniEmsCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Mini EMS number entities."""
    coordinator: MiniEmsCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        MiniEmsBatteryMinSocNumber(coordinator, entry),
        MiniEmsBatteryMaxSocNumber(coordinator, entry),
    ])


class MiniEmsBatteryMinSocNumber(CoordinatorEntity[MiniEmsCoordinator], NumberEntity):
    """Minimum battery SOC setpoint."""

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        inv_name = entry.data.get("inverter_name", entry.data.get("username", "inverter"))
        self._attr_unique_id = f"mini_ems_{entry.entry_id}_battery_min_soc"
        self._attr_name = "Pin SOC tối thiểu (Min Battery SOC)"
        self._attr_native_min_value = 5
        self._attr_native_max_value = 95
        self._attr_native_step = 5
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_mode = NumberMode.SLIDER
        self._attr_icon = "mdi:battery-low"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"Mini EMS - {inv_name}",
            "manufacturer": "Donnergy (Shenzhen DaNeng)",
            "model": entry.data.get("inverter_name", "Hybrid Inverter"),
            "configuration_url": "https://mini-ems.com",
        }
        self._value = 20.0

    @property
    def native_value(self) -> float:
        data = self.coordinator.data or {}
        inv = data.get("inverter", {})
        return float(inv.get("batteryMinSOC") or inv.get("minSOC") or self._value)

    async def async_set_native_value(self, value: float) -> None:
        self._value = value
        inv_id = self._entry.data.get("inverter_id")
        try:
            await self.coordinator.api.async_send_instruction({
                "inverterId": inv_id,
                "batteryMinSOC": int(value),
                "type": "batteryMinSOC",
            })
        except Exception as err:
            _LOGGER.error("Failed to set min SOC: %s", err)


class MiniEmsBatteryMaxSocNumber(CoordinatorEntity[MiniEmsCoordinator], NumberEntity):
    """Maximum battery SOC setpoint."""

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        inv_name = entry.data.get("inverter_name", entry.data.get("username", "inverter"))
        self._attr_unique_id = f"mini_ems_{entry.entry_id}_battery_max_soc"
        self._attr_name = "Pin SOC tối đa (Max Battery SOC)"
        self._attr_native_min_value = 10
        self._attr_native_max_value = 100
        self._attr_native_step = 5
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_mode = NumberMode.SLIDER
        self._attr_icon = "mdi:battery-high"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"Mini EMS - {inv_name}",
            "manufacturer": "Donnergy (Shenzhen DaNeng)",
            "model": entry.data.get("inverter_name", "Hybrid Inverter"),
            "configuration_url": "https://mini-ems.com",
        }
        self._value = 100.0

    @property
    def native_value(self) -> float:
        data = self.coordinator.data or {}
        inv = data.get("inverter", {})
        return float(inv.get("batteryMaxSOC") or inv.get("maxSOC") or self._value)

    async def async_set_native_value(self, value: float) -> None:
        self._value = value
        inv_id = self._entry.data.get("inverter_id")
        try:
            await self.coordinator.api.async_send_instruction({
                "inverterId": inv_id,
                "batteryMaxSOC": int(value),
                "type": "batteryMaxSOC",
            })
        except Exception as err:
            _LOGGER.error("Failed to set max SOC: %s", err)
