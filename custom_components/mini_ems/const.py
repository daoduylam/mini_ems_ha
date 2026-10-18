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

# Data keys
DATA_COORDINATOR = "coordinator"
DATA_API = "api"
