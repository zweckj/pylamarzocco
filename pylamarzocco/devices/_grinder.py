"""Module for La Marzocco grinder."""

from __future__ import annotations

from typing import cast

from pylamarzocco.const import GrinderMode, WidgetType
from pylamarzocco.models import GrinderBaristaLight, GrinderMachineStatus

from ._thing import LaMarzoccoThing, cloud_only


class LaMarzoccoGrinder(LaMarzoccoThing):
    """Class for La Marzocco grinder."""

    @cloud_only
    async def set_power(self, enabled: bool) -> bool:
        """Wake the grinder (GrindingMode) or send it to StandBy.

        The grinder ignores all other setting commands while in StandBy, so
        wake it first. The cloud applies the change asynchronously (the
        dashboard catches up a few seconds later).
        """
        assert self._cloud_client
        mode = GrinderMode.GRINDING if enabled else GrinderMode.STANDBY
        result = await self._cloud_client.set_grinder_mode(self.serial_number, mode)

        # Update dashboard if command succeeded
        if result and WidgetType.G_MACHINE_STATUS in self.dashboard.config:
            machine_status = cast(
                GrinderMachineStatus,
                self.dashboard.config[WidgetType.G_MACHINE_STATUS],
            )
            machine_status.mode = mode

        return result

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
