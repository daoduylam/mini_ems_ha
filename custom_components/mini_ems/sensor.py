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
    # Real-time inverter sensors (from /dn/system/data/list)
    # PV Solar Input
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
        key="pv1_current",
        name="PV1 Dòng điện (PV1 Current)",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        source="inverter",
        data_key="pv1Current",
        icon="mdi:solar-panel",
    ),
    MiniEmsSensorDescription(
        key="pv1_power",
        name="PV1 Công suất (PV1 Power)",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        source="inverter",
        data_key="pv1Power",
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
        key="pv2_current",
        name="PV2 Dòng điện (PV2 Current)",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        source="inverter",
        data_key="pv2Current",
        icon="mdi:solar-panel-large",
    ),
    MiniEmsSensorDescription(
        key="pv2_power",
        name="PV2 Công suất (PV2 Power)",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        source="inverter",
        data_key="pv2Power",
        icon="mdi:solar-panel-large",
    ),
    MiniEmsSensorDescription(
        key="pv_total_power",
        name="Tổng PV Công suất (PV Total Power)",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        source="inverter",
        data_key="pvTotalPower",
        icon="mdi:solar-power-variant",
    ),
    # AC Grid Output
    MiniEmsSensorDescription(
        key="ac_voltage",
        name="AC Điện áp lưới (Grid Voltage)",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        source="inverter",
        data_key="acVoltage",
        icon="mdi:transmission-tower",
    ),
    MiniEmsSensorDescription(
        key="ac_current",
        name="AC Dòng điện lưới (Grid Current)",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        source="inverter",
        data_key="acCurrent",
        icon="mdi:transmission-tower",
    ),
    MiniEmsSensorDescription(
        key="ac_power",
        name="AC Công suất (AC Power)",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        source="inverter",
        data_key="acPower",
        icon="mdi:lightning-bolt",
    ),
    MiniEmsSensorDescription(
        key="ac_frequency",
        name="Tần số lưới (AC Frequency)",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        source="inverter",
        data_key="acFrequency",
        icon="mdi:sine-wave",
    ),
    # Battery
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
        name="Pin Dòng điện (Battery Current)",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        source="inverter",
        data_key="batteryCurrent",
        icon="mdi:battery",
    ),
    MiniEmsSensorDescription(
        key="battery_power",
        name="Pin Công suất (Battery Power)",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        source="inverter",
        data_key="batteryPower",
        icon="mdi:battery-charging",
    ),
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
        key="battery_temperature",
        name="Nhiệt độ pin (Battery Temp)",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        source="inverter",
        data_key="batteryTemperature",
        icon="mdi:thermometer",
    ),
    # Load / House consumption
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
    MiniEmsSensorDescription(
        key="load_voltage",
        name="Tải điện áp (Load Voltage)",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        source="inverter",
        data_key="loadVoltage",
        icon="mdi:home-lightning-bolt-outline",
    ),
    MiniEmsSensorDescription(
        key="load_current",
        name="Tải dòng điện (Load Current)",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        source="inverter",
        data_key="loadCurrent",
        icon="mdi:home-lightning-bolt-outline",
    ),
    MiniEmsSensorDescription(
        key="load_frequency",
        name="Tải tần số (Load Frequency)",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        source="inverter",
        data_key="loadFrequency",
        icon="mdi:sine-wave",
    ),
    # Grid import/export
    MiniEmsSensorDescription(
        key="grid_power",
        name="Lưới Công suất (Grid Power)",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        source="inverter",
        data_key="gridPower",
        icon="mdi:transmission-tower",
    ),
    MiniEmsSensorDescription(
        key="grid_energy_in_today",
        name="Điện mua hôm nay (Grid Import Today)",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        source="inverter",
        data_key="gridEnergyInToday",
        icon="mdi:transmission-tower-import",
    ),
    MiniEmsSensorDescription(
        key="grid_energy_out_today",
        name="Điện bán hôm nay (Grid Export Today)",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        source="inverter",
        data_key="gridEnergyOutToday",
        icon="mdi:transmission-tower-export",
    ),
    # Inverter / Temperature
    MiniEmsSensorDescription(
        key="inverter_temperature",
        name="Nhiệt độ biến tần (Inverter Temp)",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        source="inverter",
        data_key="inverterTemperature",
        icon="mdi:thermometer",
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
    MiniEmsSensorDescription(
        key="operation_hours",
        name="Giờ hoạt động (Operation Hours)",
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        source="inverter",
        data_key="operationHours",
        icon="mdi:clock-time-eight",
    ),
    # Daily/Total energy from inverter record
    MiniEmsSensorDescription(
        key="daily_energy",
        name="Sản lượng hôm nay (Daily Energy)",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        source="inverter",
        data_key="dailyPowerGeneration",
        icon="mdi:calendar-today",
    ),
    MiniEmsSensorDescription(
        key="total_energy",
        name="Tổng sản lượng biến tần (Total Energy)",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        source="inverter",
        data_key="totalPowerGeneration",
        icon="mdi:counter",
    ),
    # Charge/Discharge energy today
    MiniEmsSensorDescription(
        key="charger_energy_today",
        name="Điện sạc pin hôm nay (Charge Energy Today)",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        source="inverter",
        data_key="chargerEnergyToday",
        icon="mdi:battery-arrow-up",
    ),
    MiniEmsSensorDescription(
        key="dis_charger_energy_today",
        name="Điện xả pin hôm nay (Discharge Energy Today)",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        source="inverter",
        data_key="disChargerEnergyToday",
        icon="mdi:battery-arrow-down",
    ),
    MiniEmsSensorDescription(
        key="inversion_energy_out_today",
        name="Điện nghịch lưu hôm nay (Inversion Out Today)",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        source="inverter",
        data_key="inversionEnergyOutToday",
        icon="mdi:lightning-bolt",
    ),
    # Status
    MiniEmsSensorDescription(
        key="inverter_name",
        name="Tên biến tần (Inverter Name)",
        source="inverter",
        data_key="inverterName",
        icon="mdi:tag",
    ),
    MiniEmsSensorDescription(
        key="inverter_model",
        name="Model biến tần",
        source="inverter",
        data_key="equipmentModel",
        icon="mdi:information",
    ),
    MiniEmsSensorDescription(
        key="firmware_version",
        name="Firmware Version",
        source="inverter",
        data_key="firmware",
        icon="mdi:chip",
    ),
    MiniEmsSensorDescription(
        key="upgrade_status",
        name="Trạng thái nâng cấp (Upgrade Status)",
        source="inverter",
        data_key="upgradeStatus",
        icon="mdi:update",
    ),
    MiniEmsSensorDescription(
        key="device_type",
        name="Loại thiết bị (Device Type)",
        source="inverter",
        data_key="deviceType",
        icon="mdi:devices",
    ),
    MiniEmsSensorDescription(
        key="power_station_name",
        name="Tên trạm điện (Power Station)",
        source="inverter",
        data_key="powerName",
        icon="mdi:solar-power-variant",
    ),
    MiniEmsSensorDescription(
        key="collector_name",
        name="Tên collector (Collector)",
        source="inverter",
        data_key="collectorName",
        icon="mdi:router-wireless",
    ),
    # Calculated / derived
    MiniEmsSensorDescription(
        key="self_consumption_ratio",
        name="Tỷ lệ tự tiêu thụ (Self Consumption %)",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        source="inverter",
        value_fn=lambda d: _calc_self_consumption(d),
        icon="mdi:home-percent",
    ),
    MiniEmsSensorDescription(
        key="system_status",
        name="Trạng thái hệ thống (System Status)",
        source="inverter",
        value_fn=lambda d: _get_system_status(d),
        icon="mdi:check-circle",
    ),
)


