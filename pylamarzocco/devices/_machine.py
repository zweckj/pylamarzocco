"""Module for La Marzocco coffee machine."""

from __future__ import annotations

import logging
from typing import Any

from pylamarzocco.const import (
    ModelCode,
    PreExtractionMode,
    SmartStandByType,
    SteamTargetLevel,
)
from pylamarzocco.models import (
    PrebrewSettingTimes,
    SecondsInOut,
    ThingSchedulingSettings,
    WakeUpScheduleSettings,
)

from ._thing import LaMarzoccoThing, cloud_only, models_supported

_LOGGER = logging.getLogger(__name__)


class LaMarzoccoMachine(LaMarzoccoThing):
    """Class for La Marzocco coffee machine"""

    schedule: ThingSchedulingSettings

    @cloud_only
    async def get_schedule(self) -> None:
        """Get the schedule for this machine."""
        assert self._cloud_client
        self.schedule = await self._cloud_client.get_thing_schedule(self.serial_number)

    async def set_power(self, enabled: bool) -> None:
        """Set the power of the machine.

        Args:
            power (bool): True to turn on, False to turn off.
        """
        assert self._cloud_client
        await self._cloud_client.set_power(self.serial_number, enabled)

    async def set_steam(self, enabled: bool) -> None:
        """Set the steam of the machine.

        Args:
            enabled (bool): True to turn on, False to turn off.
        """
        assert self._cloud_client
        await self._cloud_client.set_steam(self.serial_number, enabled)

    @cloud_only
    @models_supported((ModelCode.LINEA_MICRA, ModelCode.LINEA_MINI_R))
    async def set_steam_level(self, level: SteamTargetLevel) -> None:
        """Set the steam target level."""
        assert self._cloud_client
        await self._cloud_client.set_steam_target_level(self.serial_number, level)

    @cloud_only
    async def set_coffee_target_temperature(self, temperature: float) -> None:
        """Set the coffee target temperature of the machine."""
        assert self._cloud_client
        await self._cloud_client.set_coffee_target_temperature(
            self.serial_number, temperature
        )

    @cloud_only
    async def start_backflush(self) -> None:
        """Trigger the backflush."""
        assert self._cloud_client
        await self._cloud_client.start_backflush_cleaning(self.serial_number)

    @cloud_only
    async def set_pre_extraction_mode(self, mode: PreExtractionMode) -> None:
        """Set the preextraction mode (prebrew/preinfusion)."""
        assert self._cloud_client
        await self._cloud_client.change_pre_extraction_mode(self.serial_number, mode)

    @cloud_only
    async def set_pre_extraction_times(
        self, seconds_on: float, seconds_off: float
    ) -> None:
        """Set the times for pre-extraction."""
        assert self._cloud_client
        await self._cloud_client.change_pre_extraction_times(
            self.serial_number,
            PrebrewSettingTimes(
                times=SecondsInOut(seconds_in=seconds_on, seconds_out=seconds_off)
            ),
        )

    @cloud_only
    async def set_smart_standby(
        self, enabled: bool, minutes: int, after: SmartStandByType
    ) -> None:
        """Set the smart standby mode."""
        assert self._cloud_client
        await self._cloud_client.set_smart_standby(
            self.serial_number, enabled, minutes, after
        )

    @cloud_only
    async def delete_wakeup_schedule(
        self,
        schedule_id: str,
    ) -> None:
        """Delete an existing schedule."""
        assert self._cloud_client
        await self._cloud_client.delete_wakeup_schedule(self.serial_number, schedule_id)

    @cloud_only
    async def set_wakeup_schedule(
        self,
        schedule: WakeUpScheduleSettings,
    ) -> None:
        """Set an existing or a new schedule."""
        assert self._cloud_client
        await self._cloud_client.set_wakeup_schedule(self.serial_number, schedule)

    def to_dict(self) -> dict[Any, Any]:
        """Return self in dict represenation."""
        return {
            **super().to_dict(),
            "schedule": self.schedule.to_dict() if self.schedule else None,
        }
