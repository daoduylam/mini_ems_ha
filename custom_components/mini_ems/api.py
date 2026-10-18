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

        # Overview (always fetch)
        try:
            results["overview"] = await self.async_get_overview()
        except Exception as err:
            _LOGGER.warning("Mini EMS fetch overview failed: %s", err)
            results["overview"] = {}

        # Per-inverter real-time data
        try:
            if inverter_name:
                inv = await self.async_get_inverter_data(inverter_name)
                results["inverter"] = inv or {}
            else:
                rows = await self.async_get_inverter_list(page_size=50)
                results["inverter"] = rows[0] if rows else {}
        except Exception as err:
            _LOGGER.warning("Mini EMS fetch inverter failed: %s", err)
            results["inverter"] = {}

        # Station electricity
        try:
            results["electricity"] = await self.async_get_station_electricity()
        except Exception as err:
            _LOGGER.warning("Mini EMS fetch electricity failed: %s", err)
            results["electricity"] = []

        return results
