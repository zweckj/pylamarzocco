"""Models for La Marzocco API"""

from dataclasses import dataclass
from typing import TypedDict
from .const import LaMarzoccoBoilerType, PrebrewMode

####################################
#### base iot device specific ######
####################################


@dataclass(kw_only=True)
class LaMarzoccoFirmware:
    """Class for La Marzocco machine firmware"""

    current_version: str
    latest_version: str


@dataclass(kw_only=True)
class LaMarzoccoStatistics:
    """Class for La Marzocco machine statistics"""


@dataclass(kw_only=True)
class LaMarzoccoDeviceConfig:
    """Class for La Marzocco device configuration"""

    turned_on: bool
    doses: dict[int, float]


####################################
###### machine specific ############
####################################


@dataclass(kw_only=True)
class LaMarzoccoBoiler:
    """Class for La Marzocco boiler"""

    enabled: bool
    current_temperature: float
    target_temperature: float


@dataclass(kw_only=True)
class LaMarzoccoCoffeeStatistics(LaMarzoccoStatistics):
    """Class for La Marzocco coffee machine statistics"""

    drink_stats: dict[int, int]
    continous: int
    total_flushing: int

    @property
    def total_coffee(self) -> int:
        """Return the total amount of coffee brewed"""
        return sum(self.drink_stats.values())


@dataclass(kw_only=True)
class LaMarzoccoPrebrewConfiguration:
    """Class for La Marzocco key configuration"""

    on_time: float
    off_time: float

    @property
    def preinfusion_time(self) -> float:
        """Prefinfusion time is off time"""
        return self.off_time


@dataclass(kw_only=True)
class LaMarzoccoScheduleDay:
    """Class for La Marzocco schedule day"""

    enabled: bool
    h_on: int
    h_off: int
    m_on: int
    m_off: int


@dataclass(kw_only=True)
class LaMarzoccoSchedule:
    """Class for La Marzocco schedule"""

    enabled: bool
    days: dict[str, LaMarzoccoScheduleDay]


@dataclass(kw_only=True)
class LaMarzoccoMachineConfig(LaMarzoccoDeviceConfig):
    """Class for La Marzocco machine configuration"""

    boilers: dict[LaMarzoccoBoilerType, LaMarzoccoBoiler]
    prebrew_mode: PrebrewMode = PrebrewMode.DISABLED
    plumbed_in: bool
    prebrew_configuration: dict[int, LaMarzoccoPrebrewConfiguration]
    dose_hot_water: int | None
    water_contact: bool
    auto_on_off_enabled: bool
    auto_on_off_schedule: LaMarzoccoSchedule
    brew_active: bool
    brew_active_duration: float


####################################
###### cloud client specific #######
####################################
@dataclass(kw_only=True)
class LaMarzoccoMachineInfo:
    """Class for La Marzocco machine information."""

    serial_number: str
    name: str
    communication_key: str
    model_name: str


class LaMarzoccoCloudScheduleDay(TypedDict):
    """Input object to set the schedule"""

    day: str
    enable: bool
    on: str
    off: str


class LaMarzoccoCloudSchedule(TypedDict):
    """Input object to set the schedule"""

    enable: bool
    days: list[LaMarzoccoCloudScheduleDay]


####################################
###### grinder specific ############
####################################
@dataclass(kw_only=True)
class LaMarzoccoGrinderConfig(LaMarzoccoDeviceConfig):
    """Class for La Marzocco grinder configuration"""

    turned_on: bool
    led_enabled: bool
    bell_opened: bool
    stand_by_time: int
