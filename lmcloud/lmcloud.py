"""Class to interact with the La Marzocco Cloud API, local API and Bluetooth."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Callable, Coroutine

from authlib.integrations.base_client.errors import OAuthError  # type: ignore[import]
from authlib.integrations.httpx_client import AsyncOAuth2Client  # type: ignore[import]
from bleak import BleakError, BaseBleakScanner

from .const import (
    BACKFLUSH_ENABLED,
    BOILER_TARGET_TEMP,
    BOILERS,
    BREW_ACTIVE,
    COFFEE_BOILER_NAME,
    CURRENT,
    CUSTOMER_URL,
    DEFAULT_PORT,
    GW_AWS_PROXY_BASE_URL,
    GW_MACHINE_BASE_URL,
    KEY,
    MACHINE_MODE,
    MACHINE_NAME,
    MODEL_NAME,
    PLUMBED_IN,
    POLLING_DELAY_S,
    POLLING_DELAY_STATISTICS_S,
    PRE_INFUSION_SETTINGS,
    SERIAL_NUMBER,
    STEAM_BOILER_NAME,
    TANK_STATUS,
    TARGET,
    TOKEN_URL,
    WEEKLY_SCHEDULING_CONFIG,
)
from .exceptions import (
    AuthFail,
    BluetoothDeviceNotFound,
    BluetoothConnectionFailed,
    MachineNotFound,
    RequestNotSuccessful,
)
from .helpers import (
    parse_doses,
    parse_preinfusion_settings,
    parse_statistics,
    schedule_in_to_out,
    schedule_out_to_hass,
    schedule_out_to_in,
)
from .lmbluetooth import LMBluetooth
from .lmlocalapi import LMLocalAPI

_logger = logging.getLogger(__name__)


class LMCloud:
    """Client to interact with the La Marzocco Cloud API."""

    def __init__(self) -> None:
        """Initialize the client."""
        self._lm_local_api: LMLocalAPI | None = None
        self._lm_bluetooth: LMBluetooth | None = None
        self._client: AsyncOAuth2Client | None = None
        self._machine_info: dict[str, str] = {}
        self._firmware: dict[str, Any] = {}
        self._config: dict[str, Any] = {}
        self._gw_url_with_serial: str = ""
        self._date_received: datetime | None = None
        self._current_status: dict[str, str | bool | float] = {}
        self._config_steamboiler: dict[str, Any] = {}
        self._config_coffeeboiler: dict[str, Any] = {}
        self._statistics: list[dict[str, Any]] = []
        self._last_statistics_update: datetime | None = None
        self._use_websocket: bool = False
        self._brew_active: bool = False
        self._last_config_update: datetime | None = None

    @property
    def client(self) -> AsyncOAuth2Client:
        """Return the OAuth client."""
        return self._client

    @client.setter
    def client(self, value: AsyncOAuth2Client):
        self._client = value

    @property
    def machine_info(self) -> dict[str, str]:
        """Return info regarding the machine."""
        return self._machine_info

    @property
    def model_name(self) -> str:
        """Return the model name of the machine."""
        return self._machine_info[MODEL_NAME]

    @property
    def serial_number(self) -> str:
        """Return the serial number of the machine."""
        return self.machine_info[SERIAL_NUMBER]

    @property
    def firmware_version(self) -> str:
        """Return the firmware version of the machine."""
        return self._firmware.get("machine_firmware", {}).get("version")

    @property
    def latest_firmware_version(self) -> str:
        """Return the latest available firmware version of the machine."""
        return self._firmware.get("machine_firmware", {}).get("targetVersion")

    @property
    def gateway_version(self) -> str:
        """Return the gateway version of the machine."""
        return self._firmware.get("gateway_firmware", {}).get("version")

    @property
    def latest_gateway_version(self) -> str:
        """Return the latest available gateway version of the machine."""
        return self._firmware.get("gateway_firmware", {}).get("targetVersion")

    @property
    def date_received(self) -> datetime | None:
        """Return the date when the last update was received."""
        return self._date_received

    @property
    def websocket_terminating(self) -> bool:
        """Return the value from the local API."""
        if self._lm_local_api:
            return self._lm_local_api.terminating
        return False

    @websocket_terminating.setter
    def websocket_terminating(self, value):
        """Set the value of the local API."""
        if self._lm_local_api:
            self._lm_local_api.terminating = value

    @property
    def config(self) -> dict[str, Any]:
        """Return the config with capitalized keys to be consistent across local/remote APIs."""
        return self._config

    @property
    def power(self) -> bool:
        """Return the power state of the machine."""
        return True if self.config.get(MACHINE_MODE, False) == "BrewingMode" else False

    @property
    def steam_boiler_enabled(self) -> bool:
        """Return the steam boiler state of the machine."""
        return self._config_steamboiler.get("isEnabled", False)

    @property
    def is_heating(self) -> bool:
        """Return whether the machine is currently heating."""
        coffee_heating = (
            float(self._config_coffeeboiler.get("current", 0))
            < float(self._config_coffeeboiler.get("target", 0))
        ) and self.power
        steam_heating = (
            float(self._config_steamboiler.get("current", 0))
            < float(self._config_steamboiler.get("target", 0))
            and self.power
            and self.steam_boiler_enabled
        )
        return coffee_heating or steam_heating

    @property
    def brew_active(self) -> bool:
        """Return whether the machine is currently brewing."""
        return self._brew_active

    @property
    def heating_state(self) -> list:
        """Return the heating state of the machine."""
        return [
            "heating_on" if self.power else "heating_off",
            "steam_heater_on" if self.steam_boiler_enabled else "steam_heater_off",
        ]

    @property
    def statistics(self) -> list[dict[str, Any]]:
        """Return the statistics of the machine."""
        return self._statistics

    @property
    def schedule(self) -> list[dict[str, Any]]:
        """Return the schedule of the machine."""
        return schedule_out_to_in(self.config[WEEKLY_SCHEDULING_CONFIG])

    @property
    def current_status(self) -> dict[str, Any]:
        """Return the current status of the machine."""
        # extend the current status from super with active brew property
        self._current_status[BREW_ACTIVE] = self.brew_active
        self._current_status["coffee_boiler_on"] = self._current_status.get(
            "power", False
        )
        self._current_status["steam_boiler_on"] = self._current_status.get(
            "steam_boiler_enable", False
        ) and self._current_status.get("power", False)
        return self._current_status

    @classmethod
    async def create(
        cls, credentials: dict[str, str], machine_serial: str | None = None
    ) -> LMCloud:
        """Initialize a cloud only client"""
        self = cls()
        await self._init_cloud_api(credentials, machine_serial)
        return self

    @classmethod
    async def create_with_local_api(
        cls,
        credentials: dict[str, str],
        host: str,
        machine_serial: str | None = None,
        port: int = DEFAULT_PORT,
        use_websocket: bool = False,
        use_bluetooth: bool = False,
        bluetooth_scanner: BaseBleakScanner | None = None,
    ) -> LMCloud:
        """Also initialize a local API client"""
        self = cls()
        await self._init_cloud_api(credentials, machine_serial)
        await self._init_local_api(host, port)

        if use_websocket:
            await self._init_websocket()

        if use_bluetooth:
            await self._init_bluetooth(
                credentials["username"], bluetooth_scanner=bluetooth_scanner
            )

        await self.update_local_machine_status(in_init=True)
        return self

    async def get_all_machines(
        self, credentials: dict[str, Any]
    ) -> list[tuple[str, str]]:
        """Get a list of tuples (serial, model_name) of all machines for a user"""
        await self._connect(credentials)
        data = await self._rest_api_call(url=CUSTOMER_URL, verb="GET")
        machines: list[tuple[str, str]] = []
        for machine in data.get("fleet", []):
            machine_details = machine.get("machine", {})
            machines.append(
                (
                    machine_details.get("serialNumber"),
                    machine_details.get("model", {}).get("name"),
                )
            )
        return machines

    async def check_local_connection(
        self,
        credentials: dict[str, Any],
        host: str,
        serial: str | None = None,
        port: int = DEFAULT_PORT,
    ) -> bool:
        """Check if we can connect to the local API"""
        try:
            await self._connect(credentials)
        except AuthFail:
            return False
        try:
            machine_info = await self._get_machine_info(serial)
        except MachineNotFound:
            return False
        self._lm_local_api = LMLocalAPI(host, machine_info[KEY], port)
        try:
            await self._lm_local_api.local_get_config()
            return True
        except RequestNotSuccessful:
            return False

    async def _init_cloud_api(
        self, credentials: dict[str, str], machine_serial: str | None = None
    ) -> None:
        """Setup the cloud connection."""
        self.client = await self._connect(credentials)
        self._machine_info = await self._get_machine_info(machine_serial)
        self._gw_url_with_serial = (
            GW_MACHINE_BASE_URL + "/" + self.machine_info[SERIAL_NUMBER]
        )
        self._firmware = await self.get_firmware()
        self._date_received = datetime.now()

    async def _init_local_api(self, host: str, port: int = DEFAULT_PORT) -> None:
        """Init local connection client"""
        self._lm_local_api = LMLocalAPI(
            host=host, local_port=port, local_bearer=self.machine_info[KEY]
        )

    async def _init_websocket(self) -> None:
        """Initiate the local websocket connection"""
        _logger.debug("Initiating lmcloud with WebSockets")
        self._use_websocket = True
        assert self._lm_local_api
        asyncio.create_task(self._lm_local_api.websocket_connect())

    async def _init_bluetooth(
        self,
        username: str,
        init_client: bool = True,
        bluetooth_scanner: BaseBleakScanner | None = None,
    ):
        """Initiate the Bluetooth connection"""
        try:
            self._lm_bluetooth = await LMBluetooth.create(
                username=username,
                serial_number=self.machine_info[SERIAL_NUMBER],
                token=self.machine_info[KEY],
                init_client=init_client,
                bleak_scanner=bluetooth_scanner,
            )
        except BluetoothDeviceNotFound as e:
            _logger.warning(
                "Could not find bluetooth device."
                + "Bluetooth commands will not be available"
                + "and commands will all be sent through cloud"
            )
            _logger.debug("Full error: %s", e)
        except BleakError as e:
            _logger.warning(
                "Bleak encountered an error while trying to connect to bluetooth device."
                + "Maybe no bluetooth adapter is available?"
                + "Bluetooth commands will not be available"
                + "and commands will all be sent through cloud"
            )
            _logger.debug("Full error: %s", e)

    async def _init_bluetooth_with_known_device(
        self, username: str, address: str, name: str
    ) -> None:
        """Initiate the Bluetooth connection with a known device"""
        self._lm_bluetooth = await LMBluetooth.create_with_known_device(
            username=username,
            serial_number=self.machine_info[SERIAL_NUMBER],
            token=self.machine_info[KEY],
            address=address,
            name=name,
        )

    async def _connect(self, credentials: dict[str, str]) -> AsyncOAuth2Client:
        """Establish connection by building the OAuth client and requesting the token"""

        client = AsyncOAuth2Client(
            client_id=credentials["client_id"],
            client_secret=credentials["client_secret"],
            token_endpoint=TOKEN_URL,
        )

        headers = {
            "client_id": credentials["client_id"],
            "client_secret": credentials["client_secret"],
        }

        try:
            await client.fetch_token(
                url=TOKEN_URL,
                username=credentials["username"],
                password=credentials["password"],
                headers=headers,
            )
            return client

        except OAuthError as err:
            raise AuthFail("Authorization failure") from err

    async def websocket_connect(
        self,
        callback: Callable[[str, Any], None] | None = None,
        use_sigterm_handler: bool = True,
    ) -> None:
        """Connect to the local websocket"""
        assert self._lm_local_api
        await self._lm_local_api.websocket_connect(callback, use_sigterm_handler)

    def update_current_status(self, property_updated: str, value: Any):
        """Update a property in the current status dict"""
        if property_updated != BREW_ACTIVE:
            self._current_status[property_updated] = value
        else:
            self._brew_active = value

    async def get_config(self) -> dict[str, Any]:
        """Get configuration from cloud"""

        url = f"{self._gw_url_with_serial}/configuration"
        try:
            config = await self._rest_api_call(url=url, verb="GET")
            return config
        except RequestNotSuccessful as e:
            _logger.warning("Could not get config from cloud. Full error: %s", e)
            return self._config

    async def _update_config_obj(self, force_update: bool = False) -> None:
        """Load the config into variables in this class"""

        if self._config and not bool(self._config):
            # wait at least 10 seconds between config updates to not flood the remote API
            if (
                self._last_config_update
                and (datetime.now() - self._last_config_update).total_seconds()
                < POLLING_DELAY_S
            ) and not force_update:
                return
        config = await self.get_config()
        if config and bool(config):
            self._config = config
        self._last_config_update = datetime.now()

    async def update_local_machine_status(
        self,
        in_init: bool = False,
        force_update: bool = False,
        local_api_retry_delay: int = 3,
    ) -> None:
        """Get an update for all raw config objects from cloud or local API"""

        if self._lm_local_api:
            try:
                try:
                    _logger.debug("Getting config from local API")
                    self._config = await self._lm_local_api.local_get_config()
                except AuthFail:
                    _logger.debug(
                        "Got 403 from local API, sending token request to cloud"
                    )
                    await self._token_command()
                    await asyncio.sleep(local_api_retry_delay)
                    self._config = await self._lm_local_api.local_get_config()
            except RequestNotSuccessful as e:
                _logger.warning("Could not connect to local API although initialized")
                _logger.debug("Full error: %s", e)
                await self._update_config_obj(force_update=force_update)

            if (
                self._lm_local_api.timestamp_last_websocket_msg is None
                or (
                    datetime.now() - self._lm_local_api.timestamp_last_websocket_msg
                ).total_seconds()
                > 30
            ):
                if (
                    self._use_websocket and not in_init
                ):  # during init we don't want to log this warning
                    _logger.warning(
                        "Could not get local machine status. Falling back to cloud status"
                    )
        else:
            _logger.debug("Getting config from cloud.")
            await self._update_config_obj(force_update=force_update)

        self._config_coffeeboiler = next(
            (
                item
                for item in self.config.get(BOILERS, [])
                if item["id"] == COFFEE_BOILER_NAME
            ),
            {},
        )
        self._config_steamboiler = next(
            (
                item
                for item in self.config.get(BOILERS, [])
                if item["id"] == STEAM_BOILER_NAME
            ),
            {},
        )

        await self._update_statistics_obj(force_update=force_update)
        self._date_received = datetime.now()
        self._current_status = self._build_current_status()

    async def get_statistics(self) -> list[dict[str, Any]]:
        """Get statistics from cloud."""
        _logger.debug("Getting statistics from cloud")

        url = f"{self._gw_url_with_serial}/statistics/counters"
        try:
            statistics = await self._rest_api_call(url=url, verb="GET")
            return statistics
        except RequestNotSuccessful as e:
            _logger.warning("Could not get statistics from cloud. Full error: %s", e)
            return self._statistics

    async def _update_statistics_obj(self, force_update: bool = False) -> None:
        if self._statistics:
            # wait at least 10 seconds between config updates to not flood the remote API
            if (
                (self._last_statistics_update is not None)
                and (datetime.now() - self._last_statistics_update).total_seconds()
                < POLLING_DELAY_STATISTICS_S
                and not force_update
            ):
                return
        self._statistics = await self.get_statistics()
        self._last_statistics_update = datetime.now()

    async def _rest_api_call(
        self, url: str, verb: str = "GET", data: Any | None = None
    ) -> Any:
        """Wrapper for the API call."""

        # make sure oauth token is still valid
        if self.client.token.is_expired():
            await self.client.refresh_token(TOKEN_URL)

        # make API call
        if verb == "GET":
            response = await self.client.get(url)
        elif verb == "POST":
            response = await self.client.post(url, json=data)
        else:
            raise NotImplementedError(
                f"Wrapper function for Verb {verb} not implemented yet!"
            )

        # ensure status code indicates success
        if response.is_success:
            return response.json()["data"]

        raise RequestNotSuccessful(
            f"Request to endpoint {response.url} failed with status code {response.status_code}"
        )

    async def _send_bluetooth_command(
        self, func: Callable[[Any], Coroutine[Any, None, None]], param: Any
    ) -> bool:
        """Wrapper for bluetooth commands."""
        if self._lm_bluetooth is None or self._lm_bluetooth.client is None:
            return False

        try:
            await func(param)
            return True
        except (BleakError, BluetoothConnectionFailed) as e:
            _logger.warning(
                "Could not send command to bluetooth device, even though initalized."
                + "Falling back to cloud"
            )
            _logger.debug("Full error: %s", e)
            return False

    async def _get_machine_info(self, serial: str | None = None) -> dict[str, str]:
        """Get basic machine info from the customer endpoint."""

        machine_info: dict[str, Any] = {}
        machine_data: dict[str, Any] = {}

        data = await self._rest_api_call(url=CUSTOMER_URL, verb="GET")
        fleet = data.get("fleet", [])
        if serial is not None:
            machine_with_serial = [
                m for m in fleet if m.get("machine", {}).get("serialNumber") == serial
            ]
            if not machine_with_serial:
                raise MachineNotFound(f"Serial number {serial} not found")
            machine_data = machine_with_serial[0]
        else:
            machine_data = fleet[0]
        machine_info[KEY] = machine_data.get("communicationKey")
        machine_info[MACHINE_NAME] = machine_data.get("name")
        machine = machine_data.get("machine", {})
        machine_info[SERIAL_NUMBER] = machine.get("serialNumber")
        machine_info[MODEL_NAME] = machine.get("model", {}).get("name")

        return machine_info

    async def get_firmware(self) -> dict[str, Any]:
        """Get Firmware details."""

        url = f"{self._gw_url_with_serial}/firmware/"
        return await self._rest_api_call(url=url, verb="GET")

    async def set_power(self, enabled: bool) -> None:
        """Turn power of machine on or off"""

        if self._lm_bluetooth is not None:
            bt_ok = await self._send_bluetooth_command(
                self._lm_bluetooth.set_power, enabled
            )

        mode = "BrewingMode" if enabled else "StandBy"

        if not self._lm_bluetooth or not bt_ok:
            data = {"status": mode}
            url = f"{self._gw_url_with_serial}/status"
            await self._rest_api_call(url=url, verb="POST", data=data)

        self._config[MACHINE_MODE] = mode

    async def set_steam(self, steam_state: bool) -> None:
        """Turn Steamboiler on or off"""

        if not isinstance(steam_state, bool):
            msg = "Steam state must be boolean"
            _logger.debug(msg)
            raise TypeError(msg)

        if self._lm_bluetooth is not None:
            bt_ok = await self._send_bluetooth_command(
                self._lm_bluetooth.set_steam, steam_state
            )

        if not self._lm_bluetooth or not bt_ok:
            data = {"identifier": STEAM_BOILER_NAME, "state": steam_state}
            url = f"{self._gw_url_with_serial}/enable-boiler"
            await self._rest_api_call(url=url, verb="POST", data=data)

        idx = [STEAM_BOILER_NAME in i["id"] for i in self.config[BOILERS]].index(True)
        self._config[BOILERS][idx]["isEnabled"] = steam_state

    async def set_steam_temp(self, temperature: int) -> None:
        """Set steamboiler temperature (in Celsius)."""
        if not isinstance(temperature, int):
            msg = "Steam temp must be integer"
            _logger.debug(msg)
            raise TypeError(msg)

        if not temperature == 131 and not temperature == 128 and not temperature == 126:
            msg = "Steam temp must be one of 126, 128, 131 (°C)"
            _logger.debug(msg)
            raise ValueError(msg)

        if self._lm_bluetooth is not None:
            bt_ok = await self._send_bluetooth_command(
                self._lm_bluetooth.set_steam_temp, temperature
            )

        if not self._lm_bluetooth or not bt_ok:
            data = {"identifier": STEAM_BOILER_NAME, "value": temperature}
            url = f"{self._gw_url_with_serial}/target-boiler"
            await self._rest_api_call(url=url, verb="POST", data=data)

        self._config[BOILER_TARGET_TEMP][STEAM_BOILER_NAME] = temperature

    async def set_coffee_temp(self, temperature) -> None:
        """Set coffee boiler temperature (in Celsius)."""

        if temperature > 104 or temperature < 85:
            msg = "Coffee temp must be between 85 and 104 (°C)"
            _logger.debug(msg)
            raise ValueError(msg)

        temperature = round(temperature, 1)

        if self._lm_bluetooth is not None:
            bt_ok = await self._send_bluetooth_command(
                self._lm_bluetooth.set_coffee_temp, temperature
            )

        if not self._lm_bluetooth or not bt_ok:
            data = {"identifier": COFFEE_BOILER_NAME, "value": temperature}
            url = f"{self._gw_url_with_serial}/target-boiler"
            await self._rest_api_call(url=url, verb="POST", data=data)

        self._config[BOILER_TARGET_TEMP][COFFEE_BOILER_NAME] = temperature

    async def _set_pre_brew_infusion(self, mode: str) -> None:
        """Enable/Disable Pre-Brew or Pre-Infusion (mutually exclusive)."""

        if not mode in ("Disabled", "TypeB", "Enabled"):
            msg = (
                "Pre-Infusion/Pre-Brew can only be TypeB (PreInfusion), "
                "Enabled (Pre-Brew) or Disabled"
            )
            _logger.debug(msg)
            raise ValueError(msg)
        if mode == "TypedB" and not self.config[PLUMBED_IN]:
            msg = "Pre-Infusion can only be enabled when plumbin is enabled."
            _logger.debug(msg)
            raise ValueError(msg)

        url = f"{self._gw_url_with_serial}/enable-preinfusion."
        data = {"mode": mode}
        await self._rest_api_call(url=url, verb="POST", data=data)
        self._config[PRE_INFUSION_SETTINGS]["mode"] = mode

    async def set_prebrew(self, enabled: bool) -> None:
        """Enable/Disable Pre-brew (Mode = Enabled)."""

        mode = "Enabled" if enabled else "Disabled"
        await self._set_pre_brew_infusion(mode)

    async def set_preinfusion(self, enabled: bool) -> None:
        """Enable/Disable Pre-Infusion (Mode = TypeB)."""

        mode = "TypeB" if enabled else "Disabled"
        await self._set_pre_brew_infusion(mode)

    async def configure_prebrew(
        self, on_time=5000, off_time=5000, key: int = 1
    ) -> None:
        """Set Pre-Brew details. Also used for preinfusion (prebrewOnTime=0, prebrewOnTime=ms)."""

        if not isinstance(on_time, int) or not isinstance(off_time, int):
            msg = "Prebrew times must be in ms (integer)"
            _logger.debug(msg)
            raise TypeError(msg)

        if key < 1 or key > 4:
            msg = f"Key must be an integer value between 1 and 4, was {key}"
            _logger.debug(msg)
            raise ValueError(msg)

        if on_time % 100 != 0 or off_time % 100 != 0:
            msg = "Prebrew times must be multiple of 100"
            _logger.debug(msg)
            raise ValueError(msg)

        button = f"Dose{chr(key + 64)}"

        url = f"{self._gw_url_with_serial}/setting-preinfusion"
        data = {
            "button": button,
            "group": "Group1",
            "holdTimeMs": off_time,
            "wetTimeMs": on_time,
        }
        await self._rest_api_call(url=url, verb="POST", data=data)

        self._config[PRE_INFUSION_SETTINGS]["Group1"][0]["preWetTime"] = on_time % 1000
        self._config[PRE_INFUSION_SETTINGS]["Group1"][0]["preWetHoldTime"] = (
            off_time % 1000
        )

    async def enable_plumbin(self, enable: bool) -> None:
        """Enable or disable plumbin mode"""

        if not isinstance(enable, bool):
            msg = "Enable param must be boolean"
            _logger.debug(msg)
            raise TypeError(msg)

        data = {"enable": enable}
        url = f"{self._gw_url_with_serial}/enable-plumbin"
        await self._rest_api_call(url=url, verb="POST", data=data)
        self._config[PLUMBED_IN] = enable

    async def set_dose(self, key: int, value: int) -> None:
        """Set the value for a dose"""

        if key < 1 or key > 4:
            msg = f"Key must be an integer value between 1 and 4, was {key}"
            _logger.debug(msg)
            raise ValueError(msg)

        dose_index = f"Dose{chr(key + 64)}"

        url = f"{self._gw_url_with_serial}/dose"
        data = {
            "dose_index": dose_index,
            "dose_type": "PulsesType",
            "group": "Group1",
            "value": value,
        }

        await self._rest_api_call(url=url, verb="POST", data=data)
        if (
            "groupCapabilities" in self._config
            and len(self._config["groupCapabilities"]) > 0
            and "doses" in self._config["groupCapabilities"][0]
        ):
            idx = next(
                index
                for index, dose in enumerate(
                    self._config["groupCapabilities"][0]["doses"]
                )
                if dose.get("doseIndex") == dose_index
            )
            self._config["groupCapabilities"][0]["doses"][idx]["stopTarget"] = value

    async def set_dose_hot_water(self, value: int) -> None:
        """Set the value for the hot water dose"""
        url = f"{self._gw_url_with_serial}/dose-tea"
        data = {"dose_index": "DoseA", "value": value}
        await self._rest_api_call(url=url, verb="POST", data=data)
        self._config["teaDoses"]["DoseA"]["stopTarget"] = value

    async def configure_schedule(
        self, enable: bool, schedule: list[dict[str, Any]]
    ) -> None:
        """Set auto-on/off schedule"""
        url = f"{self._gw_url_with_serial}/scheduling"
        data = {"enable": enable, "days": schedule}
        await self._rest_api_call(url=url, verb="POST", data=data)
        self._config[WEEKLY_SCHEDULING_CONFIG] = schedule_in_to_out(enable, schedule)

    async def set_auto_on_off(
        self,
        day_of_week: str,
        hour_on: int,
        minute_on: int,
        hour_off: int,
        minute_off: int,
    ) -> None:
        """Set auto-on/off for a day of the week"""
        schedule = self.schedule
        idx = [
            index
            for (index, d) in enumerate(schedule)
            if d["day"][0:3] == day_of_week[0:3].upper()
        ][0]
        schedule[idx]["enable"] = True
        schedule[idx]["on"] = f"{hour_on:02d}:{minute_on:02d}"
        schedule[idx]["off"] = f"{hour_off:02d}:{minute_off:02d}"
        await self.configure_schedule(
            self.config[WEEKLY_SCHEDULING_CONFIG]["enabled"], schedule
        )

    async def set_auto_on_off_enable(self, day_of_week: str, enable: bool) -> None:
        """Enable or disable auto-on/off for a day of the week"""
        schedule = self.schedule
        idx = [
            index
            for (index, d) in enumerate(schedule)
            if d["day"][0:3] == day_of_week[0:3].upper()
        ][0]
        schedule[idx]["enable"] = enable
        await self.configure_schedule(
            self.config[WEEKLY_SCHEDULING_CONFIG]["enabled"], schedule
        )

    async def start_backflush(self) -> None:
        """Send command to start backflushing"""
        url = f"{self._gw_url_with_serial}/enable-backflush"
        data = {"enable": True}
        await self._rest_api_call(url=url, verb="POST", data=data)
        self._config[BACKFLUSH_ENABLED] = True

    async def _token_command(self) -> None:
        """Send token request command to cloud. This is needed when the local API returns 403."""
        url = f"{self._gw_url_with_serial}/token-request"
        response = await self._rest_api_call(url=url, verb="GET")
        command_id = response.get("commandId")
        if command_id is None:
            return

        url = f"{GW_AWS_PROXY_BASE_URL}/{self.serial_number}/commands/{command_id}"
        await self._rest_api_call(url=url, verb="GET")

    def _build_current_status(self) -> dict[str, Any]:
        """Build object which holds status for lamarzocco Home Assistant Integration"""
        state = {
            "power": self.power,
            "enable_prebrewing": True
            if self.config.get(PRE_INFUSION_SETTINGS, {}).get("mode") == "Enabled"
            else False,
            "enable_preinfusion": True
            if self.config.get(PRE_INFUSION_SETTINGS, {}).get("mode") == "TypeB"
            else False,
            "steam_boiler_enable": self.steam_boiler_enabled,
            "global_auto": self.config.get(WEEKLY_SCHEDULING_CONFIG, {}).get(
                "enabled", False
            ),
            "coffee_temp": self._config_coffeeboiler.get(CURRENT, 0),
            "coffee_set_temp": self._config_coffeeboiler.get(TARGET, 0),
            "steam_temp": self._config_steamboiler.get(CURRENT, 0),
            "steam_set_temp": self._config_steamboiler.get(TARGET, 0),
            "water_reservoir_contact": self.config.get(TANK_STATUS, False),
            "plumbin_enable": self.config.get(PLUMBED_IN, False),
            "date_received:": self.date_received,
            "machine_name": self.machine_info.get(MACHINE_NAME),
            "model_name": self.machine_info.get(MODEL_NAME),
            "update_available": self.firmware_version != self.latest_firmware_version,
            "heating_state": self.heating_state,
        }

        doses = parse_doses(self.config)
        preinfusion_settings = parse_preinfusion_settings(self.config)
        schedule = schedule_out_to_hass(self.config)
        statistics = parse_statistics(self.statistics)
        return state | doses | preinfusion_settings | schedule | statistics
