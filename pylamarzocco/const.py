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

    CM_MACHINE_STATUS = "CMMachineStatus"
    CM_COFFEE_BOILER = "CMCoffeeBoiler"
    CM_STEAM_BOILER_LEVEL = "CMSteamBoilerLevel"
    CM_PRE_EXTRACTION = "CMPreExtraction"
    CM_PRE_BREWING = "CMPreBrewing"
    CM_BACK_FLUSH = "CMBackFlush"
    CM_MACHINE_GROUP_STATUS = "CMMachineGroupStatus"
    CM_STEAM_BOILER_TEMPERATURE = "CMSteamBoilerTemperature"
    CM_GROUP_DOSES = "CMGroupDoses"
    CM_PRE_INFUSION_ENABLE = "CMPreInfusionEnable"
    CM_PRE_INFUSION = "CMPreInfusion"
    CM_BREW_BY_WEIGHT_DOSES = "CMBrewByWeightDoses"
    CM_CUP_WARMER = "CMCupWarmer"
    CM_HOT_WATER_DOSE = "CMHotWaterDose"
    CM_AUTO_FLUSH = "CMAutoFlush"
    CM_RINSE_FLUSH = "CMRinseFlush"
    CM_STEAM_FLUSH = "CMSteamFlush"
    CM_NO_WATER = "CMNoWater"
    G_MACHINE_STATUS = "GMachineStatus"
    G_DOSES = "GDoses"
    G_SINGLE_DOSE_MODE = "GSingleDoseMode"
    G_BARISTA_LIGHT = "GBaristaLight"
    G_HOPPER_OPENED = "GHopperOpened"
    G_MIRROR_DOSES = "GMirrorDoses"
    G_MORE_DOSE = "GMoreDose"
    G_GRIND_WITH = "GGrindWith"

class SteamTargetLevel(StrEnum):
    """Steam target levels."""

    LEVEL_1 = "Level1"
    LEVEL_2 = "Level2"
    LEVEL_3 = "Level3"