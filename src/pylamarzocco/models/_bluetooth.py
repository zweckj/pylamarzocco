"""Models for Bluetooth communication"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, fields, replace
from datetime import datetime, timedelta, timezone
from typing import Any, Self

from mashumaro import field_options
from mashumaro.mixins.json import DataClassJSONMixin

from pylamarzocco.const import (
    BluetoothBrewingState,
    BoilerType,
    MachineMode,
    ModelName,
    SmartStandByType,
)


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
class BluetoothCommandStatus(DataClassJSONMixin):
    """Status of a command sent via Bluetooth."""

    id: str
    message: str
    status: str


def _known_machine_mode(value: str) -> MachineMode | None:
    """Parse a machine mode, ignoring modes this library doesn't know."""
    return MachineMode(value) if value in MachineMode else None


@dataclass(kw_only=True)
class _PartialNotification(DataClassJSONMixin):
    """Part of a shot counter notification, all fields are optional."""

    def _set_fields(self) -> dict[str, Any]:
        return {f.name: v for f in fields(self) if (v := getattr(self, f.name)) is not None}

    @property
    def is_empty(self) -> bool:
        """Return whether no field is set."""
        return not self._set_fields()

    def merge(self, other: Self) -> Self:
        """Return a copy of self, overridden by every non-None field of other."""
        return replace(self, **other._set_fields())


@dataclass(kw_only=True)
class BluetoothBrewingData(_PartialNotification):
    """Brewing part of a shot counter notification."""

    started_dose_index: str | None = field(
        default=None, metadata=field_options(alias="BrewingStartedGroup1DoseIndex")
    )
    ev: bool | None = field(
        default=None, metadata=field_options(alias="BrewingUpdateGroup1Ev")
    )
    backflush: bool | None = field(
        default=None, metadata=field_options(alias="BrewingUpdateGroup1Backflush")
    )
    brewing_time: float | None = field(
        default=None, metadata=field_options(alias="BrewingUpdateGroup1Time")
    )
    flush_stopped_time: float | None = field(
        default=None, metadata=field_options(alias="FlushStoppedGroup1Time")
    )
    flush_stopped_dose_index: str | None = field(
        default=None, metadata=field_options(alias="FlushStoppedGroup1DoseIndex")
    )
    brewing_stopped_time: float | None = field(
        default=None, metadata=field_options(alias="BrewingStoppedGroup1Time")
    )
    brewing_stopped_dose_index: str | None = field(
        default=None, metadata=field_options(alias="BrewingStoppedGroup1DoseIndex")
    )
    brewing_stopped_stop_type: str | None = field(
        default=None, metadata=field_options(alias="BrewingStoppedGroup1StopType")
    )
    brewing_stopped_stop_reason: str | None = field(
        default=None, metadata=field_options(alias="BrewingStoppedGroup1StopReason")
    )

    def derive_state(
        self, received_at: datetime | None = None
    ) -> BluetoothShotCounterUpdate | None:
        """Derive the brewing state from the (merged) data, if possible."""
        if (
            self.brewing_stopped_time is not None
            or self.brewing_stopped_dose_index is not None
            or self.brewing_stopped_stop_type is not None
            or self.brewing_stopped_stop_reason is not None
            or self.ev is False
        ):
            state = BluetoothBrewingState.BREWING_STOPPED
        elif (
            self.flush_stopped_time is not None
            or self.flush_stopped_dose_index is not None
        ):
            state = BluetoothBrewingState.FLUSHED
        elif self.backflush is True:
            state = BluetoothBrewingState.BACKFLUSHING
        elif self.started_dose_index is not None or (
            self.ev is True and self.brewing_time is not None
        ):
            state = BluetoothBrewingState.BREWING
        else:
            return None

        return BluetoothShotCounterUpdate(
            state=state,
            timer_value=(
                (self.brewing_time or 0.0)
                if state is BluetoothBrewingState.BREWING
                else None
            ),
            final_shot_time=self.brewing_stopped_time,
            started_dose_index=self.started_dose_index,
            stop_reason=self.brewing_stopped_stop_reason,
            received_at=received_at or datetime.now(timezone.utc),
            raw=self,
        )


@dataclass(kw_only=True)
class BluetoothShotCounterUpdate:
    """Brewing state update derived from the Bluetooth shot counter."""

    state: BluetoothBrewingState
    timer_value: float | None = None
    final_shot_time: float | None = None
    started_dose_index: str | None = None
    stop_reason: str | None = None
    received_at: datetime
    raw: BluetoothBrewingData
    # when the current shot started, defaults to received_at - timer_value
    brewing_start_time: datetime | None = None

    def __post_init__(self) -> None:
        if (
            self.brewing_start_time is None
            and self.state is BluetoothBrewingState.BREWING
            and self.timer_value is not None
        ):
            self.brewing_start_time = self.received_at - timedelta(
                seconds=self.timer_value
            )


@dataclass(kw_only=True)
class BluetoothMachineTelemetry(_PartialNotification):
    """Live machine values sent with the shot counter notifications.

    A notification usually carries only one of them.
    """

    coffee_boiler_temperature: float | None = field(
        default=None, metadata=field_options(alias="CoffeeBoiler1UpdateTemperature")
    )
    steam_boiler_temperature: float | None = field(
        default=None, metadata=field_options(alias="SteamBoilerUpdateTemperature")
    )
    machine_mode: MachineMode | None = field(
        default=None,
        metadata=field_options(alias="MachineMode", deserialize=_known_machine_mode),
    )
    sleep: str | None = field(default=None, metadata=field_options(alias="Sleep"))
    # sent as a JSON encoded string, the meaning of the counters is unverified
    machine_statistics: dict[str, Any] | None = field(
        default=None,
        metadata=field_options(alias="MachineStatistics", deserialize=json.loads),
    )
