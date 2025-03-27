"""Module for La Marzocco coffee machine."""

from __future__ import annotations

import logging

from pylamarzocco.models import ThingSchedulingSettings

from ._thing import LaMarzoccoThing, cloud_only

_LOGGER = logging.getLogger(__name__)


class LaMarzoccoMachine(LaMarzoccoThing):
    """Class for La Marzocco coffee machine"""

    schedule: ThingSchedulingSettings

    @cloud_only
    async def get_schedule(self) -> None:
        """Get the schedule for this machine."""
        assert self.cloud_client
        self.schedule = await self.cloud_client.get_thing_schedule(self.serial_number)

    async def set_power(self, enabled: bool) -> None:
        """Set the power of the machine.

        Args:
            power (bool): True to turn on, False to turn off.
        """
        await self._bluetooth_command_with_cloud_fallback("set_power", enabled=enabled)

    async def set_steam(self, enabled: bool) -> None:
        """Set the steam of the machine.

        Args:
            enabled (bool): True to turn on, False to turn off.
        """
        await self._bluetooth_command_with_cloud_fallback("set_steam", enabled=enabled)
