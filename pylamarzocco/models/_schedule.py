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
class ThingSchedulingSettings(Thing):
    """Scheduling settings."""

    smart_wake_up_sleep_supported: bool = field(
        metadata=field_options(alias="smartWakeUpSleepSupported")
    )
    smart_wake_up_sleep: SmartWakeUpSleepSettings | None = field(
        metadata=field_options(alias="smartWakeUpSleep"),
        default=None,
    )


@dataclass(kw_only=True)
class SmartWakeUpSleepSettings(DataClassJSONMixin):
    """Smart wake up sleep settings."""

    smart_stand_by_enabled: bool = field(
        metadata=field_options(alias="smartStandByEnabled")
    )
    smart_stand_by_minutes: int = field(
        metadata=field_options(alias="smartStandByMinutes")
    )
    smart_stand_by_minutes_min: int = field(
        metadata=field_options(alias="smartStandByMinutesMin")
    )
    smart_stand_by_minutes_max: int = field(
        metadata=field_options(alias="smartStandByMinutesMax")
    )
    smart_stand_by_minutes_step: int = field(
        metadata=field_options(alias="smartStandByMinutesStep")
    )
    smart_stand_by_after: SmartStandByType = field(
        metadata=field_options(alias="smartStandByAfter")
    )
    schedules: list[WakeUpScheduleSettings] = field(
        default_factory=list,
    )


# ws SUBSCRIBE /ws/sn/SERIAL/scheduling
@dataclass(kw_only=True)
class SmartWakeUpScheduleWebsocketConfig(DataClassJSONMixin):
    """Smart wake up schedule settings from websocket."""

    connected: bool
    auto_stand_by: str | None = field(
        metadata=field_options(alias="autoStandBy"),
        default=None,
    )
    auto_on_off: str | None = field(
        metadata=field_options(alias="autoOnOff"),
        default=None,
    )
    connection_date: datetime | None = field(
        metadata=field_options(
            alias="connectionDate",
            deserialize=lambda ts: datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
            if ts
            else None,
        ),
        default=None,
    )
    auto_stand_by_supported: bool = field(
        metadata=field_options(alias="autoStandBySupported")
    )
    auto_on_off_supported: bool = field(
        metadata=field_options(alias="autoOnOffSupported")
    )
    smart_wake_up_sleep: SmartWakeUpSleepSettings | None = field(
        metadata=field_options(alias="smartWakeUpSleep"),
        default=None,
    )
    weekly_supported: bool = field(metadata=field_options(alias="weeklySupported"))
    smart_wake_up_sleep_supported: bool = field(
        metadata=field_options(alias="smartWakeUpSleepSupported")
    )
    commands: list[CommandResponse] = field(
        default_factory=list,
    )
