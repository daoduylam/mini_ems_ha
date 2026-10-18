"""Sensor platform for Mini EMS - Donnergy Inverter."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MiniEmsCoordinator


@dataclass(frozen=True, kw_only=True)
class MiniEmsSensorDescription(SensorEntityDescription):
    """Extended sensor entity description."""

    # Source: "overview" | "inverter" | "electricity"
    source: str = "inverter"
    # Key in the source dict
    value_fn: Callable[[dict], Any] | None = None
    # Optional sub-key
    data_key: str | None = None
    # Round digits
    round_digits: int | None = None


# ─────────────────────────────────────────────────────────────────────────────
# SENSOR DEFINITIONS
# Based on actual API data from mini-ems.com:8081
# ─────────────────────────────────────────────────────────────────────────────

OVERVIEW_SENSORS: tuple[MiniEmsSensorDescription, ...] = (
    # Overview sensors (from /dn/power/inverter/overviewApp)
    MiniEmsSensorDescription(
        key="current_power",
        name="Công suất hiện tại (Current Power)",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        source="overview",
        data_key="currentPower",
        icon="mdi:solar-power",
    ),
    MiniEmsSensorDescription(
        key="daily_power_generation",
        name="Sản lượng hôm nay (Daily Generation)",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        source="overview",
        data_key="dailyPowerGeneration",
        icon="mdi:solar-panel",
    ),
    MiniEmsSensorDescription(
        key="total_power_generation",
        name="Tổng sản lượng (Total Generation)",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        source="overview",
        data_key="totalPowerGeneration",
        icon="mdi:counter",
    ),
    MiniEmsSensorDescription(
        key="all_rated_power",
        name="Công suất định mức (Rated Power)",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        source="overview",
        data_key="allRatedPower",
        icon="mdi:flash",
    ),
    MiniEmsSensorDescription(
        key="income_of_the_day",
        name="Thu nhập hôm nay (Daily Income)",
        native_unit_of_measurement="VND",
        state_class=SensorStateClass.TOTAL_INCREASING,
        source="overview",
        data_key="incomeOfTheDay",
        icon="mdi:currency-usd",
    ),
    MiniEmsSensorDescription(
        key="cumulative_income",
        name="Tổng thu nhập (Cumulative Income)",
        native_unit_of_measurement="VND",
        state_class=SensorStateClass.TOTAL_INCREASING,
        source="overview",
        data_key="cumulativeIncome",
        icon="mdi:bank",
    ),
    MiniEmsSensorDescription(
        key="save_standard_coal",
        name="Than tiêu chuẩn tiết kiệm (Save Coal)",
        native_unit_of_measurement="kg",
        state_class=SensorStateClass.TOTAL_INCREASING,
        source="overview",
        data_key="saveStandardCoal",
        icon="mdi:fire",
    ),
    MiniEmsSensorDescription(
        key="emission_reduction_co2",
        name="Giảm phát thải CO2",
        native_unit_of_measurement="kg",
        state_class=SensorStateClass.TOTAL_INCREASING,
        source="overview",
        data_key="emissionReductionCO2",
        icon="mdi:molecule-co2",
    ),
    MiniEmsSensorDescription(
        key="protect_trees",
        name="Cây xanh bảo vệ",
        native_unit_of_measurement="cây",
        state_class=SensorStateClass.TOTAL_INCREASING,
        source="overview",
        data_key="protectTrees",
        icon="mdi:tree",
    ),
    MiniEmsSensorDescription(
        key="inverter_count",
        name="Số lượng biến tần",
        state_class=SensorStateClass.MEASUREMENT,
        source="overview",
        data_key="number",
        icon="mdi:counter",
    ),
    MiniEmsSensorDescription(
        key="inverter_online_count",
        name="Biến tần đang online",
        state_class=SensorStateClass.MEASUREMENT,
        source="overview",
        data_key="onlineNumber",
        icon="mdi:check-network",
    ),
)

INVERTER_SENSORS: tuple[MiniEmsSensorDescription, ...] = (
    # ── PV Solar Input ──────────────────────────────────────────────────────
    MiniEmsSensorDescription(
        key="pv1_voltage",
        name="PV1 Điện áp (PV1 Voltage)",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        source="inverter",
        data_key="pv1Voltage",
        icon="mdi:solar-panel",
    ),
    MiniEmsSensorDescription(
        key="pv2_voltage",
        name="PV2 Điện áp (PV2 Voltage)",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        source="inverter",
        data_key="pv2Voltage",
        icon="mdi:solar-panel-large",
    ),
    MiniEmsSensorDescription(
        key="pv1_power",
        name="PV1 Công suất (PV1 Power)",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        source="inverter",
        data_key="pv1Power",
        icon="mdi:solar-power",
    ),
    MiniEmsSensorDescription(
        key="pv2_power",
        name="PV2 Công suất (PV2 Power)",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        source="inverter",
        data_key="pv2Power",
        icon="mdi:solar-power",
    ),
    MiniEmsSensorDescription(
        key="pv_total_power",
        name="Tổng công suất PV (PV Total Power)",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        source="inverter",
        data_key="pvTotalPower",
        icon="mdi:solar-power-variant",
    ),
    # ── AC Output ────────────────────────────────────────────────────────────
    MiniEmsSensorDescription(
        key="ac_power",
        name="AC Công suất đầu ra (AC Output Power)",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        source="inverter",
        data_key="acPower",
        icon="mdi:lightning-bolt",
    ),
    MiniEmsSensorDescription(
        key="ac_current",
        name="AC Dòng điện đầu ra (AC Current)",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        source="inverter",
        data_key="acCurrent",
        icon="mdi:current-ac",
    ),
    MiniEmsSensorDescription(
        key="inverter_power",
        name="Biến tần công suất (Inverter Power)",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        source="inverter",
        data_key="inverterPower",
        icon="mdi:lightning-bolt-circle",
    ),
    # ── Grid ────────────────────────────────────────────────────────────────
    MiniEmsSensorDescription(
        key="grid_voltage",
        name="Điện áp lưới (Grid Voltage)",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        source="inverter",
        data_key="gridVoltage",
        icon="mdi:transmission-tower",
    ),
    MiniEmsSensorDescription(
        key="grid_frequency",
        name="Tần số lưới (Grid Frequency)",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        source="inverter",
        data_key="gridFrequency",
        icon="mdi:sine-wave",
    ),
    MiniEmsSensorDescription(
        key="grid_power",
        name="Lưới công suất (Grid Power +mua/-bán)",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        source="inverter",
        data_key="gridPower",
        icon="mdi:transmission-tower",
    ),
    MiniEmsSensorDescription(
        key="grid_current",
        name="Dòng điện lưới (Grid Current)",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        source="inverter",
        data_key="gridCurrent",
        icon="mdi:current-ac",
    ),
    # ── Battery ─────────────────────────────────────────────────────────────
    MiniEmsSensorDescription(
        key="battery_soc",
        name="Pin SOC (Battery SOC)",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        source="inverter",
        data_key="batterySOC",
        icon="mdi:battery-medium",
    ),
    MiniEmsSensorDescription(
        key="battery_voltage",
        name="Pin Điện áp (Battery Voltage)",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        source="inverter",
        data_key="batteryVoltage",
        icon="mdi:battery",
    ),
    MiniEmsSensorDescription(
        key="battery_current",
        name="Pin Dòng điện (Battery Current +sạc/-xả)",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        source="inverter",
        data_key="batteryCurrent",
        icon="mdi:battery-charging",
    ),
    MiniEmsSensorDescription(
        key="battery_power",
        name="Pin Công suất (Battery Power +sạc/-xả)",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        source="inverter",
        data_key="batteryPower",
        icon="mdi:battery-charging-outline",
    ),
    MiniEmsSensorDescription(
        key="battery_temperature",
        name="Nhiệt độ pin (Battery Temp)",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        source="inverter",
        data_key="batteryTemperature",
        icon="mdi:thermometer",
    ),
    # ── Load ────────────────────────────────────────────────────────────────
    MiniEmsSensorDescription(
        key="load_power",
        name="Tải tiêu thụ (Load Power)",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        source="inverter",
        data_key="loadPower",
        icon="mdi:home-lightning-bolt",
    ),
    # ── Inverter Temperature ─────────────────────────────────────────────────
    MiniEmsSensorDescription(
        key="inverter_temperature",
        name="Nhiệt độ biến tần (Inverter Temp)",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        source="inverter",
        data_key="temperature",
        icon="mdi:thermometer",
    ),
    # ── Energy totals from raw frame ─────────────────────────────────────────
    MiniEmsSensorDescription(
        key="total_energy_raw",
        name="Tổng sản lượng biến tần (Total kWh)",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        source="inverter",
        data_key="totalPowerGeneration",
        icon="mdi:counter",
    ),
    MiniEmsSensorDescription(
        key="daily_energy_raw",
        name="Sản lượng hôm nay biến tần (Daily kWh)",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        source="inverter",
        data_key="dailyPowerGeneration",
        icon="mdi:calendar-today",
    ),
    # ── Calculated ───────────────────────────────────────────────────────────
    MiniEmsSensorDescription(
        key="system_status",
        name="Trạng thái hệ thống (System Status)",
        source="inverter",
        value_fn=lambda d: _get_system_status(d),
        icon="mdi:check-circle",
    ),
    MiniEmsSensorDescription(
        key="self_consumption_ratio",
        name="Tỷ lệ tự tiêu thụ (Self Consumption %)",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        source="inverter",
        value_fn=lambda d: _calc_self_consumption(d),
        icon="mdi:home-percent",
    ),
)


def _calc_self_consumption(data: dict) -> float | None:
    """Calculate self-consumption ratio: load / ac_output."""
    ac = data.get("acPower") or data.get("inverterPower") or 0
    load = data.get("loadPower") or 0
    if not ac or ac <= 0:
        return None
    ratio = min(load / ac * 100, 100)
    return round(ratio, 1)


def _get_system_status(data: dict) -> str:
    """Get human-readable system status from Modbus decoded fields."""
    batt_power = data.get("batteryPower") or 0
    grid_power = data.get("gridPower") or 0  # positive = import, negative = export
    ac_power = data.get("acPower") or 0

    if ac_power > 10 and batt_power > 5:
        return "Mặt trời + Sạc pin"
    elif ac_power > 10 and grid_power < -10:
        return "Hòa lưới (bán điện)"
    elif ac_power > 10:
        return "Phát điện mặt trời"
    elif batt_power < -5:
        return "Xả pin"
    elif grid_power > 10:
        return "Mua điện lưới"
    else:
        return "Chờ"


ALL_SENSORS = OVERVIEW_SENSORS + INVERTER_SENSORS


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Mini EMS sensor entities."""
    stored = hass.data[DOMAIN][entry.entry_id]

    if "hub" in stored:
        # Local Mode entities
        hub = stored["hub"]
        local_sensors = [
            ("pv1_voltage", "PV1 Điện áp (PV1 Voltage)", "V", SensorDeviceClass.VOLTAGE),
            ("pv2_voltage", "PV2 Điện áp (PV2 Voltage)", "V", SensorDeviceClass.VOLTAGE),
            ("pv1_current", "PV1 Dòng điện (PV1 Current)", "A", SensorDeviceClass.CURRENT),
            ("pv2_current", "PV2 Dòng điện (PV2 Current)", "A", SensorDeviceClass.CURRENT),
            ("pv1_power", "PV1 Công suất (PV1 Power)", "W", SensorDeviceClass.POWER),
            ("pv2_power", "PV2 Công suất (PV2 Power)", "W", SensorDeviceClass.POWER),
            ("pv_total_power", "Tổng PV Công suất (PV Total Power)", "W", SensorDeviceClass.POWER),
            ("ac_voltage", "Điện áp lưới (AC Voltage)", "V", SensorDeviceClass.VOLTAGE),
            ("ac_frequency", "Tần số lưới (AC Frequency)", "Hz", SensorDeviceClass.FREQUENCY),
            ("ac_power", "Công suất phát AC (AC Power)", "W", SensorDeviceClass.POWER),
            ("total_energy", "Tổng sản lượng biến tần (Total Energy)", "kWh", SensorDeviceClass.ENERGY),
        ]
        entities = [
            MiniEmsLocalSensor(hub, key, name, unit, dev_class, entry)
            for key, name, unit, dev_class in local_sensors
        ]
        async_add_entities(entities, update_before_add=True)
        return

    # Cloud Mode entities
    coordinator: MiniEmsCoordinator = stored.get("coordinator") or stored
    entities = []
    for description in ALL_SENSORS:
        entities.append(MiniEmsSensor(coordinator, description, entry))

    async_add_entities(entities, update_before_add=True)


