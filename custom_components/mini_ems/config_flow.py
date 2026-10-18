"""Config flow for Mini EMS integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
import aiohttp

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import MiniEmsApi, MiniEmsApiError, MiniEmsAuthError
from .const import (
    CONF_INVERTER_ID,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class MiniEmsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Mini EMS."""

    VERSION = 1
    _login_data: dict = {}
    _inverter_list: list = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose between Cloud (Mini-EMS) and Local (Port 15444)."""
        if user_input is not None:
            mode = user_input.get("mode")
            if mode == "local":
                return await self.async_step_local()
            return await self.async_step_cloud()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("mode", default="cloud"): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                {"value": "cloud", "label": "Cloud (Tài khoản mini-ems.com)"},
                                {"value": "local", "label": "Local (Trực tiếp Port 15444 - Không cần Cloud)"},
                            ],
                            mode=SelectSelectorMode.LIST,
                        )
                    )
                }
            ),
        )

    async def async_step_local(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure local mode."""
        if user_input is not None:
            serial = user_input.get("serial", "").strip() or "DBC2511007"
            return self.async_create_entry(
                title=f"Absaar/MiniEMS Local ({serial})",
                data={
                    "connection_type": "local",
                    "serial": serial,
                    "port": user_input.get("port", 15444),
                    "poll_delay": user_input.get("poll_delay", 5),
                },
            )

        return self.async_show_form(
            step_id="local",
            data_schema=vol.Schema(
                {
                    vol.Required("port", default=15444): NumberSelector(
                        NumberSelectorConfig(min=1024, max=65535, mode=NumberSelectorMode.BOX)
                    ),
                    vol.Optional("serial", default="DBC2511007"): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.TEXT)
                    ),
                    vol.Required("poll_delay", default=5): NumberSelector(
                        NumberSelectorConfig(min=1, max=60, unit_of_measurement="giây", mode=NumberSelectorMode.BOX)
                    ),
                }
            ),
            description_placeholders={
                "hint": "Cấu hình cổng lắng nghe kết nối từ cục Wi-Fi logger (Mặc định Port 15444)",
            },
        )

    async def async_step_cloud(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle Cloud login step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass, verify_ssl=False)
            api = MiniEmsApi(
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
                session=session,
            )
            try:
                login_result = await api.async_login()
                self._login_data = {
                    "connection_type": "cloud",
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                    "user_id": str(login_result.get("userId", "")),
                }

                # Nếu user nhập thẳng serial number
                manual_serial = user_input.get("inverter_serial", "").strip()
                if manual_serial:
                    return self.async_create_entry(
                        title=f"Mini EMS - {manual_serial}",
                        data={
                            **self._login_data,
                            "inverter_name": manual_serial,
                            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                        },
                    )

                # Lấy danh sách từ API (tất cả trang)
                try:
                    self._inverter_list = await api.async_get_all_inverters()
                except Exception:
                    self._inverter_list = await api.async_get_inverter_list(page_size=50)

                if self._inverter_list:
                    return await self.async_step_select_inverter()

                errors["base"] = "no_devices"

            except MiniEmsAuthError:
                errors["base"] = "invalid_auth"
            except MiniEmsApiError:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="cloud",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.TEXT, autocomplete="username")
                    ),
                    vol.Required(CONF_PASSWORD): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD, autocomplete="current-password")
                    ),
                    vol.Optional("inverter_serial", default="DBC2511007"): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.TEXT)
                    ),
                }
            ),
            errors=errors,
            description_placeholders={
                "url": "https://mini-ems.com",
            },
        )

    async def async_step_select_inverter(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select which inverter to monitor."""
        if user_input is not None:
            # Format: "16389 | DBC2511007"
            selected = user_input["inverter_id"]
            parts = selected.split("|")
            inv_name = parts[-1].strip() if len(parts) > 1 else parts[0].strip()
            inv_data = next(
                (d for d in self._inverter_list if d.get("inverterName") == inv_name),
                {},
            )
            return self.async_create_entry(
                title=f"Mini EMS - {inv_name}",
                data={
                    **self._login_data,
                    "inverter_name": inv_name,
                    CONF_INVERTER_ID: inv_data.get("inverterId"),
                    "power_id": inv_data.get("powerId", ""),
                    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                },
            )

        options = []
        for inv in self._inverter_list[:20]:
            inv_id = inv.get("inverterId", "")
            inv_name = inv.get("inverterName", f"ID-{inv_id}")
            power = inv.get("currentPower") or inv.get("acPower", "")
            label = f"{inv_id} | {inv_name}" + (f" ({power}W)" if power else "")
            options.append(label)

        if not options:
            options = ["0 | Unknown"]

        return self.async_show_form(
            step_id="select_inverter",
            data_schema=vol.Schema(
                {
                    vol.Required("inverter_id"): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            mode=SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return options flow handler."""
        return MiniEmsOptionsFlow(config_entry)


class MiniEmsOptionsFlow(OptionsFlow):
    """Handle options for Mini EMS."""

    def __init__(self, config_entry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=current_interval,
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=10,
                            max=3600,
                            step=10,
                            unit_of_measurement="seconds",
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
        )
