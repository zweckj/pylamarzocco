"""Models for La Marzocco API"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict

from .const import (
    BoilerType,
    PhysicalKey,
    PrebrewMode,
    SmartStandbyMode,
    SteamLevel,
    WeekDay,
)

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
    doses: dict[PhysicalKey, float]


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

    drink_stats: dict[PhysicalKey, int]
    continous: int
    total_flushes: int

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
class LaMarzoccoSmartStandby:
    """Class for La Marzocco smart standby configuration"""

    enabled: bool
    minutes: int
    mode: SmartStandbyMode


@dataclass(kw_only=True)
class LaMarzoccoWakeUpSleepEntry:
    """Class for La Marzocco wake up sleep entry"""

    enabled: bool
    days: list[WeekDay]
    entry_id: str
    steam: bool
    time_on: str
    time_off: str


# @dataclass(kw_only=True)
# class LaMarzoccoScheduleDay:
#     """Class for La Marzocco schedule day"""

#     enabled: bool
#     h_on: int
#     h_off: int
#     m_on: int
#     m_off: int


# @dataclass(kw_only=True)
# class LaMarzoccoSchedule:
#     """Class for La Marzocco schedule"""

#     enabled: bool
#     days: dict[WeekDay, LaMarzoccoScheduleDay]


@dataclass(kw_only=True)
class LaMarzoccoMachineConfig(LaMarzoccoDeviceConfig):
    """Class for La Marzocco machine configuration"""

    boilers: dict[BoilerType, LaMarzoccoBoiler]
    prebrew_mode: PrebrewMode
    plumbed_in: bool
    prebrew_configuration: dict[
        PhysicalKey,
        tuple[LaMarzoccoPrebrewConfiguration, LaMarzoccoPrebrewConfiguration],
    ]
    dose_hot_water: int
    water_contact: bool
    wake_up_sleep_entries: dict[str, LaMarzoccoWakeUpSleepEntry]
    smart_standby: LaMarzoccoSmartStandby
    brew_active: bool
    brew_active_duration: float
    backflush_enabled: bool
    scale: LaMarzoccoScale | None = None
    bbw_settings: LaMarzoccoBrewByWeightSettings | None = None

    @property
    def steam_level(self) -> SteamLevel:
        """Return the steam level"""

        steam_boiler = self.boilers[BoilerType.STEAM]
        return min(SteamLevel, key=lambda x: abs(x - steam_boiler.target_temperature))


####################################
###### cloud client specific #######
####################################
@dataclass(kw_only=True)
class LaMarzoccoDeviceInfo:
    """Class for La Marzocco machine information."""

    serial_number: str
    name: str
    communication_key: str
    model: str


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


@dataclass
class AccessToken:
    """Class for OAuth access token"""

    access_token: str
    expires_in: float
    refresh_token: str


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


####################################
######## brew by weight ############
####################################


@dataclass(kw_only=True)
class LaMarzoccoScale:
    """Class for La Marzocco scale"""

    connected: bool
    name: str
    address: str
    battery: int


@dataclass(kw_only=True)
class LaMarzoccoBrewByWeightSettings:
    """Class for La Marzocco brew by weight settings"""

    doses: dict[PhysicalKey, int]
    active_dose: PhysicalKey
