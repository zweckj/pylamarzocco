# La Marzocco Cloud Command Reference

Reference of `CustomerAppThingCommandType` values and their request payloads.

Each command is sent as `POST /things/{serial}/command/{commandString}` with the
listed JSON body (payload fields are at the top level of the body).

## Type legend

| Notation | JSON |
|---|---|
| `bool` | boolean |
| `int` | integer |
| `number` | decimal number |
| `string` | string (often an enum value) |
| `object` / `list` | object / array |
| `?` suffix | nullable |

## Coverage

`✅` already implemented in `pylamarzocco/clients/_cloud.py`; `🆕` not yet.
`🔬` additionally confirmed on a Strada X.

> Note: enable-toggles are sent as `{"enabled": bool}` only (no `index`).
> The library matches this for `AutoFlush`/`SteamFlush`/`RinseFlush`/`CupWarmer`/
> `HotWaterDoseEnabled`.

> Idempotent round-trip on a Strada X: the commands marked `🔬` returned HTTP 200
> with the shown payload. `GroupDoseSettingDose` was confirmed for every weight
> mode (`MassType`/`PulsesType`/`BrewRatioType`) and dose index (`DoseA–D`), and
> `GroupBrewingPressure` while the weight cluster was active. The remaining Strada
> commands could not be round-trip checked on that unit because the feature is
> unsupported (`RinseFlushEnabled`, `PlumbIn`) or the current value is not readable
> from the dashboard (`ContinuousDose*`, `MirrorGroup1`).

## Machine — core

| Command string | Payload | Status |
|---|---|---|
| `CoffeeMachineChangeMode` | `{mode: string}` | ✅ 🔬 |
| `CoffeeMachineGroupChangeMode` | `{groupIndex: int, mode: string}` | ✅ 🔬 |
| `CoffeeMachineSettingTimeZone` | `{zone: string}` | 🆕 |
| `CoffeeMachineSettingPlumbIn` | `{enabled: bool}` | ✅ |
| `ThingFactoryReset` | `{}` (no fields) | 🆕 |

## Boilers

| Command string | Payload | Status |
|---|---|---|
| `CoffeeMachineSettingCoffeeBoilerEnabled` | `{boilerIndex: int, enabled: bool}` | ✅ 🔬 |
| `CoffeeMachineSettingCoffeeBoilerTargetTemperature` | `{boilerIndex: int, targetTemperature: number}` | ✅ 🔬 |
| `CoffeeMachineSettingSteamBoilerEnabled` | `{boilerIndex: int, enabled: bool}` | ✅ 🔬 |
| `CoffeeMachineSettingSteamBoilerTargetLevel` | `{boilerIndex: int, targetLevel: string}` | ✅ |
| `CoffeeMachineSettingSteamBoilerTargetTemperature` | `{boilerIndex: int, targetTemperature: number}` | ✅ 🔬 |

## Flush & simple toggles

| Command string | Payload | Status |
|---|---|---|
| `CoffeeMachineSettingAutoFlushEnabled` | `{enabled: bool}` | ✅ 🔬 |
| `CoffeeMachineSettingSteamFlushEnabled` | `{enabled: bool}` | ✅ 🔬 |
| `CoffeeMachineSettingRinseFlushEnabled` | `{enabled: bool}` | ✅ |
| `CoffeeMachineSettingRinseFlushTime` | `{timeSeconds: number}` | ✅ 🔬 |
| `CoffeeMachineSettingCupWarmerEnabled` | `{enabled: bool}` | ✅ |
| `CoffeeMachineBackFlushStartCleaning` | `{enabled: bool}` | ✅ |

## Hot water

| Command string | Payload | Status |
|---|---|---|
| `CoffeeMachineSettingHotWaterDoseEnabled` | `{enabled: bool}` | ✅ 🔬 |
| `CoffeeMachineSettingHotWaterDose` | `{doseIndex: string, dose: number}` | ✅ 🔬 |

## Group doses (Strada)

| Command string | Payload | Status |
|---|---|---|
| `CoffeeMachineGroupDoseChangeMode` | `{groupIndex: int, mode: string}` | ✅ 🔬 |
| `CoffeeMachineGroupDoseSettingDose` | `{groupIndex: int, mode: string, doseIndex: string, dose: number}` | ✅ 🔬 |
| `CoffeeMachineGroupDoseSettingGroupBrewingPressure` | `{groupIndex: int, pressure: number}` | ✅ 🔬 |
| `CoffeeMachineGroupDoseSettingContinuousDoseEnabled` | `{groupIndex: int, rinseEnabled: bool}` | ✅ |
| `CoffeeMachineGroupDoseSettingContinuousDose` | `{groupIndex: int, rinseSeconds: number}` | ✅ |
| `CoffeeMachineGroupDoseSettingMirrorGroup1` | `{groupIndex: int, enabled: bool}` | ✅ |

## Pre-brewing / pre-infusion

