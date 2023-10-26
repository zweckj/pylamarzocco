"""Constants for La Marzocco Cloud."""
from typing import Final

# Base URL for La Marzocco Cloud
TOKEN_URL: Final = "https://cms.lamarzocco.io/oauth/v2/token"
CUSTOMER_URL: Final = "https://cms.lamarzocco.io/api/customer"
GW_BASE_URL: Final = "https://gw-lmz.lamarzocco.io/v1/home"
GW_MACHINE_BASE_URL: Final = f"{GW_BASE_URL}/machines"
GW_AWS_PROXY_BASE_URL: Final = f"{GW_BASE_URL}/aws-proxy"

DEFAULT_PORT = 8081

POLLING_DELAY_S: Final = 20
POLLING_DELAY_STATISTICS_S: Final = 60
WEBSOCKET_RETRY_DELAY: Final = 20

# Key Names for Dictionaries

BACKFLUSH_ENABLED: Final = "isBackFlushEnabled"
BOILER_TARGET_TEMP: Final = "boilerTargetTemperature"
BOILERS: Final = "boilers"
BREW_ACTIVE: Final = "brew_active"
BREW_ACTIVE_DURATION: Final = "brew_active_duration"
COFFEE_BOILER_NAME: Final = "CoffeeBoiler1"
CURRENT: Final = "current"
KEY: Final = "key"
MACHINE_NAME: Final = "machine_name"
MACHINE_MODE: Final = "machineMode"
MODEL_NAME: Final = "model_name"
PLUMBED_IN: Final = "isPlumbedIn"
PRE_INFUSION_SETTINGS: Final = "preinfusionSettings"
SERIAL_NUMBER: Final = "serial_number"
STEAM_BOILER_NAME: Final = "SteamBoiler"
TANK_STATUS: Final = "tankStatus"
TARGET: Final = "target"
WEEKLY_SCHEDULING_CONFIG: Final = "weeklySchedulingConfig"


# bluetooth
BT_MODEL_NAMES: Final = ["MICRA", "MINI", "GS3"]
SETTINGS_CHARACTERISTIC: Final = "050b7847-e12b-09a8-b04b-8e0922a9abab"
AUTH_CHARACTERISTIC: Final = "090b7847-e12b-09a8-b04b-8e0922a9abab"
