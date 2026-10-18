"""Binary sensor platform for Mini EMS - Status indicators."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MiniEmsCoordinator


@dataclass(frozen=True, kw_only=True)
class MiniEmsBinarySensorDescription(BinarySensorEntityDescription):
    """Extended binary sensor description."""
    source: str = "inverter"
    value_fn: Callable[[dict], bool | None] = lambda d: None


BINARY_SENSORS = (
    MiniEmsBinarySensorDescription(
        key="inverter_online",
        name="Biến tần online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        source="overview",
        value_fn=lambda d: (d.get("onlineNumber", 0) or 0) > 0,
        icon="mdi:check-network",
    ),
    MiniEmsBinarySensorDescription(
        key="battery_charging",
        name="Đang sạc pin",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        source="inverter",
        value_fn=lambda d: (d.get("batteryPower", 0) or 0) > 5,
        icon="mdi:battery-charging",
    ),
    MiniEmsBinarySensorDescription(
        key="battery_discharging",
        name="Đang xả pin",
        source="inverter",
        value_fn=lambda d: (d.get("batteryPower", 0) or 0) < -5,
        icon="mdi:battery-arrow-down-outline",
    ),
    MiniEmsBinarySensorDescription(
        key="solar_producing",
        name="Mặt trời đang phát điện",
        source="inverter",
        value_fn=lambda d: (d.get("pvTotalPower") or d.get("pv1Power", 0) or 0) > 10,
        icon="mdi:weather-sunny",
    ),
    MiniEmsBinarySensorDescription(
        key="grid_importing",
        name="Đang mua điện lưới",
        source="inverter",
        value_fn=lambda d: (d.get("gridPower", 0) or 0) > 10,
        icon="mdi:transmission-tower-import",
    ),
    MiniEmsBinarySensorDescription(
        key="grid_exporting",
        name="Đang bán điện lưới (Hòa lưới)",
        source="inverter",
        value_fn=lambda d: (d.get("gridPower", 0) or 0) < -10,
        icon="mdi:transmission-tower-export",
    ),
    MiniEmsBinarySensorDescription(
        key="upgrade_available",
        name="Có bản cập nhật firmware",
        device_class=BinarySensorDeviceClass.UPDATE,
        source="inverter",
        value_fn=lambda d: d.get("upgradeStatus") == 0,
        icon="mdi:update",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Mini EMS binary sensor entities."""
    stored = hass.data[DOMAIN][entry.entry_id]

    if "hub" in stored:
        hub = stored["hub"]
        async_add_entities([MiniEmsLocalBinarySensor(hub, entry)], update_before_add=True)
        return

    coordinator: MiniEmsCoordinator = stored.get("coordinator") or stored
    entities = [
        MiniEmsBinarySensor(coordinator, desc, entry)
        for desc in BINARY_SENSORS
    ]
    async_add_entities(entities, update_before_add=True)


class MiniEmsLocalBinarySensor(BinarySensorEntity):
    """Local connection status binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_should_poll = False

    def __init__(self, hub, entry: ConfigEntry) -> None:
        self._hub = hub
        self._attr_name = "Trạng thái kết nối Local (Inverter Online)"
        serial = entry.data.get("serial", entry.data.get("inverter_name", "local"))
        self._attr_unique_id = f"mini_ems_local_{entry.entry_id}_connectivity"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"local_{entry.entry_id}")},
            "name": f"Absaar Local - {serial}",
            "manufacturer": "Absaar / Donnergy",
            "model": "Inverter Local TCP (Port 15444)",
        }

    async def async_added_to_hass(self) -> None:
        from homeassistant.helpers.dispatcher import async_dispatcher_connect
        self.async_on_remove(
            async_dispatcher_connect(self.hass, self._hub.signal, self._handle_update)
        )

    def _handle_update(self) -> None:
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        return self._hub.online


class MiniEmsBinarySensor(CoordinatorEntity[MiniEmsCoordinator], BinarySensorEntity):
    """Binary sensor for Mini EMS."""

    entity_description: MiniEmsBinarySensorDescription

    def __init__(self, coordinator, description, entry) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"mini_ems_{entry.entry_id}_{description.key}"
        inv_name = entry.data.get("inverter_name", entry.data.get("username", "inverter"))
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"Mini EMS - {inv_name}",
            "manufacturer": "Donnergy (Shenzhen DaNeng)",
            "model": entry.data.get("inverter_name", "Hybrid Inverter"),
            "configuration_url": "https://mini-ems.com",
        }

    def _get_source_data(self) -> dict:
        data = self.coordinator.data or {}
        src = self.entity_description.source
        if src == "overview":
            return data.get("overview", {})
        elif src == "inverter":
            return data.get("inverter", {})
        return {}

    @property
    def is_on(self) -> bool | None:
        """Return state."""
        source = self._get_source_data()
        if not source:
            return None
        try:
            return self.entity_description.value_fn(source)
        except Exception:
            return None
