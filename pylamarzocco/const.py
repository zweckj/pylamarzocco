"""Constants for La Marzocco Cloud."""

from __future__ import annotations

from enum import StrEnum

BASE_URL = "lion.lamarzocco.io"
CUSTOMER_APP_URL = f"https://{BASE_URL}/api/customer-app"


class MachineMode(StrEnum):
    """Machine states."""

    BREWING_MODE = "BrewingMode"
    ECO_MODE = "EcoMode"
    STANDBY = "StandBy"


class MachineState(StrEnum):
    """Machine statuses."""

    STANDBY = "StandBy"
    POWERED_ON = "PoweredOn"
    BREWING = "Brewing"
    OFF = "Off"


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
    # scale
    THING_SCALE = "ThingScale"
    # statistic widgets
    COFFEE_AND_FLUSH_TREND = "COFFEE_AND_FLUSH_TREND"
    LAST_COFFEE = "LAST_COFFEE"
    COFFEE_AND_FLUSH_COUNTER = "COFFEE_AND_FLUSH_COUNTER"


class CommandStatus(StrEnum):
    """Command statuses."""

    SUCCESS = "Success"
    ERROR = "Error"
    TIMEOUT = "Timeout"
    PENDING = "Pending"


class SteamTargetLevel(StrEnum):
    """Steam target levels."""

    LEVEL_1 = "Level1"
    LEVEL_2 = "Level2"
    LEVEL_3 = "Level3"


class StompMessageType(StrEnum):
    """Stomp message types."""

    CONNECT = "CONNECT"
    CONNECTED = "CONNECTED"
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
    PICO_GRINDER = "PICOGRINDER"
    SWAN_GRINDER = "SWANGRINDER"


class ModelName(StrEnum):
    """Model codes."""

    LINEA_MINI = "Linea Mini"
    LINEA_MICRA = "Linea Micra"
    LINEA_MINI_R = "Linea Mini R"
    GS3 = "GS3"
    GS3_MP = "GS3 MP"
    GS3_AV = "GS3 AV"
    PICO_GRINDER = "Pico"
    SWAN_GRINDER = "Swan"

    @classmethod
    def from_string(cls, name: str) -> ModelName:
        """Convert a string to a ModelName enum."""
        mapping = {
            "GS3MP": "GS3 MP",
            "GS3AV": "GS3 AV",
            "LINEAMINI2023": "Linea Mini R",
            "LINEAMICRA": "Linea Micra",
            "LINEAMINI": "Linea Mini",
            "MICRA": "Linea Micra",
            "PICOGRINDER": "Pico",
            "SWANGRINDER": "Swan",
        }
        if (key := "".join(name.upper().split())) not in mapping:
            raise ValueError(f"Invalid model name: {name}")
        return cls(mapping[key])


class FirmwareType(StrEnum):
    """Firmware types."""

    MACHINE = "Machine"
    GATEWAY = "Gateway"


class DoseIndexType(StrEnum):
    """Dose index types."""

    BY_GROUP = "ByGroup"
    BY_DOSE = "ByDose"  # TODO: Check if this is correct


class DoseMode(StrEnum):
    """Dose modes."""

    CONTINUOUS = "Continuous"
    PULSES_TYPE = "PulsesType"


class DoseIndex(StrEnum):
    """Dose index types."""

    CONTINUOUS = "Continuous"
    BY_GROUP = "ByGroup"
    DOSE_A = "DoseA"
    DOSE_B = "DoseB"
    DOSE_C = "DoseC"
    DOSE_D = "DoseD"


class SmartStandByType(StrEnum):
    """Smart Standby types."""

    LAST_BREW = "LastBrewing"
    POWER_ON = "PowerOn"


class BoilerStatus(StrEnum):
    """Boiler statuses."""

    STAND_BY = "StandBy"
    HEATING = "HeatingUp"
    READY = "Ready"
    NO_WATER = "NoWater"
    OFF = "Off"


class WeekDay(StrEnum):
    """Week days."""

    MONDAY = "Monday"
    TUESDAY = "Tuesday"
    WEDNESDAY = "Wednesday"
    THURSDAY = "Thursday"
    FRIDAY = "Friday"
    SATURDAY = "Saturday"
    SUNDAY = "Sunday"


class UpdateStatus(StrEnum):
    """Update statuses."""

    TO_UPDATE = "ToUpdate"
    UPDATED = "Updated"


class UpdateCommandStatus(StrEnum):
    """Update progress statuses."""

    IN_PROGRESS = "InProgress"


class UpdateProgressInfo(StrEnum):
    """Update progress info."""

    DOWNLOAD = "download"
    REBOOTING = "rebooting"
    STARTING_PROCESS = "starting process"


class BoilerType(StrEnum):
    """La Marzocco Coffee Machine Boilers."""

    COFFEE = "CoffeeBoiler1"
    STEAM = "SteamBoiler"


class BackFlushStatus(StrEnum):
    """Back flush statuses."""

    REQUESTED = "Requested"
    OFF = "Off"


class BluetoothReadSetting(StrEnum):
    """Declare what to read from the Bluetooth device."""

    MACHINE_CAPABILITIES = "machineCapabilities"
    MACHINE_MODE = "machineMode"
    TANK_STATUS = "tankStatus"
    BOILERS = "boilers"
    SMART_STAND_BY = "smartStandBy"
