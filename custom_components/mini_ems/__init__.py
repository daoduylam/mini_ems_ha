from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import (
    CONF_CONNECTION_TYPE,
    CONF_PORT,
    CONF_SERIAL,
    CONF_POLL_DELAY,
    CONF_DATALOGGER_URL,
    CONF_DATALOGGER_USERNAME,
    CONF_DATALOGGER_PASSWORD,
    CONF_LISTENER_IP,
    CONF_IP_CHECK_INTERVAL,
    CONNECTION_TYPE_CLOUD,
    CONNECTION_TYPE_LOCAL,
    DATA_COORDINATOR,
    DATA_HUB,
    DEFAULT_PORT,
    DEFAULT_POLL_DELAY,
    DOMAIN,
)
from .coordinator import MiniEmsCoordinator
from .local import MiniEmsLocalHub

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Mini EMS from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    conn_type = entry.data.get(CONF_CONNECTION_TYPE, CONNECTION_TYPE_CLOUD)

    if conn_type == CONNECTION_TYPE_LOCAL:
        hub = MiniEmsLocalHub(
            hass,
            entry.entry_id,
            port=entry.data.get(CONF_PORT, DEFAULT_PORT),
            serial=entry.data.get(CONF_SERIAL, entry.data.get("inverter_name", "")),
            poll_delay=entry.options.get(CONF_POLL_DELAY, entry.data.get(CONF_POLL_DELAY, DEFAULT_POLL_DELAY)),
            datalogger_url=entry.data.get(CONF_DATALOGGER_URL, ""),
            datalogger_username=entry.data.get(CONF_DATALOGGER_USERNAME, ""),
            datalogger_password=entry.data.get(CONF_DATALOGGER_PASSWORD, ""),
            listener_ip=entry.data.get(CONF_LISTENER_IP, ""),
            ip_check_interval=entry.data.get(CONF_IP_CHECK_INTERVAL, 300),
        )
        await hub.async_start()
        hass.data[DOMAIN][entry.entry_id] = {DATA_HUB: hub}
        await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR, Platform.BINARY_SENSOR])
        return True

    # Cloud mode
    coordinator = MiniEmsCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {DATA_COORDINATOR: coordinator}
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    stored = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    if DATA_HUB in stored:
        await stored[DATA_HUB].async_stop()
        platforms = [Platform.SENSOR, Platform.BINARY_SENSOR]
    else:
        platforms = PLATFORMS

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, platforms):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
