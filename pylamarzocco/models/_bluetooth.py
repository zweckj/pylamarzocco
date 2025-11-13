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


@dataclass(kw_only=True)
class MachineStatusSnapshot:
    """Minimal snapshot of machine status and settings available from both Cloud and Bluetooth.
    
    This dataclass contains only the essential information that can be retrieved
    through both the Cloud API (get_dashboard) and Bluetooth, providing a unified
    and simplified view of machine state.
    
    Note: Only includes attributes available through BOTH implementations to ensure
    consistency regardless of data source.
    """

    # Power state - simplified from MachineMode (BrewingMode = True, StandBy/EcoMode = False)
    power_on: bool
    
    # Boiler information (only target temperature, not current, as dashboard doesn't provide current)
    coffee_boiler_enabled: bool
    coffee_target_temperature: float
    
    steam_boiler_enabled: bool
    steam_target_temperature: float
    
    # Tank status - True means water is available, False means no water
    water_reservoir_contact: bool