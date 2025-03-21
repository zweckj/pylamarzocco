"""Models for device configuration."""

from __future__ import annotations
from typing import Annotated

from dataclasses import dataclass, field
from datetime import datetime, timezone

from mashumaro import field_options
from mashumaro.mixins.json import DataClassJSONMixin
from mashumaro.types import Discriminator

from pylamarzocco.models.general import CommandResponse

from pylamarzocco.const import MachineState, PreExtractionMode, WidgetType, SteamTargetLevel

@dataclass(kw_only=True)
class DeviceConfig(DataClassJSONMixin):
    """Device configuration."""

    connected: bool
    removed_widgets: list[BaseWidget] = field(
        metadata=field_options(alias="removedWidgets"), default_factory=list
    )
    connection_date: int = field(metadata=field_options(alias="connectionDate"))
    widgets: list[Widget] = field(default_factory=list)
    uuid: str
    commands: list[CommandResponse]

    @classmethod
    def __pre_deserialize__(cls, d: dict) -> dict:
        widgets: dict = d["widgets"]
        for widget in widgets:
            widget["output"]["widget_type"] = widget["code"]
        d["widgets"] = widgets
        return d


@dataclass(kw_only=True)
class BaseWidget(DataClassJSONMixin):
    """Base widget configuration."""

    code: str
    index: int


@dataclass(kw_only=True)
class Widget(BaseWidget):
    """Widget configuration."""

    output: Annotated[BaseWidgetOutput, Discriminator(field="widget_type", include_subtypes=True)]

@dataclass(kw_only=True)
class BaseWidgetOutput(DataClassJSONMixin):
    """Widget configuration."""

@dataclass(kw_only=True)
class MachineStatus(BaseWidgetOutput):
    """Machine status configuration."""

    widget_type = WidgetType.MACHINE_STATUS
    status: MachineState
    available_modes: list[MachineState] = field(
        metadata=field_options(alias="availableModes")
    )
    mode: MachineState
    next_status: MachineState | None = field(metadata=field_options(alias="nextStatus"))
    brewing_start_time: datetime | None = field(
        metadata=field_options(
            alias="brewingStartTime",
            serialize=lambda ts: datetime.fromtimestamp(ts, timezone.utc),
        ),
        default=None,
    )


@dataclass(kw_only=True)
class CoffeeBoiler(BaseWidgetOutput):
    """Coffee boiler configuration."""

    widget_type = WidgetType.COFFEE_BOILER
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
            serialize=lambda ts: datetime.fromtimestamp(ts, timezone.utc),
        ),
        default=None,
    )

@dataclass(kw_only=True)
class SteamBoilerLevel(BaseWidgetOutput):
    """Steam boiler level configuration."""
    widget_type = WidgetType.STEAM_BOILER_LEVEL
    status: MachineState # TODO: correct type
    enabled: bool
    enabled_supported: bool = field(metadata=field_options(alias="enabledSupported"))
    target_level: SteamTargetLevel = field(metadata=field_options(alias="targetLevel"))
    target_level_supported: bool = field(
        metadata=field_options(alias="targetLevelSupported")
    )
    ready_start_time: datetime | None = field(
        metadata=field_options(
            alias="readyStartTime",
            serialize=lambda ts: datetime.fromtimestamp(ts, timezone.utc),
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
    widget_type = WidgetType.PRE_EXTRACTION
    times: InOutTime

@dataclass(kw_only=True)
class PreBrewing(PreExtractionBase):
    """Pre-brewing configuration."""

    widget_type = WidgetType.PRE_BREWING
    times: PrebrewInfusionTimeLists
    dose_index_supported: bool = field(metadata=field_options(alias="doseIndexSupported"), default=False)

@dataclass(kw_only=True)
class InOutTime(DataClassJSONMixin):
    """In and out time configuration."""

    time_in: PreExtractionPreBrewInfusionTimes = field(metadata=field_options(alias="In"))
    time_out: PreExtractionPreBrewInfusionTimes = field(metadata=field_options(alias="Out"))

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
    seconds_min: T = field(
        metadata=field_options(alias="secondsMin")
    )
    seconds_max: T = field(
        metadata=field_options(alias="secondsMax")
    )
    seconds_step: T = field(
        metadata=field_options(alias="secondsStep")
    )   


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
    pre_infusion: list[PreExtractionInOutTimes] = field(metadata=field_options(alias="PreInfusion"))
    pre_brewing: list[PreExtractionInOutTimes] = field(metadata=field_options(alias="PreBrewing"))

@dataclass(kw_only=True)
class BackFlush(BaseWidgetOutput):
    """Backflush configuration."""
    widget_type = WidgetType.BACK_FLUSH
    status: str
    last_cleaning_start_time: datetime | None = field(
        metadata=field_options(
            alias="lastCleaningStartTime",
            serialize=lambda ts: datetime.fromtimestamp(ts, timezone.utc),
        ),
        default=None,
    )