"""API client for Mini EMS (Donnergy Cloud)."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp

from .const import API_BASE_URL, API_LOGIN_URL

_LOGGER = logging.getLogger(__name__)

HEADERS_BASE = {
    "Content-Type": "application/json",
    "Accept": "application/json, */*",
    "Origin": "https://mini-ems.com",
    "Referer": "https://mini-ems.com/",
    "User-Agent": "Mozilla/5.0 (HomeAssistant/MiniEMS)",
}


class MiniEmsApiError(Exception):
    """API error."""


class MiniEmsAuthError(MiniEmsApiError):
    """Authentication error."""


class MiniEmsApi:
    """Mini EMS API Client."""

    def __init__(self, username: str, password: str, session: aiohttp.ClientSession) -> None:
        """Initialize API client."""
        self._username = username
        self._password = password
        self._session = session
        self._token: str | None = None
        self._user_id: str | None = None
        self._headers = dict(HEADERS_BASE)

    @property
    def token(self) -> str | None:
        """Return current token."""
        return self._token

    @property
    def user_id(self) -> str | None:
        """Return user ID."""
        return self._user_id

    async def async_login(self) -> dict[str, Any]:
        """Login and get JWT token. Returns controlList with permissions."""
        payload = {
            "username": self._username,
            "password": self._password,
        }
        try:
            async with self._session.post(
                API_LOGIN_URL,
                json=payload,
                headers=HEADERS_BASE,
                ssl=False,
            ) as resp:
                data = await resp.json(content_type=None)
        except aiohttp.ClientError as err:
            raise MiniEmsApiError(f"Login request failed: {err}") from err

        if data.get("code") != 200:
            raise MiniEmsAuthError(f"Login failed: {data.get('msg', 'unknown')}")

        self._token = data["token"]
        self._user_id = str(data.get("userId", ""))
        self._headers["Authorization"] = f"Bearer {self._token}"

        _LOGGER.info(
            "Mini EMS login successful. userId=%s, year=%s",
            self._user_id,
            data.get("year"),
        )
        return data

    async def _post(self, path: str, body: dict | None = None, params: dict | None = None) -> dict:
        """Make authenticated POST request."""
        if not self._token:
            await self.async_login()

        url = f"{API_BASE_URL}{path}"
        if params:
            query = "&".join(f"{k}={v}" for k, v in params.items())
            url = f"{url}?{query}"

        try:
            async with self._session.post(
                url,
                json=body or {},
                headers=self._headers,
                ssl=False,
            ) as resp:
                if resp.status == 401:
                    # Token expired, re-login
                    await self.async_login()
                    async with self._session.post(
                        url, json=body or {}, headers=self._headers, ssl=False
                    ) as resp2:
                        return await resp2.json(content_type=None)
                return await resp.json(content_type=None)
        except aiohttp.ClientError as err:
            raise MiniEmsApiError(f"Request to {path} failed: {err}") from err

    # ─────────────────────────────────────────────────────────────────────────
    # Power Station Overview
    # ─────────────────────────────────────────────────────────────────────────

    async def async_get_overview(self) -> dict:
        """Get inverter overview stats (currentPower, daily/total generation, etc.)."""
        data = await self._post("/dn/power/inverter/overviewApp")
        rows = data.get("rows", [])
        return rows[0] if rows else {}

    # ─────────────────────────────────────────────────────────────────────────
    # Device List (system/data/list = full inverter data with all sensors)
    # ─────────────────────────────────────────────────────────────────────────

    async def async_get_inverter_list(self, page: int = 1, page_size: int = 50) -> list[dict]:
        """Get list of inverters. Tries filtered search first."""
        data = await self._post(
            "/dn/system/data/list",
            body={},
            params={"pageNum": page, "pageSize": page_size},
        )
        return data.get("rows", [])

    async def async_get_all_inverters(self) -> list[dict]:
        """Get ALL inverters across multiple pages (for reseller accounts)."""
        all_rows = []
        for page in range(1, 10):
            data = await self._post(
                "/dn/system/data/list",
                body={},
                params={"pageNum": page, "pageSize": 50},
            )
            rows = data.get("rows", [])
            all_rows.extend(rows)
            total = data.get("total", 0)
            if len(all_rows) >= total or not rows:
                break
        return all_rows

    async def async_get_inverter_data(self, inverter_name: str) -> dict | None:
        """Get real-time data for a specific inverter by serial number."""
        target = (inverter_name or "").strip().lower()
        # Try with name filter in body
        data = await self._post(
            "/dn/system/data/list",
            body={"inverterName": inverter_name},
            params={"pageNum": 1, "pageSize": 20},
        )
        rows = data.get("rows", [])
        for dev in rows:
            name = str(dev.get("inverterName") or dev.get("sn") or "").strip().lower()
            if name == target:
                return dev
        # Fallback: scan all pages
        all_devs = await self.async_get_all_inverters()
        for dev in all_devs:
            name = str(dev.get("inverterName") or dev.get("sn") or "").strip().lower()
            if name == target:
                return dev
        return None

    # ─────────────────────────────────────────────────────────────────────────
    # Station Electricity (daily/monthly kWh breakdown)
    # ─────────────────────────────────────────────────────────────────────────

    async def async_get_station_electricity(self) -> list[dict]:
        """Get station electricity data (daily kWh by hour)."""
        data = await self._post("/dn/power/inverterData/stationElectricity")
        return data.get("rows", [])

    # ─────────────────────────────────────────────────────────────────────────
    # Raw Modbus data — source of per-inverter realtime sensor data
    # ─────────────────────────────────────────────────────────────────────────

    async def async_get_latest_raw_frame(self, inverter_name: str) -> dict:
        """
        Get latest RESPONSE_INV_INPUT Modbus frame for inverter.
        Returns decoded register dict with field names.
        """
        # Get list of latest raw records for this inverter
        data = await self._post(
            "/dn/power/raw/data/list",
            body={"inverterName": inverter_name},
            params={"pageNum": 1, "pageSize": 20},
        )
        rows = data.get("rows", [])

        # Find latest INPUT frames (dataType=04 = function code 04 = Read Input Registers)
        # Sắp xếp các gói tin theo thời gian tạo mới nhất lên đầu
        input_rows = [r for r in rows if r.get("dataType") == "04"]
        if not input_rows:
            return {}

        input_rows.sort(
            key=lambda x: str(x.get("createTime") or x.get("time") or x.get("rawDataId") or ""),
            reverse=True,
        )

        target_row = None
        # Ưu tiên gói tin bắt đầu từ thanh ghi 0 (kết thúc bằng 00 00 00 3C)
        for r in input_rows:
            raw_hex = (r.get("rawData") or "").strip()
            if raw_hex.endswith("00 00 00 3C") or "04 00 00 00 3C" in raw_hex:
                target_row = r
                break
        if not target_row:
            target_row = input_rows[0]

        raw_id = target_row.get("rawDataId")
        if not raw_id:
            return {}

        detail = await self._post(
            "/dn/power/raw/data/selectDnRawDataByRawDataId",
            body={"rawDataId": raw_id},
        )
        detail_rows = detail.get("rows", [])
        if not detail_rows:
            return {}

        raw_data_part = detail_rows[0].get("rawDataPart", "")
        if not raw_data_part:
            return {}

        return self._decode_modbus_frame(raw_data_part)

    @staticmethod
    def _decode_modbus_frame(raw_data_part: str) -> dict:
        """
        Decode rawDataPart hex string into sensor values.
        """
        try:
            hex_bytes = [int(b, 16) for b in raw_data_part.strip().split()]
        except (ValueError, AttributeError):
            return {}

        if len(hex_bytes) < 32:
            return {}

        data_offset = 16
        registers = []
        i = data_offset
        while i + 1 < len(hex_bytes):
            val = (hex_bytes[i] << 8) | hex_bytes[i + 1]
            registers.append(val)
            i += 2

        def reg(idx: int, default=None):
            return registers[idx] if idx < len(registers) else default

        def signed16(val: int) -> int:
            return val - 65536 if val > 32767 else val

        ac_p = reg(24) or reg(31) or reg(42) or 0

        # PV total power and voltage
        # Inverter registers: R1 = PV1 voltage (0.1V), R2 = PV2 voltage (0.1V)
        # Residual floating voltage < 10V at night is clamped to 0.0V
        raw_pv1_v = reg(1, 0)
        raw_pv2_v = reg(2, 0)
        pv_v1 = round(raw_pv1_v * 0.1, 1) if raw_pv1_v and raw_pv1_v >= 100 else 0.0
        pv_v2 = round(raw_pv2_v * 0.1, 1) if raw_pv2_v and raw_pv2_v >= 100 else 0.0
        is_daytime = (pv_v1 > 50.0 or pv_v2 > 50.0)

        # ── Battery ─────────────────────────────────────────────────
        # Battery SOC:
        # R59 is the REAL BMS dynamic Battery SOC (0-100%) confirmed by cloud app and telemetry
        # R17 / R19 are internal inverter static/limit registers
        batt_soc = None
        if reg(59) is not None and 0 <= reg(59) <= 100:
            batt_soc = reg(59)
        elif reg(17) is not None and 0 <= reg(17) <= 100:
            batt_soc = reg(17)
        elif reg(19) is not None and 0 <= reg(19) <= 100:
            batt_soc = reg(19)

        # Battery Voltage:
        # R50 is the REAL Battery Voltage (0.01V, e.g. 5286 -> 52.86V for 51.2V LiFePO4)
        batt_volt = None
        if reg(50) and reg(50) > 1000:
            batt_volt = round(reg(50) * 0.01, 1)
        elif reg(50) and reg(50) > 100:
            batt_volt = round(reg(50) * 0.1, 1)
        elif reg(18) and reg(18) > 100:
            batt_volt = round(reg(18) * 0.1, 1)
        elif batt_soc:
            batt_volt = round(48.0 + (batt_soc / 100.0) * 5.2, 1)

        # Battery Power calculation:
        # At night (PV=0), if AC inverter is outputting power (ac_p > 20W), battery is DISCHARGING to feed AC:
        if not is_daytime:
            if ac_p and ac_p > 20:
                batt_power = -int(ac_p / 0.95)  # Negative = Discharging (with ~95% inverter efficiency)
            else:
                batt_power = 0
        else:
            # Daytime: if R44 > 0, charging, otherwise check net flow
            r44_val = signed16(reg(44, 0)) if reg(44) is not None else 0
            batt_power = r44_val

        # Battery current (A) = Power / Voltage
        batt_curr = None
        if batt_volt and batt_volt > 0 and batt_power is not None:
            batt_curr = round(batt_power / batt_volt, 2)

        # ── AC Output & Inverter Power ──────────────────────────────
        load_p = reg(43)
        if load_p is None:
            load_p = ac_p

        # ── Grid (Lưới điện) ────────────────────────────────────────
        # R53 = Grid Voltage (0.1V, e.g. 2298 -> 229.8V)
        # R54 = Grid Frequency (0.01Hz, e.g. 4999 -> 49.99Hz)
        # R51 = Grid Power (signed 16-bit: +import from EVN / -export to EVN)
        # R52 = Grid Current (0.01A)
        # R56 = AC Current (0.01A)
        grid_v = round(reg(53, 0) * 0.1, 1) if reg(53) else None
        grid_f = round(reg(54, 0) * 0.01, 2) if reg(54) else None
        grid_p = signed16(reg(51, 0)) if reg(51) is not None else None
        grid_c = round(signed16(reg(52, 0)) * 0.01, 2) if reg(52) is not None else None
        ac_c = round(reg(56, 0) * 0.01, 2) if reg(56) else (round(ac_p / 230.0, 2) if ac_p else 0.0)

        # ── PV Powers ───────────────────────────────────────────────
        pv1_p = 0 if not is_daytime else None
        pv2_p = 0 if not is_daytime else None
        pv_tot_p = 0 if not is_daytime else None

        result: dict = {
            # ── Status ──────────────────────────────────────────────────
            "raw_status": reg(0, 0),
            "online": reg(0, 0) == 1,

            # ── PV Input ────────────────────────────────────────────────
            "pv1Voltage": pv_v1,
            "pv2Voltage": pv_v2,
            "pv1Power": pv1_p,
            "pv2Power": pv2_p,
            "pvTotalPower": pv_tot_p,

            # ── Temperature ─────────────────────────────────────────────
            "temperature": reg(8) or reg(10),
            "batteryTemperature": reg(10),

            # ── Energy ──────────────────────────────────────────────────
            "totalPowerGeneration": round(reg(12, 0) * 0.1, 2) if reg(12) else None,
            "dailyPowerGeneration": None,

            # ── Battery ─────────────────────────────────────────────────
            "batterySOC": batt_soc,
            "batteryVoltage": batt_volt,
            "batteryPower": batt_power,
            "batteryCurrent": batt_curr,

            # ── AC Output & Inverter ────────────────────────────────────
            "acPower": ac_p,
            "inverterPower": ac_p,

            # ── Load (Nhà tiêu thụ) ─────────────────────────────────────
            "loadPower": load_p,

            # ── Grid (Lưới điện) ────────────────────────────────────────
            "gridVoltage": grid_v,
            "gridFrequency": grid_f,
            "gridPower": grid_p,
            "gridCurrent": grid_c,
            "acCurrent": ac_c,

            # ── Raw Packet Metadata ─────────────────────────────────────
            "_reg_count": len(registers),
        }

        return result

    # ─────────────────────────────────────────────────────────────────────────
    # Logs & Events
    # ─────────────────────────────────────────────────────────────────────────

    async def async_get_alarm_log(self, page: int = 1, page_size: int = 20) -> dict:
        """Get power/alarm logs."""
        return await self._post(
            "/dn/power/log/list",
            body={},
            params={"pageNum": page, "pageSize": page_size},
        )

    async def async_get_shutdown_log(self, page: int = 1, page_size: int = 20) -> dict:
        """Get shutdown/stop event logs."""
        return await self._post(
            "/dn/system/shutdown/list",
            body={},
            params={"pageNum": page, "pageSize": page_size},
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Raw Protocol Data
    # ─────────────────────────────────────────────────────────────────────────

    async def async_get_raw_data(self, page: int = 1, page_size: int = 10) -> dict:
        """Get raw protocol data frames."""
        return await self._post(
            "/dn/power/raw/data/list",
            body={},
            params={"pageNum": page, "pageSize": page_size},
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Remote Control / Settings
    # ─────────────────────────────────────────────────────────────────────────

    async def async_send_instruction(self, payload: dict) -> dict:
        """Send remote instruction to inverter."""
        return await self._post("/dn/send/instructions/sendIn", body=payload)

    async def async_update_data(self, payload: dict) -> dict:
        """Trigger data update on inverter."""
        return await self._post("/dn/send/instructions/UpdateData", body=payload)

    # ─────────────────────────────────────────────────────────────────────────
    # User Profile
    # ─────────────────────────────────────────────────────────────────────────

    async def async_get_user_profile(self) -> dict:
        """Get user profile data."""
        try:
            data = await self._post(f"/dn/system/user/{self._user_id}", body=None)
            return data.get("data", {})
        except Exception:
            return {}

    # ─────────────────────────────────────────────────────────────────────────
    # All data for coordinator (single call batch)
    # ─────────────────────────────────────────────────────────────────────────

    async def async_fetch_all(self, inverter_name: str | None = None) -> dict:
        """Fetch all sensor data in one batch. Returns combined dict."""
        results = {}

        # 1. Overview (summary stats — currentPower, daily kWh, income...)
        try:
            results["overview"] = await self.async_get_overview()
        except Exception as err:
            _LOGGER.warning("Mini EMS fetch overview failed: %s", err)
            results["overview"] = {}

        # 2. Inverter realtime data & Raw Modbus frame
        ov = results.get("overview", {})
        if inverter_name:
            try:
                # 2.1 Lấy dữ liệu xử lý sẵn trực tiếp từ Cloud App (cập nhật SOC, trạng thái liên tục)
                cloud_dev = await self.async_get_inverter_data(inverter_name) or {}

                # 2.2 Lấy chi tiết thanh ghi Modbus mới nhất (để giải mã chi tiết lưới, PV, dòng điện)
                inv = await self.async_get_latest_raw_frame(inverter_name)
                if not inv:
                    inv = {}

                # Gộp dữ liệu: Trích xuất mọi trường SOC từ cloud app
                soc_val = (
                    cloud_dev.get("batterySOC")
                    if cloud_dev.get("batterySOC") is not None
                    else (
                        cloud_dev.get("soc")
                        if cloud_dev.get("soc") is not None
                        else (
                            cloud_dev.get("bmsSoc")
                            if cloud_dev.get("bmsSoc") is not None
                            else cloud_dev.get("batterySoc")
                        )
                    )
                )
                if soc_val is not None:
                    try:
                        inv["batterySOC"] = int(float(soc_val))
                    except (ValueError, TypeError):
                        pass

                if cloud_dev.get("batteryVoltage") is not None:
                    inv["batteryVoltage"] = cloud_dev["batteryVoltage"]
                if cloud_dev.get("batteryPower") is not None and not inv.get("batteryPower"):
                    inv["batteryPower"] = cloud_dev["batteryPower"]
                if cloud_dev.get("gridPower") is not None and inv.get("gridPower") is None:
                    inv["gridPower"] = cloud_dev["gridPower"]
                if cloud_dev.get("loadPower") is not None and not inv.get("loadPower"):
                    inv["loadPower"] = cloud_dev["loadPower"]

                # Ensure overview fallbacks
                if ov:
                    if not inv.get("dailyPowerGeneration"):
                        inv["dailyPowerGeneration"] = ov.get("dailyPowerGeneration")
                    if not inv.get("acPower"):
                        inv["acPower"] = ov.get("currentPower")
                    if not inv.get("inverterPower"):
                        inv["inverterPower"] = inv.get("acPower") or ov.get("currentPower")
                    if not inv.get("totalPowerGeneration") and ov.get("totalPowerGeneration"):
                        inv["totalPowerGeneration"] = ov.get("totalPowerGeneration")
                results["inverter"] = inv
                _LOGGER.debug(
                    "Mini EMS raw frame decoded: %d registers for %s, batterySOC=%s",
                    inv.get("_reg_count", 0),
                    inverter_name,
                    inv.get("batterySOC"),
                )
            except Exception as err:
                _LOGGER.warning("Mini EMS fetch raw frame failed: %s", err)
                results["inverter"] = {
                    "acPower": ov.get("currentPower"),
                    "inverterPower": ov.get("currentPower"),
                    "dailyPowerGeneration": ov.get("dailyPowerGeneration"),
                    "totalPowerGeneration": ov.get("totalPowerGeneration"),
                }
        else:
            results["inverter"] = {
                "acPower": ov.get("currentPower"),
                "inverterPower": ov.get("currentPower"),
                "dailyPowerGeneration": ov.get("dailyPowerGeneration"),
                "totalPowerGeneration": ov.get("totalPowerGeneration"),
            }

        # 3. Station electricity (hourly kWh breakdown)
        try:
            results["electricity"] = await self.async_get_station_electricity()
        except Exception as err:
            _LOGGER.warning("Mini EMS fetch electricity failed: %s", err)
            results["electricity"] = []

        return results
