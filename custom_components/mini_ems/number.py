"""Number platform for Mini EMS - Configurable settings."""
from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfPower, UnitOfElectricCurrent
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
    stored = hass.data[DOMAIN][entry.entry_id]
    if "hub" in stored:
        return

    coordinator: MiniEmsCoordinator = stored.get("coordinator") or stored
    async_add_entities([
        MiniEmsBatteryMinSocNumber(coordinator, entry),
        MiniEmsBatteryMaxSocNumber(coordinator, entry),
        MiniEmsMaxExportPowerNumber(coordinator, entry),
        MiniEmsMaxChargeCurrentNumber(coordinator, entry),
        MiniEmsMaxDischargeCurrentNumber(coordinator, entry),
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
            inv_name = self._entry.data.get("inverter_name")
            await self.coordinator.api.async_send_instruction({
                "inverterName": inv_name,
                "inverterId": inv_id,
                "batteryMaxSOC": int(value),
                "type": "batteryMaxSOC",
            })
        except Exception as err:
            _LOGGER.error("Failed to set max SOC: %s", err)


class MiniEmsMaxExportPowerNumber(CoordinatorEntity[MiniEmsCoordinator], NumberEntity):
    """Maximum Grid Export Power limit."""

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        inv_name = entry.data.get("inverter_name", entry.data.get("username", "inverter"))
        self._attr_unique_id = f"mini_ems_{entry.entry_id}_max_export_power"
        self._attr_name = "Giới hạn công suất phát lưới (Max Export Power)"
        self._attr_native_min_value = 0
        self._attr_native_max_value = 6000
        self._attr_native_step = 100
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_mode = NumberMode.BOX
        self._attr_icon = "mdi:transmission-tower-export"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"Mini EMS - {inv_name}",
            "manufacturer": "Donnergy (Shenzhen DaNeng)",
            "model": entry.data.get("inverter_name", "Hybrid Inverter"),
            "configuration_url": "https://mini-ems.com",
        }
        self._value = 5000.0

    @property
    def native_value(self) -> float:
        data = self.coordinator.data or {}
        inv = data.get("inverter", {})
        return float(inv.get("maxExportPower") or self._value)

    async def async_set_native_value(self, value: float) -> None:
        self._value = value
        inv_id = self._entry.data.get("inverter_id")
        inv_name = self._entry.data.get("inverter_name")
        try:
            await self.coordinator.api.async_send_instruction({
                "inverterName": inv_name,
                "inverterId": inv_id,
                "maxExportPower": int(value),
                "type": "maxExportPower",
            })
        except Exception as err:
            _LOGGER.error("Failed to set max export power: %s", err)


class MiniEmsMaxChargeCurrentNumber(CoordinatorEntity[MiniEmsCoordinator], NumberEntity):
    """Maximum Battery Charge Current limit."""

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        inv_name = entry.data.get("inverter_name", entry.data.get("username", "inverter"))
        self._attr_unique_id = f"mini_ems_{entry.entry_id}_max_charge_current"
        self._attr_name = "Dòng sạc pin tối đa (Max Charge Current)"
        self._attr_native_min_value = 5
        self._attr_native_max_value = 100
        self._attr_native_step = 5
        self._attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
        self._attr_mode = NumberMode.SLIDER
        self._attr_icon = "mdi:battery-arrow-up"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"Mini EMS - {inv_name}",
            "manufacturer": "Donnergy (Shenzhen DaNeng)",
            "model": entry.data.get("inverter_name", "Hybrid Inverter"),
            "configuration_url": "https://mini-ems.com",
        }
        self._value = 50.0

    @property
    def native_value(self) -> float:
        data = self.coordinator.data or {}
        inv = data.get("inverter", {})
        return float(inv.get("maxChargeCurrent") or self._value)

    async def async_set_native_value(self, value: float) -> None:
        self._value = value
        inv_id = self._entry.data.get("inverter_id")
        inv_name = self._entry.data.get("inverter_name")
        try:
            await self.coordinator.api.async_send_instruction({
                "inverterName": inv_name,
                "inverterId": inv_id,
                "maxChargeCurrent": int(value),
                "type": "maxChargeCurrent",
            })
        except Exception as err:
            _LOGGER.error("Failed to set max charge current: %s", err)


class MiniEmsMaxDischargeCurrentNumber(CoordinatorEntity[MiniEmsCoordinator], NumberEntity):
    """Maximum Battery Discharge Current limit."""

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        inv_name = entry.data.get("inverter_name", entry.data.get("username", "inverter"))
        self._attr_unique_id = f"mini_ems_{entry.entry_id}_max_discharge_current"
        self._attr_name = "Dòng xả pin tối đa (Max Discharge Current)"
        self._attr_native_min_value = 5
        self._attr_native_max_value = 100
        self._attr_native_step = 5
        self._attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
        self._attr_mode = NumberMode.SLIDER
        self._attr_icon = "mdi:battery-arrow-down"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"Mini EMS - {inv_name}",
            "manufacturer": "Donnergy (Shenzhen DaNeng)",
            "model": entry.data.get("inverter_name", "Hybrid Inverter"),
            "configuration_url": "https://mini-ems.com",
        }
        self._value = 60.0

    @property
    def native_value(self) -> float:
        data = self.coordinator.data or {}
        inv = data.get("inverter", {})
        return float(inv.get("maxDischargeCurrent") or self._value)

    async def async_set_native_value(self, value: float) -> None:
        self._value = value
        inv_id = self._entry.data.get("inverter_id")
        inv_name = self._entry.data.get("inverter_name")
        try:
            await self.coordinator.api.async_send_instruction({
                "inverterName": inv_name,
                "inverterId": inv_id,
                "maxDischargeCurrent": int(value),
                "type": "maxDischargeCurrent",
            })
        except Exception as err:
            _LOGGER.error("Failed to set max discharge current: %s", err)
