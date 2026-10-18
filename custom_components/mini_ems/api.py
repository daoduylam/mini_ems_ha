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

        # Find latest INPUT frame (dataType=04 = function code 04 = Read Input Registers)
        input_rows = [r for r in rows if r.get("dataType") == "04"]
        if not input_rows:
            return {}

        # Fetch full record with rawDataPart
        raw_id = input_rows[0].get("rawDataId")
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

        Frame format:
        - 16 bytes: request header (unit_id + func_code + serial + start_reg + count)
        - 120 bytes: response data = 60 registers × 2 bytes each

        Register map confirmed via cross-referencing with overviewApp live values:
          R00 = status (1=online)
          R01 = PV1 voltage × 0.1V
          R02 = PV2 voltage × 0.1V
          R08 = inverter temperature °C
          R09 = battery temperature °C
          R12 = total energy × 0.1 kWh  (confirmed: 23708 = 2370.8 kWh)
          R17 = battery SOC %
          R18 = battery voltage × 0.1V
          R19 = battery SOC (duplicate)
          R24 = AC output power W  (confirmed: 571W)
          R28 = load power W
          R31 = inverter power W
          R33 = daily energy × 0.1 kWh
          R52 = battery current signed × 0.01A
          R53 = grid power signed W
          R54 = grid voltage × 0.1V  (confirmed: 230.3V)
          R56 = grid frequency × 0.1Hz  (confirmed: 49.9Hz)
          R57 = AC output current × 0.01A
        """
        try:
            # Parse hex bytes
            hex_bytes = [int(b, 16) for b in raw_data_part.strip().split()]
        except (ValueError, AttributeError):
            return {}

        if len(hex_bytes) < 32:
            return {}

        # Skip 16-byte request header, read register pairs
        data_offset = 16
        registers = []
        i = data_offset
        while i + 1 < len(hex_bytes):
            val = (hex_bytes[i] << 8) | hex_bytes[i + 1]
            registers.append(val)
            i += 2

        def reg(idx: int, default=None):
            """Get register value by index."""
            return registers[idx] if idx < len(registers) else default

        def signed(val: int) -> int:
            """Convert 16-bit unsigned to signed."""
            return val - 65536 if val > 32767 else val

        result: dict = {
            # Status
            "raw_status": reg(0, 0),
            "online": reg(0, 0) == 1,

            # PV
            "pv1Voltage": round(reg(1, 0) * 0.1, 1) if reg(1, 0) else None,
            "pv2Voltage": round(reg(2, 0) * 0.1, 1) if reg(2, 0) else None,

            # Temperature
            "temperature": reg(8),
            "batteryTemperature": reg(9),

            # Energy
            "totalPowerGeneration": round(reg(12, 0) * 0.1, 2) if reg(12) else None,
            "dailyPowerGeneration": round(reg(33, 0) * 0.1, 2) if reg(33) else None,

            # Battery
            "batterySOC": reg(17),
            "batteryVoltage": round(reg(18, 0) * 0.1, 1) if reg(18) else None,
            "batteryCurrent": round(signed(reg(52, 0)) * 0.01, 2) if reg(52) is not None else None,
            "batteryPower": signed(reg(52, 0)) if reg(52) is not None else None,

            # Output / Load
            "acPower": reg(24),
            "loadPower": reg(28),
            "inverterPower": reg(31),

            # Grid
            "gridVoltage": round(reg(54, 0) * 0.1, 1) if reg(54) else None,
            "gridFrequency": round(reg(56, 0) * 0.1, 2) if reg(56) else None,
            "gridPower": signed(reg(53, 0)) if reg(53) is not None else None,
            "acCurrent": round(reg(57, 0) * 0.01, 2) if reg(57) else None,

            # Raw registers for debugging
            "_reg_count": len(registers),
        }

        # Calculate battery power from voltage × current
        if result["batteryVoltage"] and result["batteryCurrent"]:
            result["batteryPower"] = round(
                result["batteryVoltage"] * result["batteryCurrent"], 1
            )

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
        if inverter_name:
            try:
                results["inverter"] = await self.async_get_latest_raw_frame(inverter_name)
                _LOGGER.debug(
                    "Mini EMS raw frame decoded: %d registers for %s",
                    results["inverter"].get("_reg_count", 0),
                    inverter_name,
                )
            except Exception as err:
                _LOGGER.warning("Mini EMS fetch raw frame failed: %s", err)
                results["inverter"] = {}
        else:
            results["inverter"] = {}

        # 3. Station electricity (hourly kWh breakdown)
        try:
            results["electricity"] = await self.async_get_station_electricity()
        except Exception as err:
            _LOGGER.warning("Mini EMS fetch electricity failed: %s", err)
            results["electricity"] = []

        return results
