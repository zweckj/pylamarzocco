# La Marzocco Cloud Command Reference

Reference of `CustomerAppThingCommandType` values and their request payloads.

Each command is sent as `POST /things/{serial}/command/{commandString}` with the
listed JSON body (payload fields are at the top level of the body).

## Strada X (`STRADAX`)

Cloud commands this change adds for the Strada X machine.

| Command string | Payload | Library method |
|---|---|---|
| `CoffeeMachineChangeMode` | `{mode: string}` | `set_mode` |
| `CoffeeMachineGroupChangeMode` | `{groupIndex: int, mode: string}` | `set_group_mode` |
| `CoffeeMachineSettingCoffeeBoilerEnabled` | `{boilerIndex: int, enabled: bool}` | `set_coffee_boiler` |
| `CoffeeMachineSettingAutoFlushEnabled` | `{enabled: bool}` | `set_auto_flush` |
| `CoffeeMachineSettingSteamFlushEnabled` | `{enabled: bool}` | `set_steam_flush` |
| `CoffeeMachineSettingRinseFlushEnabled` | `{enabled: bool}` | `set_rinse_flush` |
| `CoffeeMachineSettingRinseFlushTime` | `{timeSeconds: number}` | `set_rinse_flush_time` |
| `CoffeeMachineSettingCupWarmerEnabled` | `{enabled: bool}` | `set_cup_warmer` |
| `CoffeeMachineSettingHotWaterDoseEnabled` | `{enabled: bool}` | `set_hot_water_dose_enabled` |
| `CoffeeMachineSettingHotWaterDose` | `{doseIndex: string, dose: number}` | `set_hot_water_dose` |
| `CoffeeMachineGroupDoseChangeMode` | `{groupIndex: int, mode: string}` | `set_group_dose_mode` |
| `CoffeeMachineGroupDoseSettingDose` | `{groupIndex: int, mode: string, doseIndex: string, dose: number}` | `set_group_dose` |
| `CoffeeMachineGroupDoseSettingGroupBrewingPressure` | `{groupIndex: int, pressure: number}` | `set_brewing_pressure` |
| `CoffeeMachineGroupDoseSettingContinuousDoseEnabled` | `{groupIndex: int, rinseEnabled: bool}` | `set_continuous_dose_enabled` |
| `CoffeeMachineGroupDoseSettingContinuousDose` | `{groupIndex: int, rinseSeconds: number}` | `set_continuous_dose` |
| `CoffeeMachineGroupDoseSettingMirrorGroup1` | `{groupIndex: int, enabled: bool}` | `set_mirror_group1` |
| `CoffeeMachineSettingPlumbIn` | `{enabled: bool}` | `set_plumb_in` |

`set_group_dose_mode`, `set_group_dose` and `set_brewing_pressure` raise
`OperationNotAvailable` for a dose mode outside the cluster currently active on
the machine (`CMGroupDoses.availableModes`), once a dashboard has been fetched.

## Further commands

| Command string | Payload | Library method |
|---|---|---|
| `CoffeeMachinePreInfusionChangeMode` | `{groupIndex: int, mode: string}` | `change_pre_infusion_mode` |
| `CoffeeMachinePreInfusionSettingTimes` | `{groupIndex: int, doseIndex: string, times: {In: number, Out: number}}` | `change_pre_infusion_times` |
| `CoffeeMachinePreInfusionEnable` | `{enabled: bool}` | `set_pre_infusion_enabled` |
| `CoffeeMachineSettingTimeZone` | `{zone: string}` | `set_time_zone` |
| `CoffeeMachineSettingAutoSteamDose` | `{steamIndex: int, doseIndex: string, dose: number}` | `set_auto_steam_dose` |
| `CoffeeMachineBabyMilkSettingEnabled` | `{steamIndex: int, enabled: bool}` | `set_baby_milk` |
| `CoffeeMachineBabyMilkSettingTargetTemperature` | `{steamIndex: int, targetTemperature: number}` | `set_baby_milk_target_temperature` |
| `ThingScaleSettingPosition` | `{scaleName: string, force?: bool}` | `calibrate_scale` |
| `CoffeeMachineSettingAutoOnOff` | `{onTimeMinutes: int, offTimeMinutes: int, closeDay?: string}` | `set_auto_on_off` |
| `CoffeeMachineSettingAutoOnOffEnabled` | `{enabled: bool}` | `set_auto_on_off_enabled` |
| `CoffeeMachineSettingEarlyStart` | `{enabled: bool}` | `set_early_start` |
| `CoffeeMachineSettingEcoModeTimeout` | `{timeoutMinutes: number}` | `set_eco_mode_timeout` |
| `CoffeeMachineSettingEcoModeOffset` | `{offset: number}` | `set_eco_mode_offset` |
| `CoffeeMachineSettingWeeklyEnabled` | `{enabled: bool}` | `set_weekly_schedule_enabled` |
| `CoffeeMachineSettingWeeklyDay` | `{day: string, enabled: bool, onTimeMinutes: int, offTimeMinutes: int}` | `set_weekly_schedule_day` |

### Modbar pour-over

| Command string | Payload | Library method |
|---|---|---|
| `CoffeeMachineModuleChangeMode` | `{mode: string}` | `set_module_mode` |
| `CoffeeMachineTapChangeMode` | `{tapIndex: int, mode: string}` | `set_tap_mode` |
| `CoffeeMachineSettingModuleTargetTemperature` | `{targetTemperature: number}` | `set_module_target_temperature` |
| `CoffeeMachineSettingTapTargetTemperature` | `{tapIndex: int, targetOffsetTemperature: number}` | `set_tap_target_temperature_offset` |
| `CoffeeMachineChangeRecipe` | `{id: int, index: int, in: number, blooming: {out: number, pause: int}, steps: [{out: number, pause: int}]}` | `change_pour_over_recipe` |

### Not implemented

- `ThingFactoryReset` (`{}`): intentionally left out.
- `SetSpeedSystemConfig`, `SetDoseGroupPair` (grinder): listed in the enum, but
  the app has no payload class for them.