| Command string | Payload | Status |
|---|---|---|
| `CoffeeMachinePreBrewingChangeMode` | `{mode: string}` | ✅ |
| `CoffeeMachinePreBrewingSettingTimes` | `{times: object, groupIndex: int, doseIndex: string}` | ✅ |
| `CoffeeMachinePreInfusionChangeMode` | `{groupIndex: int, mode: string}` | 🆕 |
| `CoffeeMachinePreInfusionSettingTimes` | `{groupIndex: int, doseIndex: string, times: object}` | 🆕 |
| `CoffeeMachinePreInfusionEnable` | `{enabled: bool}` | 🆕 |

## Brew by weight

| Command string | Payload | Status |
|---|---|---|
| `CoffeeMachineBrewByWeightChangeMode` | `{mode: string}` | ✅ |
| `CoffeeMachineBrewByWeightSettingDoses` | `{doses: list}` | ✅ |

## Grinder

| Command string | Payload | Status |
|---|---|---|
| `GrinderChangeMode` | `{mode: string}` | 🆕 |
| `GrinderSettingSingleDoseModeEnabled` | `{enabled: bool}` | 🆕 |
| `GrinderSettingDose` | `{mode: string, doseIndex: string, dose: number}` | ✅ |
| `GrinderSettingSpeedForDose` | `{doseIndex: string, speedLevel: string}` | 🆕 |
| `GrinderSettingAutoSpeedDoseEnabled` | `{doseIndex: string, groupIndex: int, enabled: bool}` | 🆕 |
| `GrinderSettingAutoSpeedDose` | `{doseMode: string, extractionSeconds: number, doseMass: number, dosePulses: number, rateLock: bool}` | 🆕 |
| `GrinderSettingMoreDose` | `{revolutions: number}` | ✅ |
| `GrinderSettingMirrorDosesEnabled` | `{enabled: bool}` | 🆕 |
| `GrinderSettingBaristaLightEnabled` | `{enabled: bool}` | ✅ |
| `GrinderSettingGrindWithMode` | `{mode: string}` | ✅ |
| `GrinderSettingAutoStandBy` | `{standByMinutes: int}` | 🆕 |
| `SetSpeedSystemConfig` | _payload not documented_ | 🆕 |
| `SetDoseGroupPair` | _payload not documented_ | 🆕 |

## Scheduling

| Command string | Payload | Status |
|---|---|---|
| `CoffeeMachineSettingAutoOnOffEnabled` | `{enabled: bool}` | 🆕 |
| `CoffeeMachineSettingAutoOnOff` | `{onTimeMinutes: int, offTimeMinutes: int}` (variant w/ `closeDay: string`) | ✅ |
| `CoffeeMachineSettingEarlyStart` | `{enabled: bool}` | 🆕 |
| `CoffeeMachineSettingSmartStandBy` | `{enabled: bool, minutes: int, after: string}` | ✅ |
| `CoffeeMachineSettingEcoModeTimeout` | `{timeoutMinutes: number}` | 🆕 |
| `CoffeeMachineSettingEcoModeOffset` | `{offset: number}` | 🆕 |
| `CoffeeMachineSettingWakeUpSchedule` | `{id: string, enabled: bool, onTimeMinutes: int, offTimeMinutes: int, days: list, steamBoiler: bool}` | ✅ |
| `CoffeeMachineDeleteWakeUpSchedule` | `{id: string}` | ✅ |
| `CoffeeMachineSettingWeeklyEnabled` | `{enabled: bool}` | 🆕 |
| `CoffeeMachineSettingWeeklyDay` | `{day: string, enabled: bool, onTimeMinutes: int, offTimeMinutes: int}` | 🆕 |

## Auto-steam / baby milk

| Command string | Payload | Status |
|---|---|---|
| `CoffeeMachineSettingAutoSteamDose` | `{doseIndex: string, dose: number, steamIndex: int}` | 🆕 |
| `CoffeeMachineBabyMilkSettingEnabled` | `{enabled: bool, steamIndex: int}` | 🆕 |
| `CoffeeMachineBabyMilkSettingTargetTemperature` | `{targetTemperature: number, steamIndex: int}` | 🆕 |

## ModBar / Pommel module

| Command string | Payload | Status |
|---|---|---|
| `CoffeeMachineModuleChangeMode` | `{mode: string}` | 🆕 |
| `CoffeeMachineTapChangeMode` | `{tapIndex: int, mode: string}` | 🆕 |
| `CoffeeMachineSettingModuleTargetTemperature` | `{targetTemperature: number}` | 🆕 |
| `CoffeeMachineSettingTapTargetTemperature` | `{tapIndex: int, targetOffsetTemperature: number}` | 🆕 |
| `CoffeeMachineChangeRecipe` | `{id: int, index: int, in: number, blooming: object, steps: list}` | 🆕 |

## Scale

| Command string | Payload | Status |
|---|---|---|
| `ThingScaleSettingPosition` | `{scaleName: string, force: bool?}` | 🆕 |

## Strada X

