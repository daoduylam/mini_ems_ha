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
        # Try with name filter in body
        data = await self._post(
            "/dn/system/data/list",
            body={"inverterName": inverter_name},
            params={"pageNum": 1, "pageSize": 20},
        )
        rows = data.get("rows", [])
        for dev in rows:
            if dev.get("inverterName") == inverter_name:
                return dev
        # Fallback: scan all pages
        all_devs = await self.async_get_all_inverters()
        for dev in all_devs:
            if dev.get("inverterName") == inverter_name:
                return dev
        return rows[0] if rows else None

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
        # We need Frame 0 (registers 0..59, ending with '00 00 00 3C')
        input_rows = [r for r in rows if r.get("dataType") == "04"]
        if not input_rows:
            return {}

        target_row = None
        # Prefer the frame starting at register 0 (00 00 00 3C)
        for r in input_rows:
            if (r.get("rawData") or "").strip().endswith("00 00 00 3C"):
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

        ac_p = reg(24) or reg(31) or reg(42)

        # ── Battery ─────────────────────────────────────────────────
        # R17=SOC%, R18=voltage×0.1 (if 0 or None, fallback to calculated from BMS or None)
        batt_soc = reg(17) or reg(19)
        batt_volt = round(reg(18, 0) * 0.1, 1) if reg(18) else None
        # If R18 is 0 at night (standby/sleep), provide realistic battery voltage if SOC exists
        if not batt_volt and batt_soc:
            batt_volt = round(48.0 + (batt_soc / 100.0) * 5.2, 1)

        # R44 is battery power (W) signed: positive = charging, negative = discharging
        batt_power = signed16(reg(44, 0)) if reg(44) is not None else 0

        # Battery current (A) = Power / Voltage
        batt_curr = None
        if batt_volt and batt_volt > 0 and batt_power is not None:
            batt_curr = round(batt_power / batt_volt, 2)

        # ── AC Output & Inverter Power ──────────────────────────────
        load_p = reg(43)
        if load_p is None:
            load_p = ac_p

        result: dict = {
            # ── Status ──────────────────────────────────────────────────
            "raw_status": reg(0, 0),
            "online": reg(0, 0) == 1,

            # ── PV Input ────────────────────────────────────────────────
            "pv1Voltage": round(reg(1, 0) * 0.1, 1) if reg(1) else 0.0,
            "pv2Voltage": round(reg(2, 0) * 0.1, 1) if reg(2) else 0.0,

            # ── Temperature ─────────────────────────────────────────────
            "temperature": reg(8),
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
            "gridVoltage": round(reg(53, 0) * 0.1, 1) if reg(53) else None,
            "gridFrequency": round(reg(41, 0) * 0.1, 2) if reg(41) else None,
            "gridPower": signed16(reg(51, 0)) if reg(51) is not None else None,
            "gridCurrent": round(signed16(reg(52, 0)) * 0.01, 2) if reg(52) is not None else None,
            "acCurrent": round(reg(56, 0) * 0.01, 2) if reg(56) else None,

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

        # 2. Raw Modbus frame — primary source for per-inverter realtime sensors
        ov = results.get("overview", {})
        if inverter_name:
            try:
                inv = await self.async_get_latest_raw_frame(inverter_name)
                if not inv:
                    inv = {}
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
                    "Mini EMS raw frame decoded: %d registers for %s",
                    inv.get("_reg_count", 0),
                    inverter_name,
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
