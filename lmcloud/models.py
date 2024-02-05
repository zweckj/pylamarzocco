"""Models for La Marzocco API"""

from dataclasses import dataclass
from typing import TypedDict

####################################
#### base iot device specific ######
####################################


@dataclass
class LaMarzoccoFirmware:
    """Class for La Marzocco machine firmware"""

    current_version: str
    latest_version: str


@dataclass
class LaMarzoccoStatistics:
    """Class for La Marzocco machine statistics"""


####################################
###### machine specific ############
####################################
@dataclass
class LaMarzoccoBoiler:
    """Class for La Marzocco boiler"""

    enabled: bool
    current_temperature: float
    target_temperature: float


@dataclass
class LaMarzoccoCoffeeStatistics(LaMarzoccoStatistics):
    """Class for La Marzocco coffee machine statistics"""

    drink_stats: dict[int, int]
    continous: int
    total_flushing: int

    @property
    def total_coffee(self) -> int:
        """Return the total amount of coffee brewed"""
        return sum(self.drink_stats.values())


@dataclass
class LaMarzoccoPrebrewConfiguration:
    """Class for La Marzocco key configuration"""

    on_time: float
    off_time: float

    @property
    def preinfusion_time(self) -> float:
        """Prefinfusion time is off time"""
        return self.off_time


@dataclass
class LaMarzoccoScheduleDay:
    """Class for La Marzocco schedule day"""

    enabled: bool
    h_on: int
    h_off: int
    m_on: int
    m_off: int


@dataclass
class LaMarzoccoSchedule:
    """Class for La Marzocco schedule"""

    enabled: bool
    days: dict[str, LaMarzoccoScheduleDay]


####################################
###### cloud client specific #######
####################################
@dataclass
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
