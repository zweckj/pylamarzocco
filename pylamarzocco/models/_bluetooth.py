"""Models for Bluetooth communication"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, replace
from datetime import datetime, timedelta, timezone

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


@dataclass(kw_only=True)
class BluetoothBrewingData(DataClassJSONMixin):
    """Payload of a shot counter notification (all fields optional)."""

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

    def merge(self, other: BluetoothBrewingData) -> BluetoothBrewingData:
        """Return a copy of self, overridden by every non-None field of other."""
        return replace(
            self,
            **{
                f.name: getattr(other, f.name)
                for f in fields(other)
                if getattr(other, f.name) is not None
            },
        )

    def derive_state(
        self, received_at: datetime | None = None
    ) -> BluetoothShotCounterUpdate | None:
        """Derive the brewing state from the (merged) data, if possible."""
        if (
            self.brewing_stopped_time is not None
            or self.brewing_stopped_dose_index is not None
            or self.brewing_stopped_stop_type is not None
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
        elif self.ev is True and self.brewing_time is not None:
            state = BluetoothBrewingState.BREWING
        else:
            return None

        return BluetoothShotCounterUpdate(
            state=state,
            timer_value=(
                self.brewing_time if state is BluetoothBrewingState.BREWING else None
            ),
            final_shot_time=self.brewing_stopped_time,
            received_at=received_at or datetime.now(timezone.utc),
            raw=self,
        )


@dataclass(kw_only=True)
class BluetoothShotCounterUpdate:
    """Brewing state update derived from the Bluetooth shot counter."""

    state: BluetoothBrewingState
    timer_value: float | None = None
    final_shot_time: float | None = None
    received_at: datetime
    raw: BluetoothBrewingData

    @property
    def brewing_start_time(self) -> datetime | None:
        """Return when the current shot started, if brewing."""
        if self.state is not BluetoothBrewingState.BREWING or self.timer_value is None:
            return None
        return self.received_at - timedelta(seconds=self.timer_value)
