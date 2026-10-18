"""Constants for Mini EMS Integration."""

DOMAIN = "mini_ems"

# API
API_BASE_URL = "https://mini-ems.com:8081"
API_LOGIN_URL = f"{API_BASE_URL}/dn/login"
DEFAULT_SCAN_INTERVAL = 30  # seconds

# Config entry keys
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_INVERTER_ID = "inverter_id"
CONF_POWER_ID = "power_id"
CONF_SCAN_INTERVAL = "scan_interval"

# Connection Modes
CONF_CONNECTION_TYPE = "connection_type"
CONNECTION_TYPE_CLOUD = "cloud"
CONNECTION_TYPE_LOCAL = "local"

# Local Mode Config
CONF_PORT = "port"
DEFAULT_PORT = 15444
CONF_SERIAL = "serial"
CONF_POLL_DELAY = "poll_delay"
DEFAULT_POLL_DELAY = 5
CONF_DATALOGGER_URL = "datalogger_url"
CONF_DATALOGGER_USERNAME = "datalogger_username"
DEFAULT_DATALOGGER_USERNAME = "admin"
CONF_DATALOGGER_PASSWORD = "datalogger_password"
DEFAULT_DATALOGGER_PASSWORD = "admin"
CONF_LISTENER_IP = "listener_ip"
CONF_IP_CHECK_INTERVAL = "ip_check_interval"
DEFAULT_IP_CHECK_INTERVAL = 300

# Data keys
DATA_COORDINATOR = "coordinator"
DATA_API = "api"
DATA_HUB = "hub"
