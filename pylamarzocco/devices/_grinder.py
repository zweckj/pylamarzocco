"""Module for La Marzocco grinder."""

from __future__ import annotations

from typing import cast

from pylamarzocco.const import WidgetType
from pylamarzocco.models import GrinderBaristaLight

from ._thing import LaMarzoccoThing, cloud_only


class LaMarzoccoGrinder(LaMarzoccoThing):
    """Class for La Marzocco grinder."""

    @cloud_only
    async def set_barista_light(self, enabled: bool) -> bool:
        """Enable or disable the barista light.

        Note: the grinder ignores setting commands while in StandBy.
        """
        assert self._cloud_client
        result = await self._cloud_client.set_grinder_barista_light(
            self.serial_number, enabled
        )

        # Update dashboard if command succeeded
        if result and WidgetType.G_BARISTA_LIGHT in self.dashboard.config:
            barista_light = cast(
                GrinderBaristaLight,
                self.dashboard.config[WidgetType.G_BARISTA_LIGHT],
            )
            barista_light.enabled = enabled

        return result
