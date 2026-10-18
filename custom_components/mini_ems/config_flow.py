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
        """Handle the initial step - login."""
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
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                    "user_id": str(login_result.get("userId", "")),
                }
                # Fetch inverter list for selection
                try:
                    inverters = await api.async_get_inverter_list(page_size=100)
                    self._inverter_list = inverters
                    if inverters:
                        return await self.async_step_select_inverter()
                except Exception:
                    pass

                # If no inverter list, use first overview
                overview = await api.async_get_overview()
                return self.async_create_entry(
                    title=f"Mini EMS - {user_input[CONF_USERNAME]}",
                    data={
                        **self._login_data,
                        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                    },
                )
            except MiniEmsAuthError:
                errors["base"] = "invalid_auth"
            except MiniEmsApiError:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.TEXT, autocomplete="username")
                    ),
                    vol.Required(CONF_PASSWORD): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD, autocomplete="current-password")
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
            inv_id = int(user_input["inverter_id"].split("|")[0].strip())
            inv_name = user_input["inverter_id"].split("|")[-1].strip() if "|" in user_input["inverter_id"] else ""
            inv_data = next(
                (d for d in self._inverter_list if d.get("inverterId") == inv_id),
                {},
            )
            return self.async_create_entry(
                title=f"Mini EMS - {inv_data.get('inverterName', inv_name or 'Inverter')}",
                data={
                    **self._login_data,
                    CONF_INVERTER_ID: inv_id,
                    "inverter_name": inv_data.get("inverterName", ""),
                    "power_id": inv_data.get("powerId", ""),
                    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                },
            )

        options = []
        for inv in self._inverter_list[:20]:
            inv_id = inv.get("inverterId", "")
            inv_name = inv.get("inverterName", f"ID-{inv_id}")
            power = inv.get("currentPower", inv.get("acPower", ""))
            label = f"{inv_id} | {inv_name}" + (f" ({power}W)" if power else "")
            options.append(label)

        if not options:
            options = ["0 | Default Inverter"]

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
