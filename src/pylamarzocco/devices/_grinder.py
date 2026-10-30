"""Module for La Marzocco grinder."""

from __future__ import annotations

from pylamarzocco.const import (
    DoseIndex,
    DoseMode,
    GrinderDoseMode,
    GrinderGrindWithMode,
    GrinderMode,
    GrinderSpeedLevelType,
    ModelCode,
)
from pylamarzocco.models import (
    AutoStandBy,
    GrinderBaristaLight,
    GrinderDoses,
    GrinderGrindWith,
    GrinderMachineStatus,
    GrinderMirrorDoses,
    GrinderMoreDose,
    GrinderSingleDoseMode,
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
        # the speed level is a separate command
        if speed_level is not None and not await self.set_speed(
            dose_index, speed_level
        ):
            return False

        doses = self._widget(GrinderDoses)
        if mode is None:
            mode = doses.mode if doses else GrinderDoseMode.REV
        result = await self._cloud_client.set_grinder_dose(
            self.serial_number, dose_index, dose, mode
        )

        if result and doses:
            dose_list = getattr(doses.doses, mode.name.lower() + "_type", None)
            if dose_list is not None:
                for dose_setting in dose_list:
                    if dose_setting.dose_index == dose_index:
                        dose_setting.dose = dose

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

    @cloud_only
    async def set_single_dose_mode(self, enabled: bool) -> bool:
        """Enable or disable the single dose mode."""
        assert self._cloud_client
        result = await self._cloud_client.set_grinder_single_dose_mode(
            self.serial_number, enabled
        )

        if result and (single_dose := self._widget(GrinderSingleDoseMode)):
            single_dose.enabled = enabled

        return result

    @cloud_only
    async def set_mirror_doses(self, enabled: bool) -> bool:
        """Enable or disable mirroring the doses."""
        assert self._cloud_client
        result = await self._cloud_client.set_grinder_mirror_doses(
            self.serial_number, enabled
        )

        if result and (mirror_doses := self._widget(GrinderMirrorDoses)):
            mirror_doses.enabled = enabled

        return result

    @cloud_only
    @models_supported((ModelCode.SWAN_GRINDER,))
    async def set_speed(
        self, dose_index: DoseIndex, speed_level: GrinderSpeedLevelType
    ) -> bool:
        """Set the speed level of a dose."""
        assert self._cloud_client
        result = await self._cloud_client.set_grinder_speed(
            self.serial_number, dose_index, speed_level
        )

        if not result:
            return result

        if (doses := self._widget(GrinderDoses)) and doses.speed_levels is not None:
            for speed_setting in doses.speed_levels:
                if speed_setting.dose_index == dose_index:
                    speed_setting.level = speed_level
        if (speed := self._widget(GrinderSpeed)) and (
            dose_speed := speed.doses.get(str(dose_index))
        ):
            dose_speed.level = speed_level

        return result

    @cloud_only
    @models_supported((ModelCode.SWAN_GRINDER,))
    async def set_auto_speed(
        self, dose_index: DoseIndex, enabled: bool, group_index: int = 1
    ) -> bool:
        """Enable or disable the automatic speed of a dose.

        The automatic speed follows the extraction of the given group of the
        coffee machine in the same coffee station.
        """
        assert self._cloud_client
        result = await self._cloud_client.set_grinder_auto_speed_enabled(
            self.serial_number, dose_index, enabled, group_index
        )

        if (
            result
            and (speed := self._widget(GrinderSpeed))
            and (dose_speed := speed.doses.get(str(dose_index)))
        ):
            dose_speed.auto_enabled = enabled
            dose_speed.group_index = group_index

        return result

    @cloud_only
    @models_supported((ModelCode.SWAN_GRINDER,))
    async def set_auto_speed_reference(
        self,
        dose_mode: DoseMode,
        extraction_seconds: float | None = None,
        dose_mass: float | None = None,
        dose_pulses: float | None = None,
        rate_lock: bool = False,
    ) -> bool:
        """Set the reference extraction the automatic speed adapts to.

        Args:
            dose_mode: DoseMode.MASS_TYPE or DoseMode.PULSES_TYPE
            extraction_seconds: The reference extraction time
            dose_mass: The reference dose in grams, for DoseMode.MASS_TYPE
            dose_pulses: The reference dose in pulses, for DoseMode.PULSES_TYPE
            rate_lock: Keep the flow rate of the reference extraction
        """
        assert self._cloud_client
        result = await self._cloud_client.set_grinder_auto_speed_reference(
            self.serial_number,
            dose_mode,
            extraction_seconds,
            dose_mass,
            dose_pulses,
            rate_lock,
        )

        if (
            result
            and (speed := self._widget(GrinderSpeed))
            and (speed_auto := speed.speed_auto)
        ):
            speed_auto.dose_mode = dose_mode
            speed_auto.extraction_seconds = extraction_seconds
            speed_auto.dose_mass = dose_mass
            speed_auto.dose_pulses = dose_pulses
            speed_auto.rate_lock = rate_lock

        return result

    @cloud_only
    async def set_auto_standby(self, minutes: int) -> bool:
        """Set the minutes of inactivity after which the grinder goes to standby."""
        assert self._cloud_client
        result = await self._cloud_client.set_grinder_auto_standby(
            self.serial_number, minutes
        )

        if result and isinstance(self.schedule.auto_stand_by, AutoStandBy):
            self.schedule.auto_stand_by.stand_by_minutes = minutes

        return result
