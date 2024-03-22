"""Module for La Marzocco coffee machine."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any


from .client_bluetooth import LaMarzoccoBluetoothClient
from .client_cloud import LaMarzoccoCloudClient
from .client_local import LaMarzoccoLocalClient
from .const import (
    BoilerType,
    FirmwareType,
    MachineModel,
    PhysicalKey,
    PrebrewMode,
    SmartStandbyMode,
    SteamLevel,
)
from .exceptions import ClientNotInitialized, UnknownWebSocketMessage
from .helpers import (
    parse_boilers,
    parse_cloud_statistics,
    parse_coffee_doses,
    parse_preinfusion_settings,
    parse_smart_standby,
    parse_wakeup_sleep_entries,
)
from .lm_device import LaMarzoccoDevice
from .models import (
    LaMarzoccoCoffeeStatistics,
    LaMarzoccoMachineConfig,
    LaMarzoccoSmartStandby,
)

_LOGGER = logging.getLogger(__name__)


class LaMarzoccoMachine(LaMarzoccoDevice):
    """Class for La Marzocco coffee machine"""

    def __init__(
        self,
        model: MachineModel,
        serial_number: str,
        name: str,
        cloud_client: LaMarzoccoCloudClient | None = None,
        local_client: LaMarzoccoLocalClient | None = None,
        bluetooth_client: LaMarzoccoBluetoothClient | None = None,
    ) -> None:
        """Initializes a new LaMarzoccoCoffeeMachine instance"""

        super().__init__(
            model=model,
            serial_number=serial_number,
            name=name,
            cloud_client=cloud_client,
            local_client=local_client,
            bluetooth_client=bluetooth_client,
        )
        self.config: LaMarzoccoMachineConfig = LaMarzoccoMachineConfig(
            turned_on=False,
            boilers={},
            prebrew_mode=PrebrewMode.DISABLED,
            plumbed_in=False,
            prebrew_configuration={},
            dose_hot_water=0,
            doses={},
            water_contact=False,
            brew_active=False,
            brew_active_duration=0,
            smart_standby=LaMarzoccoSmartStandby(
                enabled=False,
                minutes=10,
                mode=SmartStandbyMode.POWER_ON,
            ),
            wake_up_sleep_entries=[],
        )
        self.statistics: LaMarzoccoCoffeeStatistics = LaMarzoccoCoffeeStatistics(
            drink_stats={},
            continous=0,
            total_flushes=0,
        )

        self._notify_callback: Callable[[], None] | None = None
        self._system_info: dict[str, Any] | None = None
        self._timestamp_last_websocket_msg: datetime | None = None

    @classmethod
    async def create(cls, *args: Any, **kwargs: Any) -> LaMarzoccoMachine:
        """Create a new LaMarzoccoMachine instance"""

        self = cls(*args, **kwargs)
        await self.get_config()
        if self._cloud_client is not None:
            await self.get_firmware()
            await self.get_statistics()
        return self

    @property
    def full_model_name(self) -> str:
        """Return the full model name"""

        if self.model == MachineModel.LINEA_MICRA:
            return "Linea Micra"

        return self.model

    @property
    def websocket_connected(self) -> bool:
        """Return the connection status of the websocket client."""

        if self._local_client is None:
            return False
        return self._local_client.websocket_connected

    def parse_config(self, raw_config: dict[str, Any]) -> None:
        """Parse the config object."""

        super().parse_config(raw_config)
        self._raw_config = raw_config
        self.config.turned_on = raw_config["machineMode"] == "BrewingMode"
        self.config.plumbed_in = raw_config["isPlumbedIn"]
        self.config.water_contact = raw_config["tankStatus"]
        self.config.doses, self.config.dose_hot_water = parse_coffee_doses(raw_config)
        self.config.boilers = parse_boilers(raw_config["boilers"])
        self.config.prebrew_mode, self.config.prebrew_configuration = (
            parse_preinfusion_settings(raw_config)
        )
        self.config.smart_standby = parse_smart_standby(
            raw_config.get("smartStandBy", {})
        )
        self.config.wake_up_sleep_entries = parse_wakeup_sleep_entries(
            raw_config.get("wakeUpSleepEntries", [])
        )

    def parse_statistics(self, raw_statistics: list[dict[str, Any]]) -> None:
        """Parse the statistics object."""

        self.statistics = parse_cloud_statistics(raw_statistics)

    async def set_power(
        self,
        enabled: bool,
    ) -> bool:
        """Turn power of machine on or off"""

        if await self._bluetooth_command_with_cloud_fallback(
            command="set_power",
            enabled=enabled,
        ):
            self.config.turned_on = enabled
            self.config.boilers[BoilerType.COFFEE].enabled = enabled
            return True
        return False

    async def set_steam(
        self,
        enabled: bool,
    ) -> bool:
        """Turn Steamboiler on or off"""

        if await self._bluetooth_command_with_cloud_fallback(
            command="set_steam",
            enabled=enabled,
        ):
            self.config.boilers[BoilerType.STEAM].enabled = enabled
            return True
        return False

    async def set_temp(
        self,
        boiler: BoilerType,
        temperature: float,
    ) -> bool:
        """Set target temperature for boiler"""

        if boiler == BoilerType.STEAM:
            if self.model == MachineModel.LINEA_MICRA:
                if temperature not in SteamLevel:
                    msg = "Steam temp must be one of 126, 128, 131 (°C)"
                    _LOGGER.debug(msg)
                    raise ValueError(msg)
            elif self.model == MachineModel.LINEA_MINI:
                _LOGGER.error("Steam temp is not supported on Linea Mini.")
                return False
        else:
            if temperature > 104 or temperature < 85:
                msg = "Coffee temp must be between 85 and 104 (°C)"
                _LOGGER.debug(msg)
                raise ValueError(msg)

            temperature = round(temperature, 1)

        if await self._bluetooth_command_with_cloud_fallback(
            command="set_temp",
            boiler=boiler,
            temperature=temperature,
        ):

            self.config.boilers[boiler].target_temperature = temperature
            return True
        return False

    async def set_steam_level(
        self,
        level: SteamLevel,
    ) -> bool:
        """Set steam level"""
        return await self.set_temp(BoilerType.STEAM, level)

    async def set_prebrew_mode(self, mode: PrebrewMode) -> bool:
        """Set preinfusion mode"""

        if mode == PrebrewMode.PREINFUSION and not self.config.plumbed_in:
            msg = "Pre-Infusion can only be enabled when plumbin is enabled."
            _LOGGER.debug(msg)
            raise ValueError(msg)

        if await self.cloud_client.set_prebrew_mode(self.serial_number, mode):
            self.config.prebrew_mode = mode
            return True
        return False

    async def set_prebrew_time(
        self,
        prebrew_on_time: float | None = None,
        prebrew_off_time: float | None = None,
        key: PhysicalKey = PhysicalKey.A,
    ) -> bool:
        """Set prebrew time"""

        if prebrew_on_time is None:
            prebrew_on_time = self.config.prebrew_configuration[key].on_time

        if prebrew_off_time is None:
            prebrew_off_time = self.config.prebrew_configuration[key].off_time

        if await self.cloud_client.configure_pre_brew_infusion_time(
            self.serial_number, prebrew_on_time, prebrew_off_time, key
        ):
            self.config.prebrew_configuration[key].on_time = prebrew_on_time
            self.config.prebrew_configuration[key].off_time = prebrew_off_time
            return True
        return False

    async def set_preinfusion_time(
        self,
        preinfusion_time: float,
        key: PhysicalKey = PhysicalKey.A,
    ) -> bool:
        """Set preinfusion time"""

        if await self.cloud_client.configure_pre_brew_infusion_time(
            self.serial_number, 0, preinfusion_time, key
        ):
            self.config.prebrew_configuration[key].off_time = preinfusion_time
            return True
        return False

    async def set_dose(self, dose: int, key: PhysicalKey) -> bool:
        """Set dose"""

        if await self.cloud_client.set_dose(self.serial_number, key, dose):
            self.config.doses[key] = dose
            return True
        return False

    async def set_dose_tea_water(self, dose: int) -> bool:
        """Set tea dose"""

        if await self.cloud_client.set_dose_hot_water(self.serial_number, dose):
            self.config.dose_hot_water = dose
            return True
        return False

    async def set_plumbed_in(self, enabled: bool) -> bool:
        """Set plumbed in"""

        if await self.cloud_client.enable_plumbin(self.serial_number, enabled):
            self.config.plumbed_in = enabled
            return True
        return False

    async def start_backflush(self) -> None:
        """Start backflush"""

        await self.cloud_client.start_backflush(self.serial_number)

    # async def set_schedule(self, schedule: LaMarzoccoSchedule) -> bool:
    #     """Set schedule"""

    #     if await self.cloud_client.set_schedule(
    #         self.serial_number, schedule_to_request(schedule)
    #     ):
    #         self.config.auto_on_off_schedule = schedule
    #         return True
    #     return False

    # async def enable_schedule_globally(self, enabled: bool) -> bool:
    #     """Enable schedule globally"""

    #     schedule = deepcopy(self.config.auto_on_off_schedule)
    #     schedule.enabled = enabled
    #     return await self.set_schedule(schedule)

    # async def set_schedule_day(
    #     self,
    #     day: WeekDay,
    #     enabled: bool,
    #     h_on: int,
    #     m_on: int,
    #     h_off: int,
    #     m_off: int,
    # ) -> bool:
    #     """Configure a single day in the schedule"""

    #     day_settings = LaMarzoccoScheduleDay(
    #         enabled=enabled,
    #         h_on=h_on,
    #         h_off=h_off,
    #         m_on=m_on,
    #         m_off=m_off,
    #     )
    #     schedule = deepcopy(self.config.auto_on_off_schedule)
    #     schedule.days[day] = day_settings
    #     return await self.set_schedule(schedule)

    async def set_smart_standby(
        self, enabled: bool, minutes: int, mode: SmartStandbyMode
    ) -> bool:
        """Set smart standby"""

        if await self.cloud_client.set_smart_standby(
            serial_number=self.serial_number,
            enabled=enabled,
            minutes=minutes,
            mode=mode,
        ):
            self.config.smart_standby = LaMarzoccoSmartStandby(
                enabled=enabled, mode=mode, minutes=minutes
            )
            return True
        return False

    async def update_firmware(self, component: FirmwareType) -> bool:
        """Update firmware"""

        return await self.cloud_client.update_firmware(self.serial_number, component)

    async def websocket_connect(
        self, notify_callback: Callable[[], None] | None = None
    ) -> None:
        """Connect to the websocket of the machine."""

        self._notify_callback = notify_callback
        if self._local_client is None:
            raise ClientNotInitialized("Local client not initialized")

        await self._local_client.websocket_connect(
            callback=self.on_websocket_message_received
        )

    def on_websocket_message_received(self, message: str | bytes) -> None:
        """Websocket message received"""

        self._timestamp_last_websocket_msg = datetime.now()
        message = str(message)

        _LOGGER.debug("Received message from websocket, message %s", message)
        notify = False
        try:
            notify = self._parse_websocket_message(message)
        except UnknownWebSocketMessage as exc:
            _LOGGER.warning("Unknown websocket message received")
            _LOGGER.warning("Message: %s", message)
            _LOGGER.debug(exc)
        except TypeError as exc:
            _LOGGER.error("Error when parsing websocket message: %s, %s", message, exc)

        if notify and self._notify_callback:
            self._notify_callback()

    def _parse_websocket_message(self, message: str) -> bool:
        """Handle a message received on the websocket."""

        message = json.loads(message)

        if isinstance(message, dict):
            self._parse_dict_message(message)
            return False

        if isinstance(message, list):
            if "KeepAlive" in message[0]:
                return False
            self._parse_list_message(message)
            return True

        raise UnknownWebSocketMessage(f"Unknown websocket message: {message}")

    def _parse_dict_message(self, message: Any) -> bool:
        """ "Parse websocket message that is a dict."""

        if "MachineConfiguration" in message:
            # got machine configuration
            self._raw_config = json.loads(message["MachineConfiguration"])
            return False

        if "SystemInfo" in message:
            self._system_info = json.loads(message["SystemInfo"])
            return False

        raise UnknownWebSocketMessage(f"Unknown websocket message: {message}")

    def _parse_list_message(self, message: list[dict[str, Any]]) -> bool:
        """Parse websocket message that is a list."""

        property_updated = False
        for msg in message:

            if "SteamBoilerUpdateTemperature" in msg:
                self.config.boilers[BoilerType.STEAM].current_temperature = msg[
                    "SteamBoilerUpdateTemperature"
                ]
                property_updated = True

            elif "CoffeeBoiler1UpdateTemperature" in msg:
                self.config.boilers[BoilerType.COFFEE].current_temperature = msg[
                    "CoffeeBoiler1UpdateTemperature"
                ]
                property_updated = True

            elif "Sleep" in msg:
                self.config.turned_on = False
                property_updated = True

            elif "SteamBoilerEnabled" in msg:
                value = msg["SteamBoilerEnabled"]
                self.config.boilers[BoilerType.STEAM].enabled = value
                property_updated = True

            elif "WakeUp" in msg:
                self.config.turned_on = True
                property_updated = True

            elif "MachineMode" in msg:
                self.config.turned_on = msg["MachineMode"] == "BrewingMode"
                property_updated = True

            elif "MachineStatistics" in msg:
                property_updated = True

            elif "BrewingUpdateGroup1Time" in msg:
                self.config.brew_active_duration = msg["BrewingUpdateGroup1Time"]
                property_updated = True

            elif "BrewingStartedGroup1StopType" in msg:
                self.config.brew_active = True
                property_updated = True

            elif (
                "BrewingStoppedGroup1StopType" in msg or "BrewingSnapshotGroup1" in msg
            ):
                self.config.brew_active = False
                property_updated = True

            elif "SteamBoilerUpdateSetPoint" in msg:
                self.config.boilers[BoilerType.STEAM].target_temperature = msg[
                    "SteamBoilerUpdateSetPoint"
                ]
                property_updated = True

            elif "CoffeeBoiler1UpdateSetPoint" in msg:
                self.config.boilers[BoilerType.COFFEE].target_temperature = msg[
                    "CoffeeBoiler1UpdateSetPoint"
                ]
                property_updated = True

            elif "BoilersTargetTemperature" in msg:
                target_temps = json.loads(msg["BoilersTargetTemperature"])
                for boiler in BoilerType:
                    self.config.boilers[boiler].target_temperature = target_temps[
                        boiler
                    ]
                property_updated = True

            elif "Boilers" in msg:
                boilers = json.loads(msg["Boilers"])
                self.config.boilers = parse_boilers(boilers)
                property_updated = True

            elif "PreinfusionSettings" in msg:
                settings: dict[str, Any] = {}
                settings["preinfusionSettings"] = json.loads(msg["PreinfusionSettings"])

                self.config.prebrew_mode, self.config.prebrew_configuration = (
                    parse_preinfusion_settings(settings)
                )
                property_updated = True

        if not property_updated:
            raise UnknownWebSocketMessage(f"Unknown websocket message: {message}")
        return True
