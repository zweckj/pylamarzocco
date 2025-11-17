"""Module for La Marzocco coffee machine."""

from __future__ import annotations

import logging
from typing import Any, cast

from bleak.exc import BleakError

from pylamarzocco import LaMarzoccoBluetoothClient, LaMarzoccoCloudClient
from pylamarzocco.const import (
    BoilerStatus,
    BoilerType,
    MachineMode,
    MachineState,
    ModelCode,
    PreExtractionMode,
    SmartStandByType,
    SteamTargetLevel,
    WidgetType,
)
from pylamarzocco.exceptions import BluetoothConnectionFailed
from pylamarzocco.models import (
    CoffeeAndFlushCounter,
    CoffeeAndFlushTrend,
    CoffeeBoiler,
    LastCoffeeList,
    MachineStatus,
    PrebrewSettingTimes,
    SecondsInOut,
    SteamBoilerLevel,
    SteamBoilerTemperature,
    ThingSchedulingSettings,
    WakeUpScheduleSettings,
)

from ._thing import LaMarzoccoThing, cloud_only, models_supported

_LOGGER = logging.getLogger(__name__)


STEAM_LEVEL_MAPPING = {
    SteamTargetLevel.LEVEL_1: 126,
    SteamTargetLevel.LEVEL_2: 128,
    SteamTargetLevel.LEVEL_3: 131,
}


