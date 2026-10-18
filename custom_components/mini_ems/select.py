"""Select platform for Mini EMS - Remote control dropdowns."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity, SelectEntityDescription
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
    """Set up Mini EMS select entities."""
    stored = hass.data[DOMAIN][entry.entry_id]
    if "hub" in stored:
        return

    coordinator: MiniEmsCoordinator = stored.get("coordinator") or stored
    async_add_entities([
        MiniEmsWorkModeSelect(coordinator, entry),
        MiniEmsBatteryChargingModeSelect(coordinator, entry),
    ])


class MiniEmsWorkModeSelect(CoordinatorEntity[MiniEmsCoordinator], SelectEntity):
    """Work mode selector."""

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        inv_name = entry.data.get("inverter_name", entry.data.get("username", "inverter"))
        self._attr_unique_id = f"mini_ems_{entry.entry_id}_work_mode"
        self._attr_name = "Chế độ hoạt động (Work Mode)"
        self._attr_icon = "mdi:tune"
        self._attr_options = [
            "Mặt trời ưu tiên (Solar First)",
            "Pin ưu tiên (Battery First)",
            "Lưới ưu tiên (Grid First)",
            "Tự dùng (Self-Consumption)",
        ]
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"Mini EMS - {inv_name}",
            "manufacturer": "Donnergy (Shenzhen DaNeng)",
            "model": entry.data.get("inverter_name", "Hybrid Inverter"),
            "configuration_url": "https://mini-ems.com",
        }

    @property
    def current_option(self) -> str | None:
        return self.coordinator.control_states.get("work_mode", "Tự dùng (Self-Consumption)")

    async def async_select_option(self, option: str) -> None:
        """Send work mode command."""
        self.coordinator.control_states["work_mode"] = option
        self.async_write_ha_state()

        mode_map = {
            "Mặt trời ưu tiên (Solar First)": 0,
            "Pin ưu tiên (Battery First)": 1,
            "Lưới ưu tiên (Grid First)": 2,
            "Tự dùng (Self-Consumption)": 3,
        }
        mode_val = mode_map.get(option, 0)
        inv_name = self._entry.data.get("inverter_name")
        inv_id = self._entry.data.get("inverter_id")
        try:
            await self.coordinator.api.async_send_instruction({
                "inverterName": inv_name,
                "inverterId": inv_id,
                "workMode": mode_val,
                "type": "workMode",
            })
        except Exception as err:
            _LOGGER.error("Failed to set work mode: %s", err)


class MiniEmsBatteryChargingModeSelect(CoordinatorEntity[MiniEmsCoordinator], SelectEntity):
    """Battery charging mode selector."""

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        inv_name = entry.data.get("inverter_name", entry.data.get("username", "inverter"))
        self._attr_unique_id = f"mini_ems_{entry.entry_id}_charge_mode"
        self._attr_name = "Chế độ sạc pin (Charge Mode)"
        self._attr_icon = "mdi:battery-charging-outline"
        self._attr_options = [
            "Tự động (Auto)",
            "Chỉ mặt trời (Solar Only)",
            "Mặt trời + Lưới (Solar + Grid)",
        ]
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"Mini EMS - {inv_name}",
            "manufacturer": "Donnergy (Shenzhen DaNeng)",
            "model": entry.data.get("inverter_name", "Hybrid Inverter"),
            "configuration_url": "https://mini-ems.com",
        }

    @property
    def current_option(self) -> str | None:
        return self.coordinator.control_states.get("charge_mode", "Tự động (Auto)")

    async def async_select_option(self, option: str) -> None:
        """Send charge mode command."""
        self.coordinator.control_states["charge_mode"] = option
        self.async_write_ha_state()

        mode_map = {
            "Tự động (Auto)": 0,
            "Chỉ mặt trời (Solar Only)": 1,
            "Mặt trời + Lưới (Solar + Grid)": 2,
        }
        inv_name = self._entry.data.get("inverter_name")
        inv_id = self._entry.data.get("inverter_id")
        try:
            await self.coordinator.api.async_send_instruction({
                "inverterName": inv_name,
                "inverterId": inv_id,
                "chargeMode": mode_map.get(option, 0),
                "type": "chargeMode",
            })
        except Exception as err:
            _LOGGER.error("Failed to set charge mode: %s", err)
