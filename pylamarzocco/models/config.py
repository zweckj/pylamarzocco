"""Models for device configuration."""

from __future__ import annotations

from dataclasses import dataclass, field

from mashumaro import field_options
from mashumaro.mixins.json import DataClassJSONMixin

from pylamarzocco.models.general import CommandResponse

from pylamarzocco.const import MachineState


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


@dataclass(kw_only=True)
class BaseWidget(DataClassJSONMixin):
    """Base widget configuration."""

    code: str
    index: int

@dataclass(kw_only=True)
class WidgetBaseOutput(DataClassJSONMixin):
    """Widget configuration."""

@dataclass(kw_only=True)
class Widget(BaseWidget):
    """Widget configuration."""

    output: WidgetBaseOutput

@dataclass(kw_only=True)
class CMMachineStatusOutput(WidgetBaseOutput):
    """Machine status configuration."""
    status: MachineState
    available_modes: list[MachineState] = field(metadata=field_options(alias="availableModes"))
    mode: MachineState
    next_state: MachineState | None = field(metadata=field_options(alias="nextState"))
    brewing_start_time: int | None = field(metadata=field_options(alias="brewingStartTime"), default=None)

@dataclass(kw_only=True)
class CMCoffeeBoilerOutput(WidgetBaseOutput):
    """Coffee boiler configuration."""
    status: MachineState
    enabled: bool
    enabled_supported: bool = field(metadata=field_options(alias="enabledSupported"))
    target_temperature: float = field(metadata=field_options(alias="targetTemperature"))
    target_temperature_min: int = field(metadata=field_options(alias="targetTemperatureMin"))
    target_temperature_max: int = field(metadata=field_options(alias="targetTemperatureMax"))
    target_temperature_step: float = field(metadata=field_options(alias="targetTemperatureStep"))
    ready_start_time: int | None = field(metadata=field_options(alias="readyStartTime"), default=None)