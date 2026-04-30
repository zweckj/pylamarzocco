"""Models for scheduling."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from mashumaro import field_options
from mashumaro.config import BaseConfig
from mashumaro.mixins.json import DataClassJSONMixin

from pylamarzocco.const import SmartStandByType, WeekDay

from ._general import CommandResponse, Thing


@dataclass(kw_only=True)
class WakeUpScheduleSettings(DataClassJSONMixin):
    """Wake up schedule settings."""

    identifier: str | None = field(metadata=field_options(alias="id"), default=None)
    enabled: bool = field(default=False)
    on_time_minutes: int = field(metadata=field_options(alias="onTimeMinutes"))
    off_time_minutes: int = field(metadata=field_options(alias="offTimeMinutes"))
    steam_boiler: bool = field(metadata=field_options(alias="steamBoiler"))
    days: list[WeekDay] = field(default_factory=list)

    class Config(BaseConfig):
        """Config for Mashumaro serialization."""

        serialize_by_alias = True
        omit_none = True


@dataclass(kw_only=True)
class SmartWakeUpSleepSettings(DataClassJSONMixin):
    """Smart wake up sleep settings."""

    smart_stand_by_enabled: bool = field(
        metadata=field_options(alias="smartStandByEnabled"),
        default=False,
    )
    smart_stand_by_minutes: int = field(
        metadata=field_options(alias="smartStandByMinutes"),
        default=0,
    )
    smart_stand_by_minutes_min: int = field(
        metadata=field_options(alias="smartStandByMinutesMin"),
        default=0,
    )
    smart_stand_by_minutes_max: int = field(
        metadata=field_options(alias="smartStandByMinutesMax"),
        default=0,
    )
    smart_stand_by_minutes_step: int = field(
        metadata=field_options(alias="smartStandByMinutesStep"),
        default=0,
    )
    smart_stand_by_after: SmartStandByType = field(
        metadata=field_options(alias="smartStandByAfter"),
        default=SmartStandByType.POWER_ON,
    )
    schedules: list[WakeUpScheduleSettings] = field(
        default_factory=list,
    )
    schedules_dict: dict[str, WakeUpScheduleSettings] = field(
        default_factory=dict,
    )

    @classmethod
    def __post_deserialize__(cls, obj: SmartWakeUpSleepSettings) -> SmartWakeUpSleepSettings:
        # move the firmware to a dict with type as key
        obj.schedules_dict = {schedule.identifier: schedule for schedule in obj.schedules if schedule.identifier}
        return obj



@dataclass(kw_only=True)
class SmartStandBy(DataClassJSONMixin):
    """Smart standby settings (top level)."""

    enabled: bool = False
    minutes: int = 0
    minutes_min: int = field(metadata=field_options(alias="minutesMin"), default=0)
    minutes_max: int = field(metadata=field_options(alias="minutesMax"), default=0)
    minutes_step: int = field(metadata=field_options(alias="minutesStep"), default=0)
    after: SmartStandByType = field(default=SmartStandByType.POWER_ON)


@dataclass(kw_only=True)
class ThingSchedulingSettings(Thing):
    """Scheduling settings."""

    smart_stand_by_supported: bool = field(
        metadata=field_options(alias="smartStandBySupported"),
        default=False,
    )
    smart_stand_by: SmartStandBy | None = field(
        metadata=field_options(alias="smartStandBy"),
        default=None,
    )
    smart_wake_up_sleep_supported: bool = field(
        metadata=field_options(alias="smartWakeUpSleepSupported"),
        default=True,
    )
    smart_wake_up_sleep: SmartWakeUpSleepSettings = field(
        metadata=field_options(alias="smartWakeUpSleep"),
        default_factory=SmartWakeUpSleepSettings,
    )
    auto_stand_by: str | None = field(
        metadata=field_options(alias="autoStandBy"),
        default=None,
    )
    auto_stand_by_supported: bool = field(
        metadata=field_options(alias="autoStandBySupported"),
        default=False,
    )
    auto_on_off: str | None = field(
        metadata=field_options(alias="autoOnOff"),
        default=None,
    )
    auto_on_off_supported: bool = field(
        metadata=field_options(alias="autoOnOffSupported"),
        default=False,
    )
