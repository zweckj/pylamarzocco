"""Models for the La Marzocco API."""

from ._authentication import AccessToken, RefreshTokenRequest, SigninTokenRequest
from ._config import (
    BackFlush,
    BaseDoseSettings,
    BrewByWeightDoses,
    BrewByWeightDoseSettings,
    CoffeeBoiler,
    DosePulsesType,
    DoseSettings,
    GroupDosesSettings,
    HotWaterDose,
    InOutTime,
    MachineStatus,
    NextStatus,
    NoWater,
    PreBrewInfusionTime,
    PrebrewInfusionTimeLists,
    PreBrewing,
    PrebrewSettingTimes,
    PreExtraction,
    PreExtractionBase,
    PreExtractionBaseTimes,
    PreExtractionInOutTimes,
    PreExtractionPreBrewInfusionTimes,
    SecondsInOut,
    SteamBoilerLevel,
    SteamBoilerTemperature,
    ThingConfig,
    ThingDashboardConfig,
    ThingDashboardWebsocketConfig,
    ThingScale,
    ThingSettings,
)
from ._general import (
    BaseWidget,
    BaseWidgetOutput,
    CommandResponse,
    Thing,
    WebSocketDetails,
    Widget,
)
from ._schedule import (
    ThingSchedulingSettings,
    SmartWakeUpScheduleWebsocketConfig,
    SmartWakeUpSleepSettings,
    WakeUpScheduleSettings,
)
from ._statistics import (
    CoffeeAndFlushCounter,
    CoffeeAndFlushTrend,
    CoffeeHistoryEvent,
    LastCoffee,
    LastCoffeeList,
    ThingStatistics,
)
from ._update import FirmwareSettings, FirmwareVersion, UpdateDetails

from ._bluetooth import (
    BluetoothBoilerDetails,
    BluetoothMachineCapabilities,
    BluetoothSmartStandbyDetails,
)

__all__ = [
    "AccessToken",
    "BackFlush",
    "BaseDoseSettings",
    "BaseWidget",
    "BaseWidgetOutput",
    "BluetoothBoilerDetails",
    "BluetoothMachineCapabilities",
    "BluetoothSmartStandbyDetails",
    "BrewByWeightDoseSettings",
    "BrewByWeightDoses",
    "CoffeeAndFlushCounter",
    "CoffeeAndFlushTrend",
    "CoffeeBoiler",
    "CoffeeHistoryEvent",
    "CommandResponse",
    "ThingConfig",
    "ThingDashboardConfig",
    "ThingDashboardWebsocketConfig",
    "DosePulsesType",
    "DoseSettings",
    "FirmwareSettings",
    "FirmwareVersion",
    "GroupDosesSettings",
    "HotWaterDose",
    "InOutTime",
    "LastCoffee",
    "LastCoffeeList",
    "MachineStatus",
    "NoWater",
    "NextStatus",
    "PreBrewInfusionTime",
    "PreBrewing",
    "PreExtraction",
    "PreExtractionBase",
    "PreExtractionBaseTimes",
    "PreExtractionInOutTimes",
    "PreExtractionPreBrewInfusionTimes",
    "PrebrewInfusionTimeLists",
    "PrebrewSettingTimes",
    "RefreshTokenRequest",
    "ThingSchedulingSettings",
    "SecondsInOut",
    "SigninTokenRequest",
    "SmartWakeUpScheduleWebsocketConfig",
    "SmartWakeUpSleepSettings",
    "SteamBoilerLevel",
    "SteamBoilerTemperature",
    "Thing",
    "ThingScale",
    "ThingSettings",
    "ThingStatistics",
    "UpdateDetails",
    "WakeUpScheduleSettings",
    "WebSocketDetails",
    "Widget",
]