Confirmed against a Strada X machine (paired with a `SWANGRINDER`). The dashboard
reports exactly these 8 widgets; the table maps each widget to the command(s) that
drive it and the `LaMarzoccoMachine` / `LaMarzoccoCloudClient` method that sends
them.

| Dashboard widget | Command string | Library method | Status |
|---|---|---|---|
| `CMMachineGroupStatus` | `CoffeeMachineChangeMode` | `set_mode` | ✅ |
| | `CoffeeMachineGroupChangeMode` | `set_group_mode` | ✅ |
| `CMCoffeeBoiler` | `CoffeeMachineSettingCoffeeBoilerTargetTemperature` | `set_coffee_target_temperature` | ✅ |
| | `CoffeeMachineSettingCoffeeBoilerEnabled` | `set_coffee_boiler` | ✅ |
| `CMSteamBoilerTemperature` | `CoffeeMachineSettingSteamBoilerEnabled` / `…TargetTemperature` / `…TargetLevel` | `set_steam` / `set_steam_target_temperature` / `set_steam_level` | ✅ |
| `CMAutoFlush` | `CoffeeMachineSettingAutoFlushEnabled` | `set_auto_flush` | ✅ |
| `CMSteamFlush` | `CoffeeMachineSettingSteamFlushEnabled` | `set_steam_flush` | ✅ |
| `CMRinseFlush` | `CoffeeMachineSettingRinseFlushEnabled` | `set_rinse_flush` | ✅ |
| | `CoffeeMachineSettingRinseFlushTime` | `set_rinse_flush_time` | ✅ |
| `CMHotWaterDose` | `CoffeeMachineSettingHotWaterDoseEnabled` | `set_hot_water_dose_enabled` | ✅ |
| | `CoffeeMachineSettingHotWaterDose` | `set_hot_water_dose` | ✅ |
| `CMGroupDoses` | `CoffeeMachineGroupDoseChangeMode` | `set_group_dose_mode` | ✅ 🔬 |
| | `CoffeeMachineGroupDoseSettingDose` | `set_group_dose` | ✅ 🔬 |
| | `CoffeeMachineGroupDoseSettingGroupBrewingPressure` | `set_brewing_pressure` | ✅ 🔬 |
| | `CoffeeMachineGroupDoseSettingContinuousDoseEnabled` | `set_continuous_dose_enabled` | ✅ |
| | `CoffeeMachineGroupDoseSettingContinuousDose` | `set_continuous_dose` | ✅ |
| | `CoffeeMachineGroupDoseSettingMirrorGroup1` | `set_mirror_group1` | ✅ |

No dashboard widget, but applicable to the Strada X (`plumbIn` appears in its
`settings.json`):

| Command string | Library method | Status |
|---|---|---|
| `CoffeeMachineSettingPlumbIn` | `set_plumb_in` | ✅ |

### Capability notes

- **Cup warmer is not a Strada X feature.** The machine exposes no `CMCupWarmer`
  widget and no `cupWarmer` flag in `settings.json`. `CoffeeMachineSettingCupWarmerEnabled`
  / `set_cup_warmer` exist as generic cloud commands but do not apply to this model.
- **Grinder commands** (`Grinder…`) belong to the paired `SWANGRINDER` (a separate
  thing), not to the coffee machine.
- The continuous-dose commands use `rinseEnabled` / `rinseSeconds` field names in
  the payload (kept verbatim above), even though the feature is surfaced as a
  "continuous dose" in the `CMGroupDoses` widget.

### Dose-mode clusters (`CMGroupDoses`)

The group dose mode is not freely switchable. `CMGroupDoses.availableModes` is
dynamic and groups the modes into clusters that are selected at the machine; the
cloud accepts a `CoffeeMachineGroupDoseChangeMode` to a mode outside the current
cluster with HTTP 200 but **silently ignores** it. Observed clusters on the
Strada X:

| Active mode | `availableModes` | Settings exposed |
|---|---|---|
| `ManualType` | `[ManualType]` | none (manual stop) |
| `MassType` | `[MassType, PulsesType, BrewRatioType]` | per-mode `doses` (`DoseA–D`) + `brewingPressure` |
| `ProfileType` | `[ProfileType]` | `profile` (selected profile, mass, time, pressure curve) |

In the weight cluster the same dose slot is interpreted per mode: `MassType` in
grams (step `0.1`), `PulsesType` in pulses (step `1`), `BrewRatioType` as a ratio
(step `0.01`).

Because of this coupling, `LaMarzoccoMachine` guards the related setters when the
dashboard is known and raises `OperationNotAvailable` instead of sending an
ineffective command:

- `set_group_dose_mode` — target mode must be in `availableModes`.
- `set_group_dose` — target mode must have populated doses (be in the active
  cluster) and the `doseIndex` must exist for it.
- `set_brewing_pressure` — requires `brewingPressureSupported` in the current mode.

The guards only apply once a dashboard has been fetched; without cached state the
commands are forwarded unchanged.
