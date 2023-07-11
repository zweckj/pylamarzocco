# URLs
TOKEN_URL = "https://cms.lamarzocco.io/oauth/v2/token"
CUSTOMER_URL = "https://cms.lamarzocco.io/api/customer"
GW_MACHINE_BASE_URL = "https://gw-lmz.lamarzocco.io/v1/home/machines"

POLLING_DELAY_S = 20
POLLING_DELAY_STATISTICS_S = 60
WEBSOCKET_RETRY_DELAY = 20

MODEL_LMU = "Micra"

BT_MODEL_NAMES = [
    "MICRA",
    "MINI",
    "GS3"
]

# Key Names for Dictionaries
KEY = "key"
SERIAL_NUMBER = "serial_number"
MACHINE_NAME = "machine_name"
MODEL_NAME = "model_name"

# Dict keys are camel case for local API, all upper for remote API
MACHINE_MODE="machineMode"
STEAM_BOILER_NAME = "SteamBoiler"
COFFEE_BOILER_NAME = "CoffeeBoiler1"
BOILER_TARGET_TEMP = "boilerTargetTemperature"
BOILERS = "boilers"
PLUMBED_IN = "isPlumbedIn"
PRE_INFUSION_SETTINGS = "preinfusionSettings"
WEEKLY_SCHEDULING_CONFIG = "weeklySchedulingConfig"
BACKFLUSH_ENABLED = "isBackFlushEnabled"
CURRENT = "current"
TARGET = "target"
TANK_STATUS = "tankStatus"
BREW_ACTIVE = "brew_active"
BREW_ACTIVE_DURATION = "brew_active_duration"


# bluetooth
SETTINGS_CHARACTERISTIC = "050b7847-e12b-09a8-b04b-8e0922a9abab"
AUTH_CHARACTERISTIC = "090b7847-e12b-09a8-b04b-8e0922a9abab"
