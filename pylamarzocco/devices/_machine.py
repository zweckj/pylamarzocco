"""Module for La Marzocco coffee machine."""

from __future__ import annotations

import logging
from typing import Any

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
    NoWater,
    PrebrewSettingTimes,
    SecondsInOut,
    SteamBoilerLevel,
    ThingDashboardConfig,
    ThingSchedulingSettings,
    WakeUpScheduleSettings,
    Widget,
)

from ._thing import LaMarzoccoThing, cloud_only, models_supported

_LOGGER = logging.getLogger(__name__)


STEAM_LEVEL_MAPPING = {
    SteamTargetLevel.LEVEL_1: 126,
    SteamTargetLevel.LEVEL_2: 128,
    SteamTargetLevel.LEVEL_3: 131,
}

STEAM_LEVEL_REVERSE_MAPPING = {v: k for k, v in STEAM_LEVEL_MAPPING.items()}


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

    async def get_dashboard_from_bluetooth(self) -> None:
        """Get the current boiler settings through Bluetooth and update dashboard.
        
        This method retrieves boiler information, tank status, and smart standby settings
        via Bluetooth and constructs a new ThingDashboardConfig object with the received
        values, assigning it to self.dashboard and updating self.schedule.
        
        Raises:
            BluetoothConnectionFailed: If Bluetooth client is not available or connection fails.
        """
        if self._bluetooth_client is None:
            raise BluetoothConnectionFailed("Bluetooth client is not initialized")
        
        try:
            async with self._bluetooth_client:
                # Get all data from Bluetooth
                boilers = await self._bluetooth_client.get_boilers()
                machine_mode = await self._bluetooth_client.get_machine_mode()
                tank_status = await self._bluetooth_client.get_tank_status()
                smart_standby = await self._bluetooth_client.get_smart_standby_settings()
                
                # Build widget list from Bluetooth data
                widgets: list[Widget] = []
                
                # Add machine status widget
                machine_state = (
                    MachineState.POWERED_ON 
                    if machine_mode == MachineMode.BREWING_MODE 
                    else MachineState.STANDBY
                )
                machine_status = MachineStatus(
                    status=machine_state,
                    available_modes=[MachineMode.BREWING_MODE, MachineMode.STANDBY],
                    mode=machine_mode,
                    next_status=None,
                )
                widgets.append(
                    Widget(
                        code=WidgetType.CM_MACHINE_STATUS,
                        index=1,
                        output=machine_status,
                    )
                )
                
                # Process boilers
                for boiler in boilers:
                    if boiler.id == BoilerType.COFFEE:
                        # Add coffee boiler widget
                        boiler_status = (
                            BoilerStatus.READY 
                            if boiler.is_enabled and boiler.current >= boiler.target - 1
                            else BoilerStatus.HEATING if boiler.is_enabled
                            else BoilerStatus.STAND_BY
                        )
                        coffee_boiler = CoffeeBoiler(
                            status=boiler_status,
                            enabled=boiler.is_enabled,
                            enabled_supported=False,
                            target_temperature=float(boiler.target),
                            target_temperature_min=80,
                            target_temperature_max=100,
                            target_temperature_step=0.1,
                        )
                        widgets.append(
                            Widget(
                                code=WidgetType.CM_COFFEE_BOILER,
                                index=1,
                                output=coffee_boiler,
                            )
                        )
                    elif boiler.id == BoilerType.STEAM:
                        # Add steam boiler widget
                        boiler_status = (
                            BoilerStatus.READY 
                            if boiler.is_enabled and boiler.current >= boiler.target - 1
                            else BoilerStatus.HEATING if boiler.is_enabled
                            else BoilerStatus.STAND_BY
                        )
                        # Map temperature to steam level
                        target_level = STEAM_LEVEL_REVERSE_MAPPING.get(
                            boiler.target, SteamTargetLevel.LEVEL_1
                        )
                        steam_boiler = SteamBoilerLevel(
                            status=boiler_status,
                            enabled=boiler.is_enabled,
                            enabled_supported=True,
                            target_level=target_level,
                            target_level_supported=True,
                        )
                        widgets.append(
                            Widget(
                                code=WidgetType.CM_STEAM_BOILER_LEVEL,
                                index=1,
                                output=steam_boiler,
                            )
                        )
                
                # Add tank status widget (no water alarm when tank_status is False)
                no_water = NoWater(allarm=not tank_status)
                widgets.append(
                    Widget(
                        code=WidgetType.CM_NO_WATER,
                        index=1,
                        output=no_water,
                    )
                )
                
                # Create new dashboard config with Bluetooth data
                self.dashboard = ThingDashboardConfig(
                    serial_number=self.serial_number,
                    widgets=widgets,
                )
                
                # Update schedule with smart standby settings from Bluetooth
                self.schedule.smart_stand_by_enabled = smart_standby.enabled
                self.schedule.smart_stand_by_minutes = smart_standby.minutes
                self.schedule.smart_stand_by_after = smart_standby.mode
                
        except BleakError as exc:
            raise BluetoothConnectionFailed(
                f"Failed to get dashboard data via Bluetooth: {exc}"
            ) from exc

    async def set_power(self, enabled: bool) -> bool:
        """Set the power of the machine.

        Args:
            power (bool): True to turn on, False to turn off.
        """
        return await self.__bluetooth_command_with_cloud_fallback(
            "set_power", enabled=enabled
        )

    @cloud_only
    async def set_steam(self, enabled: bool) -> bool:
        """Set the steam of the machine.

        Args:
            enabled (bool): True to turn on, False to turn off.
        """
        assert self._cloud_client
        return await self._cloud_client.set_steam(self.serial_number, enabled)

    @models_supported((ModelCode.LINEA_MICRA, ModelCode.LINEA_MINI_R))
    async def set_steam_level(self, level: SteamTargetLevel) -> bool:
        """Set the steam target level."""

        return await self.__bluetooth_command_with_cloud_fallback(
            command="set_temp",
            bluetooth_kwargs={
                "boiler": BoilerType.STEAM,
                "temperature": STEAM_LEVEL_MAPPING[level],
            },
            cloud_command="set_steam_target_level",
            cloud_kwargs={"target_level": level},
        )

    async def set_coffee_target_temperature(self, temperature: float) -> bool:
        """Set the coffee target temperature of the machine."""

        return await self.__bluetooth_command_with_cloud_fallback(
            command="set_temp",
            bluetooth_kwargs={
                "boiler": BoilerType.COFFEE,
                "temperature": temperature,
            },
            cloud_command="set_coffee_target_temperature",
            cloud_kwargs={"target_temperature": temperature},
        )

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
                async with self._bluetooth_client:
                    await func(**bt_kwargs)
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
            else:
                return True

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
