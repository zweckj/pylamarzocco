"""Module for La Marzocco grinder."""

from __future__ import annotations

from typing import cast

from pylamarzocco.const import (
    DoseIndex,
    GrinderDoseMode,
    GrinderGrindWithMode,
    GrinderSpeedLevelType,
    ModelCode,
    WidgetType,
)
from pylamarzocco.models import (
    GrinderBaristaLight,
    GrinderDoses,
    GrinderGrindWith,
    GrinderMoreDose,
    GrinderSpeed,
)

from ._thing import LaMarzoccoThing, cloud_only, models_supported


class LaMarzoccoGrinder(LaMarzoccoThing):
    """Class for La Marzocco grinder."""

    @cloud_only
    async def set_barista_light(self, enabled: bool) -> bool:
        """Enable or disable the barista light."""
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

    @cloud_only
    @models_supported((ModelCode.SWAN_GRINDER,))
    async def set_grind_with(self, mode: GrinderGrindWithMode) -> bool:
        """Set the grind-with mode."""
        assert self._cloud_client
        result = await self._cloud_client.set_grinder_grind_with(
            self.serial_number, mode
        )

        # Update dashboard if command succeeded
        if result and WidgetType.G_GRIND_WITH in self.dashboard.config:
            grind_with = cast(
                GrinderGrindWith,
                self.dashboard.config[WidgetType.G_GRIND_WITH],
            )
            grind_with.mode = mode

        return result

    @cloud_only
    async def set_dose(
        self,
        dose_index: DoseIndex,
        dose: float,
        mode: GrinderDoseMode | None = None,
        speed_level: GrinderSpeedLevelType | None = None,
    ) -> bool:
        """Set the dose, and optionally the speed level, of a grinder dose.

        If no mode is given, the grinder's current dose mode is used.
        """
        assert self._cloud_client
        if mode is None:
            # Default to the grinder's current dose mode when available.
            if WidgetType.G_DOSES in self.dashboard.config:
                doses = cast(GrinderDoses, self.dashboard.config[WidgetType.G_DOSES])
                mode = doses.mode
            else:
                mode = GrinderDoseMode.REV
        result = await self._cloud_client.set_grinder_dose(
            self.serial_number, dose_index, dose, mode, speed_level
        )

        if not result:
            return result

        # Update dashboard dose value if command succeeded
        if WidgetType.G_DOSES in self.dashboard.config:
            doses = cast(GrinderDoses, self.dashboard.config[WidgetType.G_DOSES])
            dose_list = getattr(doses.doses, mode.name.lower() + "_type", None)
            if dose_list is not None:
                for dose_setting in dose_list:
                    if dose_setting.dose_index == dose_index:
                        dose_setting.dose = dose
            if speed_level is not None and doses.speed_levels is not None:
                for speed_setting in doses.speed_levels:
                    if speed_setting.dose_index == dose_index:
                        speed_setting.level = speed_level

        # Update the GSpeed widget speed level as well
        if (
            speed_level is not None
            and WidgetType.G_SPEED in self.dashboard.config
        ):
            speed = cast(GrinderSpeed, self.dashboard.config[WidgetType.G_SPEED])
            if str(dose_index) in speed.doses:
                speed.doses[str(dose_index)].level = speed_level

        return result

    @cloud_only
    @models_supported((ModelCode.SWAN_GRINDER,))
    async def set_more_dose(self, revolutions: float) -> bool:
        """Set the additional ("more dose") revolutions of the grinder."""
        assert self._cloud_client
        result = await self._cloud_client.set_grinder_more_dose(
            self.serial_number, revolutions
        )

        # Update dashboard if command succeeded
        if result and WidgetType.G_MORE_DOSE in self.dashboard.config:
            more_dose = cast(
                GrinderMoreDose,
                self.dashboard.config[WidgetType.G_MORE_DOSE],
            )
            more_dose.revolutions = revolutions

        return result