def _calc_self_consumption(data: dict) -> float | None:
    """Calculate self-consumption ratio."""
    pv = data.get("pvTotalPower") or data.get("pv1Power", 0)
    load = data.get("loadPower") or data.get("acPower", 0)
    if not pv or pv <= 0:
        return None
    ratio = min(load / pv * 100, 100)
    return round(ratio, 1)


def _get_system_status(data: dict) -> str:
    """Get human-readable system status."""
    batt = data.get("batteryPower", 0) or 0
    grid = data.get("gridPower", 0) or 0
    pv = data.get("pvTotalPower") or data.get("pv1Power", 0) or 0

    if pv > 10 and batt > 5:
        return "Mặt trời + Sạc pin"
    elif pv > 10 and grid < 0:
        return "Hòa lưới (bán điện)"
    elif pv > 10:
        return "Mặt trời"
    elif batt < -5:
        return "Xả pin"
    elif grid > 10:
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
    coordinator: MiniEmsCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for description in ALL_SENSORS:
        entities.append(MiniEmsSensor(coordinator, description, entry))

    async_add_entities(entities, update_before_add=True)


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
            # Add inverter metadata
            for field in [
                "inverterId", "powerId", "inverterName", "collectorName",
                "equipmentModel", "firmware", "upgradeStatus", "deviceType",
                "powerName",
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
