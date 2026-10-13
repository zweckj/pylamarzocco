"""Module for La Marzocco grinder."""

from __future__ import annotations

from pylamarzocco.const import (
    DoseIndex,
    GrinderDoseMode,
    GrinderGrindWithMode,
    GrinderMode,
    GrinderSpeedLevelType,
    ModelCode,
)
from pylamarzocco.models import (
    GrinderBaristaLight,
    GrinderDoses,
    GrinderGrindWith,
    GrinderMachineStatus,
    GrinderMoreDose,
    GrinderSpeed,
)

from ._thing import LaMarzoccoThing, cloud_only, models_supported


class LaMarzoccoGrinder(LaMarzoccoThing):
    """Class for La Marzocco grinder."""

    @cloud_only
    async def set_power(self, enabled: bool) -> bool:
        """Wake the grinder (GrindingMode) or send it to StandBy."""
        assert self._cloud_client
        mode = GrinderMode.GRINDING if enabled else GrinderMode.STANDBY
        result = await self._cloud_client.set_grinder_mode(self.serial_number, mode)

        # Update dashboard if command succeeded
        if result and (machine_status := self._widget(GrinderMachineStatus)):
            machine_status.mode = mode

        return result

    @cloud_only
    async def set_barista_light(self, enabled: bool) -> bool:
        """Enable or disable the barista light."""
        assert self._cloud_client
        result = await self._cloud_client.set_grinder_barista_light(
            self.serial_number, enabled
        )

        # Update dashboard if command succeeded
        if result and (barista_light := self._widget(GrinderBaristaLight)):
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

        if result and (grind_with := self._widget(GrinderGrindWith)):
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
        """Set the dose, and optionally the speed level, of a grinder dose."""
        assert self._cloud_client
        if mode is None:
            doses = self._widget(GrinderDoses)
            mode = doses.mode if doses else GrinderDoseMode.REV
        result = await self._cloud_client.set_grinder_dose(
            self.serial_number, dose_index, dose, mode, speed_level
        )

        if not result:
            return result

        if doses := self._widget(GrinderDoses):
            dose_list = getattr(doses.doses, mode.name.lower() + "_type", None)
            if dose_list is not None:
                for dose_setting in dose_list:
                    if dose_setting.dose_index == dose_index:
                        dose_setting.dose = dose
            if speed_level is not None and doses.speed_levels is not None:
                for speed_setting in doses.speed_levels:
                    if speed_setting.dose_index == dose_index:
                        speed_setting.level = speed_level

        if speed_level is not None and (speed := self._widget(GrinderSpeed)):
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

        if result and (more_dose := self._widget(GrinderMoreDose)):
            more_dose.revolutions = revolutions

        return result