class LaMarzoccoMachine(LaMarzoccoThing):
    """Class for La Marzocco coffee machine"""

    def __init__(
        self,
        serial_number: str,
        cloud_client: LaMarzoccoCloudClient | None = None,
        bluetooth_client: LaMarzoccoBluetoothClient | None = None,
    ) -> None:
        """Set up machine."""
        super().__init__(serial_number, cloud_client, bluetooth_client)
        self.schedule = ThingSchedulingSettings(serial_number=serial_number)

    @cloud_only
    async def get_schedule(self) -> None:
        """Get the schedule for this machine."""
        assert self._cloud_client
        self.schedule = await self._cloud_client.get_thing_schedule(self.serial_number)

    async def get_model_info_from_bluetooth(self) -> None:
        """Fetch and update model information from Bluetooth.
        
        Retrieves machine capabilities via Bluetooth and updates the dashboard
        with model_name and model_code information.
        """
        if self._bluetooth_client is None:
            raise BluetoothConnectionFailed("Bluetooth client not initialized")
        
        try:
            capabilities = await self._bluetooth_client.get_machine_capabilities()
        except (BleakError, BluetoothConnectionFailed) as exc:
            _LOGGER.error("Failed to get machine capabilities from Bluetooth: %s", exc)
            raise

        # Update dashboard with capabilities information
        self.dashboard.model_name = capabilities.family
        # Set model_code based on model_name (enum names match)
        try:
            self.dashboard.model_code = ModelCode[capabilities.family.name]
        except KeyError:
            _LOGGER.warning(
                "Could not map model_name %s to model_code", capabilities.family
            )

    async def get_dashboard_from_bluetooth(self) -> None:
        """Fill the dashboard with data from Bluetooth (excluding standby settings)."""
        if self._bluetooth_client is None:
            raise BluetoothConnectionFailed("Bluetooth client not initialized")

        # Get machine mode and update machine status
        try:
            machine_mode = await self._bluetooth_client.get_machine_mode()
        except (BleakError, BluetoothConnectionFailed) as exc:
            _LOGGER.error("Failed to get machine mode from Bluetooth: %s", exc)
            raise

        # Initialize or update machine status widget
        machine_status = cast(
            MachineStatus,
            self.dashboard.config.get(
                WidgetType.CM_MACHINE_STATUS,
                MachineStatus(
                    status=MachineState.STANDBY,
                    available_modes=[MachineMode.BREWING_MODE, MachineMode.STANDBY],
                    mode=machine_mode,
                    next_status=None,
                ),
            ),
        )
        machine_status.mode = machine_mode
        self.dashboard.config[WidgetType.CM_MACHINE_STATUS] = machine_status

        # Get boilers and update dashboard
        try:
            boilers = await self._bluetooth_client.get_boilers()
        except (BleakError, BluetoothConnectionFailed) as exc:
            _LOGGER.error("Failed to get boilers from Bluetooth: %s", exc)
            raise

        for boiler in boilers:
            if boiler.id == BoilerType.COFFEE:
                # Initialize or update coffee boiler widget
                coffee_boiler = cast(
                    CoffeeBoiler,
                    self.dashboard.config.get(
                        WidgetType.CM_COFFEE_BOILER,
                        CoffeeBoiler(
                            status=BoilerStatus.STAND_BY,
                            enabled=boiler.is_enabled,
                            enabled_supported=False,
                            target_temperature=float(boiler.target),
                            target_temperature_min=80,
                            target_temperature_max=100,
                            target_temperature_step=0.1,
                        ),
                    ),
                )
                coffee_boiler.enabled = boiler.is_enabled
                coffee_boiler.target_temperature = float(boiler.target)
                self.dashboard.config[WidgetType.CM_COFFEE_BOILER] = coffee_boiler
            elif boiler.id == BoilerType.STEAM:
                # Models that support steam level (Micra and Mini R)
                if self.dashboard.model_code in (
                    ModelCode.LINEA_MICRA,
                    ModelCode.LINEA_MINI_R,
                ):
                    # Initialize or update steam boiler level widget
                    steam_level = cast(
                        SteamBoilerLevel,
                        self.dashboard.config.get(
                            WidgetType.CM_STEAM_BOILER_LEVEL,
                            SteamBoilerLevel(
                                status=BoilerStatus.STAND_BY,
                                enabled=boiler.is_enabled,
                                enabled_supported=True,
                                target_level=SteamTargetLevel.LEVEL_1,
                                target_level_supported=True,
                            ),
                        ),
                    )
                    steam_level.enabled = boiler.is_enabled
                    self.dashboard.config[WidgetType.CM_STEAM_BOILER_LEVEL] = steam_level
                    # Remove temperature widget if it exists (not applicable for this model)
                    self.dashboard.config.pop(WidgetType.CM_STEAM_BOILER_TEMPERATURE, None)
                else:
                    # Other models (GS3, original Mini) use steam temperature widget
                    steam_temp = cast(
                        SteamBoilerTemperature,
                        self.dashboard.config.get(
                            WidgetType.CM_STEAM_BOILER_TEMPERATURE,
                            SteamBoilerTemperature(
                                status=BoilerStatus.STAND_BY,
                                enabled=boiler.is_enabled,
                                enabled_supported=False,
                                target_temperature=float(boiler.target),
                                target_temperature_min=126,
                                target_temperature_max=131,
                                target_temperature_step=1.0,
                                target_temperature_supported=True,
                            ),
                        ),
                    )
                    steam_temp.enabled = boiler.is_enabled
                    steam_temp.target_temperature = float(boiler.target)
                    self.dashboard.config[WidgetType.CM_STEAM_BOILER_TEMPERATURE] = (
                        steam_temp
                    )
                    # Remove level widget if it exists (not applicable for this model)
                    self.dashboard.config.pop(WidgetType.CM_STEAM_BOILER_LEVEL, None)

    async def set_power(self, enabled: bool) -> bool:
        """Set the power of the machine.

        Args:
            power (bool): True to turn on, False to turn off.
        """
        result = await self.__bluetooth_command_with_cloud_fallback(
            "set_power", enabled=enabled
        )

        # Update dashboard if command succeeded
        if result and WidgetType.CM_MACHINE_STATUS in self.dashboard.config:
            machine_status = cast(
                MachineStatus, self.dashboard.config[WidgetType.CM_MACHINE_STATUS]
            )
            machine_status.mode = (
                MachineMode.BREWING_MODE if enabled else MachineMode.STANDBY
            )

        return result

    async def set_steam(self, enabled: bool) -> bool:
        """Set the steam of the machine.

        Args:
            enabled (bool): True to turn on, False to turn off.
        """
        result = await self.__bluetooth_command_with_cloud_fallback(
            command="set_steam",
            enabled=enabled,
        )

        # Update dashboard if command succeeded
        if result:
            if WidgetType.CM_STEAM_BOILER_LEVEL in self.dashboard.config:
                steam_level = cast(
                    SteamBoilerLevel,
                    self.dashboard.config[WidgetType.CM_STEAM_BOILER_LEVEL],
                )
                steam_level.enabled = enabled
            if WidgetType.CM_STEAM_BOILER_TEMPERATURE in self.dashboard.config:
                steam_temp = cast(
                    SteamBoilerTemperature,
                    self.dashboard.config[WidgetType.CM_STEAM_BOILER_TEMPERATURE],
                )
                steam_temp.enabled = enabled

        return result

    @models_supported((ModelCode.LINEA_MICRA, ModelCode.LINEA_MINI_R))
    async def set_steam_level(self, level: SteamTargetLevel) -> bool:
        """Set the steam target level."""

        result = await self.__bluetooth_command_with_cloud_fallback(
            command="set_temp",
            bluetooth_kwargs={
                "boiler": BoilerType.STEAM,
                "temperature": STEAM_LEVEL_MAPPING[level],
            },
            cloud_command="set_steam_target_level",
            cloud_kwargs={"target_level": level},
        )

        # Update dashboard if command succeeded
        if result and WidgetType.CM_STEAM_BOILER_TEMPERATURE in self.dashboard.config:
            steam_temp = cast(
                SteamBoilerTemperature,
                self.dashboard.config[WidgetType.CM_STEAM_BOILER_TEMPERATURE],
            )
            steam_temp.target_temperature = float(STEAM_LEVEL_MAPPING[level])

        return result

    async def set_coffee_target_temperature(self, temperature: float) -> bool:
        """Set the coffee target temperature of the machine."""

        result = await self.__bluetooth_command_with_cloud_fallback(
            command="set_temp",
            bluetooth_kwargs={
                "boiler": BoilerType.COFFEE,
                "temperature": temperature,
            },
            cloud_command="set_coffee_target_temperature",
            cloud_kwargs={"target_temperature": temperature},
        )

        # Update dashboard if command succeeded
        if result and WidgetType.CM_COFFEE_BOILER in self.dashboard.config:
            coffee_boiler = cast(
                CoffeeBoiler, self.dashboard.config[WidgetType.CM_COFFEE_BOILER]
            )
            coffee_boiler.target_temperature = float(temperature)

        return result

    @cloud_only
    async def start_backflush(self) -> bool:
        """Trigger the backflush."""
        assert self._cloud_client
        return await self._cloud_client.start_backflush_cleaning(self.serial_number)

    @cloud_only
    async def set_pre_extraction_mode(self, mode: PreExtractionMode) -> bool:
        """Set the preextraction mode (prebrew/preinfusion)."""
        assert self._cloud_client
        return await self._cloud_client.change_pre_extraction_mode(
            self.serial_number, mode
        )

    @cloud_only
    async def set_pre_extraction_times(
        self, seconds_on: float, seconds_off: float
    ) -> bool:
        """Set the times for pre-extraction."""
        assert self._cloud_client
        return await self._cloud_client.change_pre_extraction_times(
            self.serial_number,
            PrebrewSettingTimes(
                times=SecondsInOut(seconds_in=seconds_on, seconds_out=seconds_off)
            ),
        )

    async def set_smart_standby(
        self, enabled: bool, minutes: int, mode: SmartStandByType
    ) -> bool:
        """Set the smart standby mode."""
        return await self.__bluetooth_command_with_cloud_fallback(
            command="set_smart_standby",
            bluetooth_kwargs={
                "enabled": enabled,
                "mode": mode,
                "minutes": minutes,
            },
            cloud_kwargs={
                "enabled": enabled,
                "minutes": minutes,
                "after": mode,
            },
        )

    @cloud_only
    async def delete_wakeup_schedule(
        self,
        schedule_id: str,
    ) -> bool:
        """Delete an existing schedule."""
        assert self._cloud_client
        return await self._cloud_client.delete_wakeup_schedule(
            self.serial_number, schedule_id
        )

    @cloud_only
    async def set_wakeup_schedule(
        self,
        schedule: WakeUpScheduleSettings,
    ) -> bool:
        """Set an existing or a new schedule."""
        assert self._cloud_client
        return await self._cloud_client.set_wakeup_schedule(
            self.serial_number, schedule
        )

    def to_dict(self) -> dict[Any, Any]:
        """Return self in dict represenation."""
        return {
            **super().to_dict(),
            "schedule": self.schedule.to_dict() if self.schedule else None,
        }

    async def __bluetooth_command_with_cloud_fallback(
        self,
        command: str,
        cloud_command: str | None = None,
        bluetooth_kwargs: dict[str, Any] | None = None,
        cloud_kwargs: dict[str, Any] | None = None,
        **kwargs,
    ) -> bool:
        """Send a command to the machine via Bluetooth, falling back to cloud if necessary.

        Args:
            command: Command name for Bluetooth client
            cloud_command: Command name for cloud client (or None if the same as BT)
            bluetooth_kwargs: Arguments specific to Bluetooth command
            cloud_kwargs: Arguments specific to cloud command
            **common_kwargs: Arguments common to both commands
        """
        bluetooth_kwargs = bluetooth_kwargs or {}
        cloud_kwargs = cloud_kwargs or {}

        # Merge common kwargs with specific kwargs
        bt_kwargs = {**kwargs, **bluetooth_kwargs}
        cl_kwargs = {**kwargs, **cloud_kwargs}

        # Add serial number to cloud kwargs
        cl_kwargs["serial_number"] = self.serial_number

        cloud_command = command if cloud_command is None else cloud_command

        # First, try with bluetooth
        if self._bluetooth_client is not None:
            func = getattr(self._bluetooth_client, command)
            try:
                _LOGGER.debug(
                    "Sending command %s over bluetooth with params %s",
                    command,
                    str(bt_kwargs),
                )
                result = await func(**bt_kwargs)
                # Check if command succeeded
                if result.status.lower() == "success":
                    return True
            except (BleakError, BluetoothConnectionFailed) as exc:
                msg = "Could not send command to bluetooth device, even though initalized."

                if self._cloud_client is None:
                    _LOGGER.error(
                        "%s Cloud client not initialized, cannot fallback. Full error %s",
                        msg,
                        exc,
                    )
                    return False

                _LOGGER.warning("%s Falling back to cloud", msg)
                _LOGGER.debug("Full error: %s", exc)

        # no bluetooth or failed, try with cloud
        if self._cloud_client is not None:
            _LOGGER.debug(
                "Sending command %s over cloud with params %s",
                command,
                str(cl_kwargs),
            )
            func = getattr(self._cloud_client, cloud_command)
            if await func(**cl_kwargs):
                return True
        return False

    @cloud_only
    async def get_coffee_and_flush_trend(
        self, days: int, timezone: str
    ) -> CoffeeAndFlushTrend:
        """Get the last coffee and flush trend of a thing."""
        assert self._cloud_client
        coffee_and_flush_trend = (
            await self._cloud_client.get_thing_coffee_and_flush_trend(
                serial_number=self.serial_number,
                days=days,
                timezone=timezone,
            )
        )
        self.statistics.widgets[WidgetType.COFFEE_AND_FLUSH_TREND] = (
            coffee_and_flush_trend
        )
        return coffee_and_flush_trend

    @cloud_only
    async def get_last_coffee(self, days: int) -> LastCoffeeList:
        """Get the last coffee."""
        assert self._cloud_client
        last_coffee_list = await self._cloud_client.get_thing_last_coffee(
            serial_number=self.serial_number,
            days=days,
        )
        self.statistics.widgets[WidgetType.LAST_COFFEE] = last_coffee_list
        return last_coffee_list

    @cloud_only
    async def get_coffee_and_flush_counter(self) -> CoffeeAndFlushCounter:
        """Get the coffee and flush counter."""
        assert self._cloud_client
        coffee_and_flush_counter = (
            await self._cloud_client.get_thing_coffee_and_flush_counter(
                serial_number=self.serial_number,
            )
        )
        self.statistics.widgets[WidgetType.COFFEE_AND_FLUSH_COUNTER] = (
            coffee_and_flush_counter
        )
        return coffee_and_flush_counter
