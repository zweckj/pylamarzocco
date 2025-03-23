"""Models for device configuration."""

from __future__ import annotations
from typing import Annotated, Any

from dataclasses import dataclass, field
from datetime import datetime, timezone

from mashumaro import field_options
from mashumaro.mixins.json import DataClassJSONMixin
from mashumaro.types import Discriminator

from pylamarzocco.models.general import CommandResponse

from pylamarzocco.const import (
    MachineState,
    PreExtractionMode,
    WidgetType,
    SteamTargetLevel,
    DeviceType,
    ModelCode,
    FirmwareType,
)


@dataclass(kw_only=True)
class Device(DataClassJSONMixin):
    """Generic device information t"""

    serial_number: str = field(metadata=field_options(alias="serialNumber"))
    type: DeviceType
    name: str
    location: str | None = field(default=None)
    model_code: ModelCode = field(metadata=field_options(alias="modelCode"))
    model_name: str = field(metadata=field_options(alias="modelName"))
    connected: bool
    connection_date: datetime = field(
        metadata=field_options(
            alias="connectionDate",
            deserialize=lambda ts: datetime.fromtimestamp(ts / 1000, timezone.utc),
        )
    )
    offline_mode: bool = field(metadata=field_options(alias="offlineMode"))
    require_firmware_update: bool = field(
        metadata=field_options(alias="requireFirmwareUpdate"), default=False
    )
    available_firmware_update: bool = field(
        metadata=field_options(alias="availableFirmwareUpdate"), default=False
    )
    coffee_station: dict | None = field(
        metadata=field_options(alias="coffeeStation"), default=None
    )
    image_url: str = field(metadata=field_options(alias="imageUrl"))
    ble_auth_token: str | None = field(
        metadata=field_options(alias="bleAuthToken"), default=None
    )


@dataclass(kw_only=True)
class DashboardConfig(DataClassJSONMixin):
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
    def __post_deserialize__(cls, obj: DashboardConfig) -> DashboardConfig:
        # move the widgets to a dict with type as key for easy access to config
        obj.config = {widget.code: widget.output for widget in obj.widgets}
        return obj

@dataclass(kw_only=True)
class DashboardDeviceConfig(DashboardConfig, Device):
    """Device configuration from API."""


@dataclass(kw_only=True)
class DashboardWSConfig(DashboardConfig):
    """Device configuration from WS."""

    connected: bool
    removed_widgets: list[BaseWidget] = field(
        metadata=field_options(alias="removedWidgets"), default_factory=list
    )
    connection_date: int = field(metadata=field_options(alias="connectionDate"))
    uuid: str
    commands: list[CommandResponse]


@dataclass(kw_only=True)
class BaseWidget(DataClassJSONMixin):
    """Base widget configuration."""

    code: WidgetType
    index: int


@dataclass(kw_only=True)
class Widget(BaseWidget):
    """Widget configuration."""

    output: Annotated[
        BaseWidgetOutput, Discriminator(field="widget_type", include_subtypes=True)
    ]


@dataclass(kw_only=True)
class BaseWidgetOutput(DataClassJSONMixin):
    """Widget configuration."""


@dataclass(kw_only=True)
class MachineStatus(BaseWidgetOutput):
    """Machine status configuration."""

    widget_type = WidgetType.CM_MACHINE_STATUS
    status: MachineState
    available_modes: list[MachineState] = field(
        metadata=field_options(alias="availableModes")
    )
    mode: MachineState
    next_status: MachineState | None = field(metadata=field_options(alias="nextStatus"))
    brewing_start_time: datetime | None = field(
        metadata=field_options(
            alias="brewingStartTime",
            deserialize=lambda ts: datetime.fromtimestamp(ts / 1000, timezone.utc),
        ),
        default=None,
    )


@dataclass(kw_only=True)
class CoffeeBoiler(BaseWidgetOutput):
    """Coffee boiler configuration."""

    widget_type = WidgetType.CM_COFFEE_BOILER
    status: MachineState
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
    status: MachineState  # TODO: correct type
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

    dose_index: str = field(metadata=field_options(alias="doseIndex"))
    seconds: SecondsInOut


@dataclass(kw_only=True)
class PrebrewInfusionTimeLists(DataClassJSONMixin):
    """Prebrew/-infusion configuration."""

    pre_infusion: list[PreExtractionInOutTimes] = field(
        metadata=field_options(alias="PreInfusion")
    )
    pre_brewing: list[PreExtractionInOutTimes] = field(
        metadata=field_options(alias="PreBrewing")
    )


@dataclass(kw_only=True)
class BackFlush(BaseWidgetOutput):
    """Backflush configuration."""

    widget_type = WidgetType.CM_BACK_FLUSH
    status: str
    last_cleaning_start_time: datetime | None = field(
        metadata=field_options(
            alias="lastCleaningStartTime",
            deserialize=lambda ts: datetime.fromtimestamp(ts / 1000, timezone.utc),
        ),
        default=None,
    )


@dataclass(kw_only=True)
class FirmwareSettings(DataClassJSONMixin):
    """Firmware settings configuration."""

    type: FirmwareType
    build_version: str = field(metadata=field_options(alias="buildVersion"))
    change_log: str = field(metadata=field_options(alias="changeLog"))
    thing_model_code: str = field(
        metadata=field_options(alias="thingModelCode")
    )
    status: str
    available_update: dict | None = field(
        metadata=field_options(alias="availableUpdate"), default=None
    )

@dataclass(kw_only=True)
class DeviceSettings(Device):
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
    auto_update: bool = field(
        metadata=field_options(alias="autoUpdate"), default=False
    )