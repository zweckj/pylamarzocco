"""Constants for La Marzocco Cloud."""

from enum import StrEnum

# Base URL for La Marzocco Cloud

BASE_URL = "lion.lamarzocco.io"
CUSTOMER_APP_URL = f"https://{BASE_URL}/api/customer-app"


class MachineState(StrEnum):
    """Machine states."""

    BREWING_MODE = "BrewingMode"
    STANDBY = "StandBy"

class PreExtractionMode(StrEnum):
    """Pre-extraction modes."""

    PREINFUSION = "PreInfusion"
    PREBREWING = "PreBrewing"
    DISABLED = "Disabled"

class WidgetType(StrEnum):
    """Widget types."""

    MACHINE_STATUS = "CMMachineStatus"
    COFFEE_BOILER = "CMCoffeeBoiler"
    STEAM_BOILER_LEVEL = "CMSteamBoilerLevel"
    PRE_EXTRACTION = "CMPreExtraction"
    PRE_BREWING = "CMPreBrewing"
    BACK_FLUSH = "CMBackFlush"

class SteamTargetLevel(StrEnum):
    """Steam target levels."""

    LEVEL_1 = "Level1"
    LEVEL_2 = "Level2"
    LEVEL_3 = "Level3"