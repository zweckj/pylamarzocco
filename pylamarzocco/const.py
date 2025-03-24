"""Constants for La Marzocco Cloud."""

from enum import StrEnum

TOKEN_EXPIRATION = 60 * 60 * 24 * 5  # 5 days

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


class StompMessageType(StrEnum):
    """Stomp message types."""

    CONNECT = "CONNECT"
    CONNECTED = "CONNECTED"
    DISCONNECT = "DISCONNECT"
    SUBSCRIBE = "SUBSCRIBE"
    UNSUBSCRIBE = "UNSUBSCRIBE"
    MESSAGE = "MESSAGE"


class DeviceType(StrEnum):
    """Device types."""

    MACHINE = "CoffeeMachine"
    GRINDER = "Grinder"


class ModelCode(StrEnum):
    """Model codes."""

    LINEA_MINI = "LINEAMINI"
    LINEA_MICRA = "LINEAMICRA"
    LINEA_MINI_R = "LINEAMINIR"
    GS3 = "GS3"
    GS3_MP = "GS3MP"
    GS3_AV = "GS3AV"


class FirmwareType(StrEnum):
    """Firmware types."""

    MACHINE = "Machine"
    GATEWAY = "Gateway"


class DoseIndexType(StrEnum):
    """Dose index types."""

    BY_GROUP = "ByGroup"
    BY_DOSE = "ByDose"  # TODO: Check if this is correct


class SmartStandByType(StrEnum):
    """Smart Standby types."""

    LAST_BREW = "LastBrewing"
    POWER_ON = "PowerOn"
