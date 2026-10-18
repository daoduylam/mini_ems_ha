"""Switch platform for Mini EMS."""
from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
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
    """Set up Mini EMS switch entities."""
    stored = hass.data[DOMAIN][entry.entry_id]
    if "hub" in stored:
        return

    coordinator: MiniEmsCoordinator = stored.get("coordinator") or stored
    async_add_entities([
        MiniEmsGridExportSwitch(coordinator, entry),
        MiniEmsForceChargeSwitch(coordinator, entry),
    ])


class MiniEmsGridExportSwitch(CoordinatorEntity[MiniEmsCoordinator], SwitchEntity):
    """Toggle grid export (selling power to grid)."""

    def __init__(self, coordinator: MiniEmsCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        inv_name = entry.data.get("inverter_name", entry.data.get("username", "inverter"))
        self._attr_unique_id = f"mini_ems_{entry.entry_id}_grid_export"
        self._attr_name = "Cho phép bán điện lưới (Grid Export)"
        self._attr_icon = "mdi:transmission-tower-export"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"Mini EMS - {inv_name}",
            "manufacturer": "Donnergy (Shenzhen DaNeng)",
            "model": entry.data.get("inverter_name", "Hybrid Inverter"),
            "configuration_url": "https://mini-ems.com",
        }

    @property
    def is_on(self) -> bool:
        return self.coordinator.control_states.get("grid_export", True)

    async def async_turn_on(self, **kwargs) -> None:
        self.coordinator.control_states["grid_export"] = True
        self.async_write_ha_state()
        await self._send_command(1)

    async def async_turn_off(self, **kwargs) -> None:
        self.coordinator.control_states["grid_export"] = False
        self.async_write_ha_state()
        await self._send_command(0)

    async def _send_command(self, value: int) -> None:
        inv_name = self._entry.data.get("inverter_name")
        inv_id = self._entry.data.get("inverter_id")
        try:
            await self.coordinator.api.async_send_instruction({
                "inverterName": inv_name,
                "inverterId": inv_id,
                "gridExport": value,
                "type": "gridExport",
            })
        except Exception as err:
            _LOGGER.error("Failed to toggle grid export: %s", err)


class MiniEmsForceChargeSwitch(CoordinatorEntity[MiniEmsCoordinator], SwitchEntity):
    """Force charge battery from grid."""

    def __init__(self, coordinator: MiniEmsCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        inv_name = entry.data.get("inverter_name", entry.data.get("username", "inverter"))
        self._attr_unique_id = f"mini_ems_{entry.entry_id}_force_charge"
        self._attr_name = "Buộc sạc pin từ lưới (Force Charge)"
        self._attr_icon = "mdi:battery-charging-high"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"Mini EMS - {inv_name}",
            "manufacturer": "Donnergy (Shenzhen DaNeng)",
            "model": entry.data.get("inverter_name", "Hybrid Inverter"),
            "configuration_url": "https://mini-ems.com",
        }

    @property
    def is_on(self) -> bool:
        return self.coordinator.control_states.get("force_charge", False)

    async def async_turn_on(self, **kwargs) -> None:
        self.coordinator.control_states["force_charge"] = True
        self.async_write_ha_state()
        await self._send_command(1)

    async def async_turn_off(self, **kwargs) -> None:
        self.coordinator.control_states["force_charge"] = False
        self.async_write_ha_state()
        await self._send_command(0)

    async def _send_command(self, value: int) -> None:
        inv_name = self._entry.data.get("inverter_name")
        inv_id = self._entry.data.get("inverter_id")
        try:
            await self.coordinator.api.async_send_instruction({
                "inverterName": inv_name,
                "inverterId": inv_id,
                "forceCharge": value,
                "type": "forceCharge",
            })
        except Exception as err:
            _LOGGER.error("Failed to toggle force charge: %s", err)
