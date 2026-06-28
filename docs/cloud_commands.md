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