class MiniEmsLocalSensor(SensorEntity):
    """Local TCP Socket Sensor directly connected to inverter datalogger."""

    _attr_should_poll = False

    def __init__(
        self,
        hub,
        key: str,
        name: str,
        unit: str,
        device_class: SensorDeviceClass,
        entry: ConfigEntry,
    ) -> None:
        self._hub = hub
        self._key = key
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        if device_class in (SensorDeviceClass.POWER, SensorDeviceClass.VOLTAGE, SensorDeviceClass.CURRENT, SensorDeviceClass.FREQUENCY):
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif device_class == SensorDeviceClass.ENERGY:
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING

        serial = entry.data.get("serial", entry.data.get("inverter_name", "local"))
        self._attr_unique_id = f"mini_ems_local_{entry.entry_id}_{key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"local_{entry.entry_id}")},
            "name": f"Absaar Local - {serial}",
            "manufacturer": "Absaar / Donnergy",
            "model": "Inverter Local TCP (Port 15444)",
        }

    async def async_added_to_hass(self) -> None:
        """Register update dispatcher."""
        from homeassistant.helpers.dispatcher import async_dispatcher_connect
        self.async_on_remove(
            async_dispatcher_connect(self.hass, self._hub.signal, self._handle_update)
        )

    def _handle_update(self) -> None:
        self.async_write_ha_state()

    @property
    def native_value(self) -> Any:
        return self._hub.data.get(self._key)

    @property
    def available(self) -> bool:
        return self._hub.online


