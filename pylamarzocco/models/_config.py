"""Models for device configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from mashumaro import field_options
from mashumaro.config import BaseConfig
from mashumaro.mixins.json import DataClassJSONMixin

from pylamarzocco.const import (
    BackFlushStatus,
    BoilerStatus,
    DoseIndex,
    DoseIndexType,
    DoseMode,
    FirmwareType,
    MachineMode,
    MachineState,
    PreExtractionMode,
    SteamTargetLevel,
    WidgetType,
)

from ._general import (
    BaseWidget,
    BaseWidgetOutput,
    CommandResponse,
    Thing,
    Widget,
)

from ._update import FirmwareSettings


@dataclass(kw_only=True)
class ThingConfig(DataClassJSONMixin):
    """Dashboard config with widgets."""

    widgets: list[Widget] = field(default_factory=list)
    config: dict[WidgetType, BaseWidgetOutput] = field(default_factory=dict)

    @classmethod
    def __pre_deserialize__(cls, d: dict[str, Any]) -> dict[str, Any]:
        # move code to widget_type for mashumaro annotated serialization
        widgets = d["widgets"]
        for widget in widgets:
            widget["output"]["widget_type"] = widget["code"]
        d["widgets"] = widgets
        return d

    @classmethod
    def __post_deserialize__(cls, obj: ThingConfig) -> ThingConfig:
        # move the widgets to a dict with type as key for easy access to config
        obj.config = {widget.code: widget.output for widget in obj.widgets}
        return obj


@dataclass(kw_only=True)
class ThingDashboardConfig(ThingConfig, Thing):
    """Device configuration from API."""


@dataclass(kw_only=True)
class ThingDashboardWebsocketConfig(ThingConfig):
    """Device configuration from WS."""

    connected: bool
    removed_widgets: list[BaseWidget] = field(
        metadata=field_options(alias="removedWidgets"), default_factory=list
    )
    connection_date: int = field(metadata=field_options(alias="connectionDate"))
    uuid: str
    commands: list[CommandResponse]


@dataclass(kw_only=True)
class MachineStatus(BaseWidgetOutput):
    """Machine status configuration."""

    widget_type = WidgetType.CM_MACHINE_STATUS
    status: MachineState
    available_modes: list[MachineMode] = field(
        metadata=field_options(alias="availableModes")
    )
    mode: MachineMode
    next_status: NextStatus | None = field(metadata=field_options(alias="nextStatus"))
    brewing_start_time: datetime | None = field(
        metadata=field_options(
            alias="brewingStartTime",
            deserialize=lambda ts: datetime.fromtimestamp(ts / 1000, timezone.utc),
        ),
        default=None,
    )


@dataclass(kw_only=True)
class NextStatus(DataClassJSONMixin):
    """Next status configuration."""

    status: MachineState
    start_time: datetime = field(
        metadata=field_options(
            alias="startTime",
            deserialize=lambda ts: datetime.fromtimestamp(ts / 1000, timezone.utc),
        )
    )


@dataclass(kw_only=True)
class CoffeeBoiler(BaseWidgetOutput):
    """Coffee boiler configuration."""

    widget_type = WidgetType.CM_COFFEE_BOILER
    status: BoilerStatus
    enabled: bool
    enabled_supported: bool = field(metadata=field_options(alias="enabledSupported"))
    target_temperature: float = field(metadata=field_options(alias="targetTemperature"))
    target_temperature_min: int = field(
        metadata=field_options(alias="targetTemperatureMin")
    )
    target_temperature_max: int = field(
        metadata=field_options(alias="targetTemperatureMax")
    )
    target_temperature_step: float = field(
        metadata=field_options(alias="targetTemperatureStep")
    )
    ready_start_time: datetime | None = field(
        metadata=field_options(
            alias="readyStartTime",
            deserialize=lambda ts: datetime.fromtimestamp(ts / 1000, timezone.utc),
        ),
        default=None,
    )


@dataclass(kw_only=True)
class SteamBoilerLevel(BaseWidgetOutput):
    """Steam boiler level configuration."""

    widget_type = WidgetType.CM_STEAM_BOILER_LEVEL
    status: BoilerStatus
    enabled: bool
    enabled_supported: bool = field(metadata=field_options(alias="enabledSupported"))
    target_level: SteamTargetLevel = field(metadata=field_options(alias="targetLevel"))
    target_level_supported: bool = field(
        metadata=field_options(alias="targetLevelSupported")
    )
    ready_start_time: datetime | None = field(
        metadata=field_options(
            alias="readyStartTime",
            deserialize=lambda ts: datetime.fromtimestamp(ts / 1000, timezone.utc),
        ),
        default=None,
    )


@dataclass(kw_only=True)
class SteamBoilerTemperature(CoffeeBoiler):
    """Steam boiler temperature configuration."""

    widget_type = WidgetType.CM_STEAM_BOILER_TEMPERATURE
    target_temperature_supported: bool = field(
        metadata=field_options(alias="targetTemperatureSupported")
    )


@dataclass(kw_only=True)
class PreExtractionBase(BaseWidgetOutput):
    """Pre-extraction configuration."""

    available_modes: list[PreExtractionMode] = field(
        metadata=field_options(alias="availableModes")
    )
    mode: PreExtractionMode


@dataclass(kw_only=True)
class PreExtraction(PreExtractionBase):
    """Pre-extraction configuration."""

    widget_type = WidgetType.CM_PRE_EXTRACTION
    times: InOutTime


@dataclass(kw_only=True)
class PreBrewing(PreExtractionBase):
    """Pre-brewing configuration."""

    widget_type = WidgetType.CM_PRE_BREWING
    times: PrebrewInfusionTimeLists
    dose_index_supported: bool = field(
        metadata=field_options(alias="doseIndexSupported"), default=False
    )


@dataclass(kw_only=True)
class InOutTime(DataClassJSONMixin):
    """In and out time configuration."""

    time_in: PreExtractionPreBrewInfusionTimes = field(
        metadata=field_options(alias="In")
    )
    time_out: PreExtractionPreBrewInfusionTimes = field(
        metadata=field_options(alias="Out")
    )


@dataclass(kw_only=True)
class SecondsInOut(DataClassJSONMixin):
    """Seconds in and out configuration."""

    seconds_in: float = field(metadata=field_options(alias="In"))
    seconds_out: float = field(metadata=field_options(alias="Out"))

    class Config(BaseConfig):
        """Config for Mashumaro serialization."""

        serialize_by_alias = True


@dataclass(kw_only=True)
class PreBrewInfusionTime(DataClassJSONMixin):
    """Prebrew/-infusion configuration."""

    pre_infusion: float = field(metadata=field_options(alias="PreInfusion"))
    pre_brewing: float = field(metadata=field_options(alias="PreBrewing"))


@dataclass(kw_only=True)
class PreExtractionBaseTimes[T](DataClassJSONMixin):
    """Pre-extraction times configuration."""

    seconds_min: T = field(metadata=field_options(alias="secondsMin"))
    seconds_max: T = field(metadata=field_options(alias="secondsMax"))
    seconds_step: T = field(metadata=field_options(alias="secondsStep"))


@dataclass(kw_only=True)
class PreExtractionPreBrewInfusionTimes(PreExtractionBaseTimes[PreBrewInfusionTime]):
    """Pre-extraction times configuration."""

    seconds: float


@dataclass(kw_only=True)
class PreExtractionInOutTimes(PreExtractionBaseTimes[SecondsInOut]):
    """Pre-extraction times configuration."""

    dose_index: DoseIndex = field(metadata=field_options(alias="doseIndex"))
    seconds: SecondsInOut


@dataclass(kw_only=True)
class PrebrewInfusionTimeLists(DataClassJSONMixin):
    """Prebrew/-infusion configuration."""

    pre_infusion: list[PreExtractionInOutTimes] = field(
        metadata=field_options(alias="PreInfusion"), default_factory=list
    )
    pre_brewing: list[PreExtractionInOutTimes] = field(
        metadata=field_options(alias="PreBrewing"), default_factory=list
    )


@dataclass(kw_only=True)
class BackFlush(BaseWidgetOutput):
    """Backflush configuration."""

    widget_type = WidgetType.CM_BACK_FLUSH
    status: BackFlushStatus
    last_cleaning_start_time: datetime | None = field(
        metadata=field_options(
            alias="lastCleaningStartTime",
            deserialize=lambda ts: datetime.fromtimestamp(ts / 1000, timezone.utc),
        ),
        default=None,
    )


@dataclass(kw_only=True)
class RinseFlush(BaseWidgetOutput):
    """Rinse flush configuration."""

    widget_type = WidgetType.CM_RINSE_FLUSH
    enabled: bool
    enabled_supported: bool = field(metadata=field_options(alias="enabledSupported"))
    time_seconds: float = field(metadata=field_options(alias="timeSeconds"))
    time_seconds_min: int = field(metadata=field_options(alias="timeSecondsMin"))
    time_seconds_max: int = field(metadata=field_options(alias="timeSecondsMax"))
    time_seconds_step: int = field(metadata=field_options(alias="timeSecondsStep"))


@dataclass(kw_only=True)
class ThingSettings(Thing):
    """Device settings configuration."""

    actual_firmwares: list[FirmwareSettings] = field(
        metadata=field_options(alias="actualFirmwares"), default_factory=list
    )
    wifi_ssid: str | None = field(
        metadata=field_options(alias="wifiSsid"), default=None
    )
    wifi_rssi: int | None = field(
        metadata=field_options(alias="wifiRssi"), default=None
    )
    plumb_in_supported: bool = field(
        metadata=field_options(alias="plumbInSupported"), default=False
    )
    is_plumbed_in: bool = field(
        metadata=field_options(alias="isPlumbedIn"), default=False
    )
    cropster_supported: bool = field(
        metadata=field_options(alias="cropsterSupported"), default=False
    )
    cropster_active: bool = field(
        metadata=field_options(alias="cropsterActive"), default=False
    )
    hemro_supported: bool = field(
        metadata=field_options(alias="hemroSupported"), default=False
    )
    hemro_active: bool = field(
        metadata=field_options(alias="hemroActive"), default=False
    )
    factory_reset_supported: bool = field(
        metadata=field_options(alias="factoryResetSupported"), default=False
    )
    auto_update_supported: bool = field(
        metadata=field_options(alias="autoUpdateSupported"), default=False
    )
    auto_update: bool = field(metadata=field_options(alias="autoUpdate"), default=False)
    firmwares: dict[FirmwareType, FirmwareSettings] = field(default_factory=dict)

    @classmethod
    def __post_deserialize__(cls, obj: ThingSettings) -> ThingSettings:
        # move the firmware to a dict with type as key
        obj.firmwares = {firmware.type: firmware for firmware in obj.actual_firmwares}
        return obj


@dataclass(kw_only=True)
class PrebrewSettingTimes(DataClassJSONMixin):
    """Prebrew/-infusion configuration."""

    times: SecondsInOut
    group_index: int = field(metadata=field_options(alias="groupIndex"), default=1)
    dose_index: DoseIndexType = field(
        metadata=field_options(alias="doseIndex"), default=DoseIndexType.BY_GROUP
    )

    def __pre_serialize__(self) -> PrebrewSettingTimes:
        self.times.seconds_in = round(self.times.seconds_in, 1)
        self.times.seconds_out = round(self.times.seconds_out, 1)
        return self

    class Config(BaseConfig):
        """Config for Mashumaro serialization."""

        serialize_by_alias = True


@dataclass(kw_only=True)
class GroupDosesSettings(BaseWidgetOutput):
    """Group doses configuration."""

    widget_type = WidgetType.CM_GROUP_DOSES
    mirror_with_group_1_supported: bool = field(
        metadata=field_options(alias="mirrorWithGroup1Supported"), default=False
    )
    mirror_with_group_1: str | None = field(
        metadata=field_options(alias="mirrorWithGroup1"), default=None
    )
    mirror_with_group_1_not_effective: bool = field(
        metadata=field_options(alias="mirrorWithGroup1NotEffective"), default=False
    )
    available_modes: list[DoseMode] = field(
        metadata=field_options(alias="availableModes"), default_factory=list
    )
    mode: DoseMode = field(default=DoseMode.PULSES_TYPE)
    profile: str | None = field(default=None)
    doses: DosePulsesType
    continuous_dose_supported: bool = field(
        metadata=field_options(alias="continuousDoseSupported"), default=False
    )
    continuous_dose: str | None = field(
        metadata=field_options(alias="continuousDose"), default=None
    )
    brewing_pressure_supported: bool = field(
        metadata=field_options(alias="brewingPressureSupported"), default=False
    )
    brewing_pressure: str | None = field(
        metadata=field_options(alias="brewingPressure"), default=None
    )


@dataclass(kw_only=True)
class DosePulsesType(DataClassJSONMixin):
    """Dose pulses type configuration."""

    pulses_type: list[DoseSettings] = field(
        metadata=field_options(alias="PulsesType"), default_factory=list
    )


@dataclass(kw_only=True)
class BaseDoseSettings(DataClassJSONMixin):
    """Base dose settings"""

    dose: float
    dose_min: float = field(metadata=field_options(alias="doseMin"))
    dose_max: float = field(metadata=field_options(alias="doseMax"))
    dose_step: int = field(metadata=field_options(alias="doseStep"))


@dataclass(kw_only=True)
class DoseSettings(BaseDoseSettings):
    """Dose configuration."""

    dose_index: DoseIndex = field(metadata=field_options(alias="doseIndex"))


@dataclass(kw_only=True)
class HotWaterDose(BaseWidgetOutput):
    """Settings for hot water."""

    widget_type = WidgetType.CM_HOT_WATER_DOSE
    enabled: bool
    enabled_supported: bool = field(metadata=field_options(alias="enabledSupported"))
    doses: list[DoseSettings] = field(default_factory=list)


@dataclass(kw_only=True)
class BrewByWeightDoses(BaseWidgetOutput):
    """Settings for brew by weight."""

    widget_type = WidgetType.CM_BREW_BY_WEIGHT_DOSES
    scale_connected: bool = field(
        metadata=field_options(alias="scaleConnected"), default=False
    )
    available_modes: list[DoseMode] = field(
        metadata=field_options(alias="availableModes"), default_factory=list
    )
    mode: DoseMode
    doses: BrewByWeightDoseSettings


@dataclass(kw_only=True)
class BrewByWeightDoseSettings(DataClassJSONMixin):
    """Brew by weight doses."""

    dose_1: BaseDoseSettings = field(metadata=field_options(alias="Dose1"))
    dose_2: BaseDoseSettings = field(metadata=field_options(alias="Dose2"))


@dataclass(kw_only=True)
class ThingScale(BaseWidgetOutput):
    """Settings for ThingScale."""

    widget_type = WidgetType.THING_SCALE

    name: str
    connected: bool
    battery_level: float = field(metadata=field_options(alias="batteryLevel"))
    calibration_required: bool = field(
        metadata=field_options(alias="calibrationRequired")
    )


@dataclass(kw_only=True)
class NoWater(BaseWidgetOutput):
    """No water status."""

    widget_type = WidgetType.CM_NO_WATER
    allarm: bool
