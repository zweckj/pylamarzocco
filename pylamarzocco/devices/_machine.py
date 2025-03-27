"""Module for La Marzocco coffee machine."""

from __future__ import annotations

import logging

from . import LaMarzoccoThing

_LOGGER = logging.getLogger(__name__)


class LaMarzoccoMachine(LaMarzoccoThing):
    """Class for La Marzocco coffee machine"""

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