class MiniEmsSensor(CoordinatorEntity[MiniEmsCoordinator], SensorEntity):
    """Representation of a Mini EMS sensor."""

    entity_description: MiniEmsSensorDescription

    def __init__(
        self,
        coordinator: MiniEmsCoordinator,
        description: MiniEmsSensorDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry

        inverter_name = entry.data.get("inverter_name", entry.data.get("username", "inverter"))
        self._attr_unique_id = f"mini_ems_{entry.entry_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"Mini EMS - {inverter_name}",
            "manufacturer": "Donnergy (Shenzhen DaNeng)",
            "model": entry.data.get("inverter_name", "Hybrid Inverter"),
            "configuration_url": "https://mini-ems.com",
            "sw_version": self._get_fw_version(),
        }

    def _get_fw_version(self) -> str | None:
        """Get firmware version from data."""
        if self.coordinator.data:
            inv = self.coordinator.data.get("inverter", {})
            return inv.get("firmware")
        return None

    def _get_source_data(self) -> dict:
        """Get data dict based on source."""
        data = self.coordinator.data or {}
        source = self.entity_description.source
        if source == "overview":
            return data.get("overview", {})
        elif source == "inverter":
            return data.get("inverter", {})
        elif source == "electricity":
            rows = data.get("electricity", [])
            return rows[0] if rows else {}
        return {}

    @property
    def native_value(self) -> Any:
        """Return sensor value."""
        source_data = self._get_source_data()
        if not source_data:
            return None

        desc = self.entity_description

        # Custom value function
        if desc.value_fn is not None:
            try:
                return desc.value_fn(source_data)
            except Exception:
                return None

        # Direct key lookup
        if desc.data_key:
            val = source_data.get(desc.data_key)
            if val is None:
                return None
            # Round if needed
            if desc.round_digits is not None and isinstance(val, (int, float)):
                return round(val, desc.round_digits)
            return val

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        data = self.coordinator.data or {}
        inv = data.get("inverter", {})
        attrs: dict[str, Any] = {}

        if self.entity_description.source == "inverter":
            # Add inverter metadata and packet debug logs
            for field in [
                "inverterId", "powerId", "inverterName", "collectorName",
                "equipmentModel", "firmware", "upgradeStatus", "deviceType",
                "powerName", "_reg_count", "_raw_frame_id", "_raw_time", "_raw_data",
            ]:
                if field in inv:
                    attrs[field] = inv[field]

        elif self.entity_description.source == "overview":
            overview = data.get("overview", {})
            attrs.update({
                k: v for k, v in overview.items()
                if k not in ("currentPower", "dailyPowerGeneration", "totalPowerGeneration")
            })

        return attrs

    @property
    def available(self) -> bool:
        """Return availability."""
        if not self.coordinator.last_update_success:
            return False
        source_data = self._get_source_data()
        return bool(source_data)
