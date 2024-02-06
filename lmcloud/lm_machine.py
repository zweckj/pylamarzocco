"""Module for La Marzocco coffee machine."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from copy import deepcopy
from datetime import datetime
from typing import Any

from bleak import BLEDevice

from .const import LaMarzoccoBoilerType, LaMarzoccoMachineModel, PrebrewMode, WeekDay
from .exceptions import ClientNotInitialized, UnknownWebSocketMessage
from .helpers import (
    parse_boilers,
    parse_cloud_statistics,
    parse_coffee_doses,
    parse_preinfusion_settings,
    parse_schedule,
    schedule_to_request,
)
from .client_bluetooth import LaMarzoccoBluetoothClient
from .lm_iot_device import LaMarzoccoIoTDevice
from .client_local import LaMarzoccoLocalClient
from .client_cloud import LaMarzoccoCloudClient
from .models import (
    LaMarzoccoBoiler,
    LaMarzoccoCoffeeStatistics,
    LaMarzoccoPrebrewConfiguration,
    LaMarzoccoSchedule,
    LaMarzoccoScheduleDay,
)

_LOGGER = logging.getLogger(__name__)


class LaMarzoccoMachine(LaMarzoccoIoTDevice):
    """Class for La Marzocco coffee machine"""

    def __init__(
        self,
        model: LaMarzoccoMachineModel,
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
        self.boilers: dict[LaMarzoccoBoilerType, LaMarzoccoBoiler] = {}
        self.prebrew_mode = PrebrewMode.DISABLED
        self.plumbed_in = False
        self.prebrew_configuration: dict[int, LaMarzoccoPrebrewConfiguration] = {}
        self.dose_hot_water: int | None = None
        self.water_contact = True
        self.auto_on_off_enabled = False
        self.auto_on_off_schedule = LaMarzoccoSchedule(False, {})
        self.brew_active = False
        self.brew_active_duration = 0

        self._notify_callback: Callable[[], None] | None = None
        self._system_info: dict[str, Any] | None = None
        self._machine_configuration: dict[str, Any] | None = None
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
    def steam_level(self) -> int:
        """Return the steam level"""
        steam_boiler = self.boilers[LaMarzoccoBoilerType.STEAM]
        if steam_boiler.target_temperature < 128:
            return 1
        if steam_boiler.target_temperature == 128:
            return 2
        return 3

    def parse_config(self, raw_config: dict[str, Any]) -> None:
        """Parse the config object."""
        super().parse_config(raw_config)
        self._raw_config = raw_config
        self.turned_on = raw_config["machineMode"] == "BrewingMode"
        self.plumbed_in = raw_config["isPlumbedIn"]
        self.doses, self.dose_hot_water = parse_coffee_doses(raw_config)
        self.boilers = parse_boilers(raw_config["boilers"])
        self.auto_on_off_schedule = parse_schedule(raw_config["weeklySchedulingConfig"])
        self.prebrew_mode, self.prebrew_configuration = parse_preinfusion_settings(
            raw_config
        )

    def parse_statistics(
        self, raw_statistics: list[dict[str, Any]]
    ) -> LaMarzoccoCoffeeStatistics:
        """Parse the statistics object."""
        return parse_cloud_statistics(raw_statistics)

    async def set_power(
        self,
        enabled: bool,
        ble_device: BLEDevice | None = None,
    ) -> bool:
        """Turn power of machine on or off"""

        if await self._bluetooth_command_with_cloud_fallback(
            command="set_power",
            ble_device=ble_device,
            serial_number=self.serial_number,
            enabled=enabled,
        ):
            self.turned_on = enabled
            self.boilers[LaMarzoccoBoilerType.COFFEE].enabled = enabled
            return True
        return False

    async def set_steam(
        self,
        steam_state: bool,
        ble_device: BLEDevice | None = None,
    ) -> bool:
        """Turn Steamboiler on or off"""

        if await self._bluetooth_command_with_cloud_fallback(
            command="set_steam",
            ble_device=ble_device,
            serial_number=self.serial_number,
            enabled=steam_state,
        ):
            self.boilers[LaMarzoccoBoilerType.STEAM].enabled = steam_state
            return True
        return False

    async def set_temp(
        self,
        boiler: LaMarzoccoBoilerType,
        temperature: float,
        ble_device: BLEDevice | None = None,
    ) -> bool:
        """Set target temperature for boiler"""
        if boiler == LaMarzoccoBoilerType.STEAM:
            if self.model == LaMarzoccoMachineModel.LINEA_MICRA:
                if temperature not in (126, 128, 131):
                    msg = "Steam temp must be one of 126, 128, 131 (°C)"
                    _LOGGER.debug(msg)
                    raise ValueError(msg)
            elif self.model == LaMarzoccoMachineModel.LINEA_MINI:
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
            ble_device=ble_device,
            serial_number=self.serial_number,
            boiler=boiler,
            temperature=temperature,
        ):

            self.boilers[boiler].target_temperature = temperature
            return True
        return False

    async def set_prebrew_mode(self, mode: PrebrewMode) -> bool:
        """Set preinfusion mode"""

        if mode == PrebrewMode.PREINFUSION and not self.plumbed_in:
            msg = "Pre-Infusion can only be enabled when plumbin is enabled."
            _LOGGER.debug(msg)
            raise ValueError(msg)

        if await self.cloud_client.set_prebrew_mode(self.serial_number, mode):
            self.prebrew_mode = mode
            return True
        return False

    async def set_prebrew_time(
        self,
        prebrew_on_time: float,
        prebrew_off_time: float,
        key: int = 1,
    ) -> bool:
        """Set prebrew time"""

        if await self.cloud_client.configure_pre_brew_infusion_time(
            self.serial_number, prebrew_on_time, prebrew_off_time, key
        ):
            self.prebrew_configuration[key].on_time = prebrew_on_time
            self.prebrew_configuration[key].off_time = prebrew_off_time
            return True
        return False

    async def set_preinfusion_time(
        self,
        preinfusion_time: float,
        key: int = 1,
    ) -> bool:
        """Set preinfusion time"""

        if await self.cloud_client.configure_pre_brew_infusion_time(
            self.serial_number, 0, preinfusion_time, key
        ):
            self.prebrew_configuration[key].off_time = preinfusion_time
            return True
        return False

    async def set_dose(self, dose: int, key: int = 1) -> bool:
        """Set dose"""

        if await self.cloud_client.set_dose(self.serial_number, key, dose):
            self.doses[key] = dose
            return True
        return False

    async def set_dose_tea_water(self, dose: int) -> bool:
        """Set tea dose"""

        if await self.cloud_client.set_dose_hot_water(self.serial_number, dose):
            self.dose_hot_water = dose
            return True
        return False

    async def set_plumbed_in(self, enabled: bool) -> bool:
        """Set plumbed in"""

        if await self.cloud_client.enable_plumbin(self.serial_number, enabled):
            self.plumbed_in = enabled
            return True
        return False

    async def start_backflush(self) -> None:
        """Start backflush"""

        await self.cloud_client.start_backflush(self.serial_number)

    async def set_schedule(self, schedule: LaMarzoccoSchedule) -> bool:
        """Set schedule"""

        if await self.cloud_client.set_schedule(
            self.serial_number, schedule_to_request(schedule)
        ):
            self.auto_on_off_schedule = schedule
            return True
        return False

    async def enable_schedule_globally(self, enabled: bool) -> bool:
        """Enable schedule globally"""
        schedule = deepcopy(self.auto_on_off_schedule)
        schedule.enabled = enabled
        return await self.set_schedule(schedule)

    async def set_schedule_day(
        self,
        day: WeekDay,
        enabled: bool,
        h_on: int,
        m_on: int,
        h_off: int,
        m_off: int,
    ) -> bool:
        """Configure a single day in the schedule"""
        day_settings = LaMarzoccoScheduleDay(enabled, h_on, h_off, m_on, m_off)
        schedule = deepcopy(self.auto_on_off_schedule)
        schedule.days[day] = day_settings
        return await self.set_schedule(schedule)

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
        try:
            notify = self._parse_websocket_message(message)
        except UnknownWebSocketMessage as exc:
            _LOGGER.warning("Unknown websocket message received")
            _LOGGER.debug(exc)

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
        if "MachineConfiguration" in message:
            # got machine configuration
            self._machine_configuration = json.loads(message["MachineConfiguration"])
            return False

        if "SystemInfo" in message:
            self._system_info = json.loads(message["SystemInfo"])
            return False

        raise UnknownWebSocketMessage(f"Unknown websocket message: {message}")

    def _parse_list_message(self, message: list[dict[str, Any]]) -> bool:
        for msg in message:

            if "SteamBoilerUpdateTemperature" in msg:
                self.boilers[LaMarzoccoBoilerType.STEAM].current_temperature = msg[
                    "SteamBoilerUpdateTemperature"
                ]

            elif "CoffeeBoiler1UpdateTemperature" in msg:
                self.boilers[LaMarzoccoBoilerType.COFFEE].current_temperature = msg[
                    "CoffeeBoiler1UpdateTemperature"
                ]

            elif "Sleep" in msg:
                self.turned_on = False

            elif "SteamBoilerEnabled" in msg:
                value = msg["SteamBoilerEnabled"]
                self.boilers[LaMarzoccoBoilerType.STEAM].enabled = value == "Enabled"

            elif "WakeUp" in msg:
                self.turned_on = True

            elif "MachineStatistics" in msg:
                self.statistics = self.parse_statistics(
                    json.loads(msg["MachineStatistics"])
                )

            elif "BrewingUpdateGroup1Time" in msg:
                self.brew_active_duration = msg["BrewingUpdateGroup1Time"]

            elif "BrewingStartedGroup1StopType" in msg:
                self.brew_active = True

            elif (
                "BrewingStoppedGroup1StopType" in msg or "BrewingSnapshotGroup1" in msg
            ):
                self.brew_active = False

            elif "SteamBoilerUpdateSetPoint" in msg:
                self.boilers[LaMarzoccoBoilerType.STEAM].target_temperature = msg[
                    "SteamBoilerUpdateSetPoint"
                ]

            elif "CoffeeBoiler1UpdateSetPoint" in msg:
                self.boilers[LaMarzoccoBoilerType.COFFEE].target_temperature = msg[
                    "CoffeeBoiler1UpdateSetPoint"
                ]

            elif "BoilersTargetTemperature" in msg:
                boilers = json.loads(msg["BoilersTargetTemperature"])
                for boiler in boilers:
                    value = boiler["value"]
                    self.boilers[
                        LaMarzoccoBoilerType(boiler["id"])
                    ].target_temperature = value

            elif "Boilers" in msg:
                boilers = json.loads(msg["Boilers"])
                self.boilers = parse_boilers(boilers)

            elif "PreinfusionSettings" in msg:
                settings: dict[str, Any] = {}
                settings["preinfusionSettings"] = json.loads(msg["PreinfusionSettings"])

                mode, config = parse_preinfusion_settings(settings)
                self.prebrew_mode = mode
                self.prebrew_configuration = config

        raise UnknownWebSocketMessage(f"Unknown websocket message: {message}")
