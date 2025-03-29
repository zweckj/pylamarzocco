"""Models for Bluetooth communication"""

from dataclasses import dataclass, field

from mashumaro import field_options
from mashumaro.mixins.json import DataClassJSONMixin

from pylamarzocco.const import MachineMode, ModelName, BoilerType, SmartStandByType


@dataclass(kw_only=True)
class BluetoothMachineCapabilities(DataClassJSONMixin):
    """Machine capabilities for Bluetooth communication."""

    family: ModelName = field(metadata=field_options(deserialize=ModelName.from_string))
    groups_number: int = field(metadata=field_options(alias="groupsNumber"))
    coffee_boilers_number: int = field(
        metadata=field_options(alias="coffeeBoilersNumber")
    )
    has_cup_warmer: bool = field(metadata=field_options(alias="hasCupWarmer"))
    steam_boilers_number: int = field(
        metadata=field_options(alias="steamBoilersNumber")
    )
    tea_doses_number: int = field(metadata=field_options(alias="teaDosesNumber"))
    machine_modes: list[MachineMode] = field(
        metadata=field_options(alias="machineModes")
    )
    scheduling_type: str = field(metadata=field_options(alias="schedulingType"))


@dataclass(kw_only=True)
class BluetoothBoilerDetails(DataClassJSONMixin):
    """Details for a boiler."""

    id: BoilerType
    is_enabled: bool = field(metadata=field_options(alias="isEnabled"))
    target: int
    current: int

@dataclass(kw_only=True)
class BluetoothSmartStandbyDetails(DataClassJSONMixin):
    """Details for smart standby."""

    mode: SmartStandByType
    minutes: int
    enabled: bool