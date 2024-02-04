""" Helper functions for lmcloud. """

from typing import Any

from .const import LaMarzoccoBoilerType, PrebrewMode, WeekDay
from .lm_cloud import LaMarzoccoCloudSchedule
from .lm_machine import (LaMarzoccoBoiler, LaMarzoccoCoffeeStatistics,
                         LaMarzoccoPrebrewConfiguration, LaMarzoccoSchedule,
                         LaMarzoccoScheduleDay)


def schedule_to_request(schedule: LaMarzoccoSchedule) -> LaMarzoccoCloudSchedule:
    """convert schedule to API expected input format"""

    schedule_conv: LaMarzoccoCloudSchedule = {
        "enable": schedule.enabled,
        "days": [],
    }
    for day, schedule_day in schedule.days.items():
        # requests wants 00:00, response gives 24:00
        h_on = "00" if schedule_day.h_on == 24 else str(schedule_day.h_on).zfill(2)
        h_off = "00" if schedule_day.h_off == 24 else str(schedule_day.h_off).zfill(2)

        hh_mm_on = h_on + ":" + str(schedule_day.m_on).zfill(2)
        hh_mm_off = h_off + ":" + str(schedule_day.m_off).zfill(2)

        schedule_conv["days"].append(
            {
                "day": str.upper(day),
                "enable": schedule_day.enabled,
                "on": hh_mm_on,
                "off": hh_mm_off,
            }
        )
    return schedule_conv


def parse_schedule(schedule: dict[str, Any]) -> LaMarzoccoSchedule:
    """Parse schedule from API config object."""
    global_enable: bool = schedule["enabled"]
    days: dict[str, LaMarzoccoScheduleDay] = {}
    for weekday in WeekDay:
        day_settings = schedule[weekday]
        days[weekday] = LaMarzoccoScheduleDay(
            enabled=day_settings["enabled"],
            h_on=day_settings["h_on"],
            h_off=day_settings["h_off"],
            m_on=day_settings["m_on"],
            m_off=day_settings["m_off"],
        )
    return LaMarzoccoSchedule(enabled=global_enable, days=days)


def parse_boilers(
    boilers: list[dict[str, Any]]
) -> tuple[LaMarzoccoBoiler, LaMarzoccoBoiler]:
    """Parse boiler settings from API config object."""
    coffee_boiler = LaMarzoccoBoiler(False, 0, 0)
    steam_boiler = LaMarzoccoBoiler(False, 0, 0)
    for boiler in boilers:
        is_enabled = boiler["isEnabled"] == "Enabled"
        current_temp = boiler["current"]
        target_temp = boiler["target"]
        if boiler["id"] == LaMarzoccoBoilerType.COFFEE:
            coffee_boiler = LaMarzoccoBoiler(
                enabled=is_enabled,
                current_temperature=current_temp,
                target_temperature=target_temp,
            )
        elif boiler["id"] == LaMarzoccoBoilerType.STEAM:
            steam_boiler = LaMarzoccoBoiler(
                enabled=is_enabled,
                current_temperature=current_temp,
                target_temperature=target_temp,
            )

    return coffee_boiler, steam_boiler


def parse_preinfusion_settings(
    config: dict[str, Any]
) -> tuple[PrebrewMode, dict[int, LaMarzoccoPrebrewConfiguration]]:
    """Parse preinfusion settings from API config object."""
    parsed: dict[int, LaMarzoccoPrebrewConfiguration] = {}
    i = 1
    preinfusion_settings = config.get("preinfusionSettings", {})
    mode = PrebrewMode(preinfusion_settings.get("mode", "Disabled"))
    for group in preinfusion_settings.get("Group1", {}):
        parsed[i] = LaMarzoccoPrebrewConfiguration(
            on_time=group.get("preWetTime", 0),
            off_time=group.get("preWetHoldTime", 0),
        )

    return mode, parsed


def parse_coffee_doses(config: dict[str, Any]) -> tuple[dict[int, int], int | None]:
    """Parse doses from API config object."""
    parsed: dict[int, int] = {}
    i = 1
    group_capabilities = config.get("groupCapabilities", [])
    if len(group_capabilities) == 0:
        return parsed, None

    for dose in group_capabilities[0].get("doses", []):
        parsed[i] = dose.get("stopTarget", 0)
        i += 1
    dose_hot_water = config.get("teaDoses", {}).get("DoseA", {}).get("stopTarget", 0)
    return parsed, dose_hot_water


def parse_cloud_statistics(
    statistics: list[dict[str, Any]]
) -> LaMarzoccoCoffeeStatistics:
    """Parse statistics from API statistics object."""

    drink_stats: dict[int, int] = {}
    for stat in statistics:
        coffee_type: int = stat["coffeeType"]
        count: int = stat["count"]
        if 0 <= coffee_type < 4:
            drink_stats[coffee_type + 1] = count
        elif coffee_type == 4:
            continuous = count
        elif coffee_type == -1:
            total_flushing = count
    return LaMarzoccoCoffeeStatistics(drink_stats, continuous, total_flushing)


def parse_webhook_statistics(statistics: dict[str, Any]) -> LaMarzoccoCoffeeStatistics:
    """Parse statistics from webhook statistics object."""
    group = statistics["groups"][0]
    doses = group["doses"]
    drink_stats: dict[int, int] = {}
    for dose in doses:
        key: str = next(iter(dose))
        if key.startswith("Dose"):
            drink_stats[ord(key[-1]) - 64] = dose[key]
        elif key == "ContinuousDose":
            continuous = dose[key]
    total_flushing = group["clean"]
    return LaMarzoccoCoffeeStatistics(drink_stats, continuous, total_flushing)
