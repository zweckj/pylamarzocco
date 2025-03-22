"""La Marzocco Cloud API Client."""

from __future__ import annotations

from collections.abc import Callable
import asyncio
import logging
import time
from datetime import datetime
from http import HTTPMethod
from typing import Any
import uuid

from aiohttp import (
    ClientSession,
    ClientWebSocketResponse,
    WSMsgType,
    ClientWSTimeout,
    ClientConnectionError,
    ClientTimeout,
)
from aiohttp.client_exceptions import ClientError, InvalidURL

from pylamarzocco.util import (
    is_success,
    encode_stomp_ws_message,
    decode_stomp_ws_message,
)
from pylamarzocco.const import (
    CUSTOMER_APP_URL,
    BASE_URL,
    StompMessageType,
)
from pylamarzocco.exceptions import AuthFail, RequestNotSuccessful
from pylamarzocco.models.authentication import TokenRequest, AccessToken
from pylamarzocco.models.general import CommandResponse
from pylamarzocco.models.config import (
    DashboardWSConfig,
    Device,
    DashboardDeviceConfig,
    DeviceSettings,
)

_LOGGER = logging.getLogger(__name__)


class LaMarzoccoCloudClient:
    """La Marzocco Cloud Client."""

    _client: ClientSession

    def __init__(
        self,
        username: str,
        password: str,
        client: ClientSession | None = None,
        notification_callback: Callable[[DashboardWSConfig], Any] | None = None,
    ) -> None:
        if client is None:
            self._client = ClientSession()
        else:
            self._client = client
        self._username = username
        self._password = password
        self._access_token: AccessToken | None = None
        self.websocket_disconnected = True
        self.websocket: ClientWebSocketResponse | None = None
        self.notification_callback: Callable[[DashboardWSConfig], Any] | None = (
            notification_callback
        )

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        if self._access_token is None or self._access_token.expires_in < time.time():
            await self._async_get_access_token()
        assert self._access_token
        if self._access_token.expires_in < time.time() + 300:
            await self._async_get_refresh_token()
        return self._access_token.access_token

    async def _async_get_access_token(self) -> None:
        """Get a new access token."""
        data = TokenRequest(username=self._username, password=self._password).to_dict()
        _LOGGER.debug("Getting new access token, data: %s", data)
        self._access_token = await self.__async_get_token(data)

    async def _async_get_refresh_token(self) -> None:
        """Refresh a access token."""
        # TODO: implement refresh token logic

    async def __async_get_token(self, data: dict[str, Any]) -> AccessToken:
        """Wrapper for a token request."""
        try:
            response = await self._client.post(
                f"{CUSTOMER_APP_URL}/auth/signin", json=data
            )
        except ClientError as ex:
            raise RequestNotSuccessful(
                "Error during HTTP request."
                + f"Request auth to endpoint failed with error: {ex}"
            ) from ex
        if is_success(response):
            json_response = await response.json()
            return AccessToken.from_dict(json_response)

        if response.status == 401:
            raise AuthFail("Invalid username or password")

        raise RequestNotSuccessful(
            f"Request t auth endpoint failed with status code {response.status}"
            + f"response: {await response.text()}"
        )

    async def _rest_api_call(
        self,
        url: str,
        method: HTTPMethod,
        data: dict[str, Any] | None = None,
        timeout: int = 5,
    ) -> dict:
        """Wrapper for the API call."""

        access_token = await self.async_get_access_token()
        headers = {"Authorization": f"Bearer {access_token}"}

        try:
            response = await self._client.request(
                method=method,
                url=url,
                json=data,
                timeout=ClientTimeout(total=timeout),
                headers=headers,
            )
        except ClientError as ex:
            raise RequestNotSuccessful(
                f"Error during HTTP request. Request to endpoint {url} failed with error: {ex}"
            ) from ex

        # ensure status code indicates success
        if is_success(response):
            json_response = await response.json()
            _LOGGER.debug("Request to %s successful", json_response)
            return json_response

        raise RequestNotSuccessful(
            f"Request to endpoint {response.url} failed with status code {response.status}"
            + f"response: {await response.text()}"
        )

    async def list_things(self) -> list[Device]:
        """Get all things."""
        url = f"{CUSTOMER_APP_URL}/things"
        result = await self._rest_api_call(url=url, method=HTTPMethod.GET)
        return [Device.from_dict(device) for device in result]

    async def get_thing_dashboard(self, serial_number: str) -> DashboardDeviceConfig:
        """Get the dashboard of a thing."""
        url = f"{CUSTOMER_APP_URL}/things/{serial_number}/dashboard"
        result = await self._rest_api_call(url=url, method=HTTPMethod.GET)
        return DashboardDeviceConfig.from_dict(result)

    async def get_thing_settings(self, serial_number: str) -> DeviceSettings:
        """Get the settings of a thing."""
        url = f"{CUSTOMER_APP_URL}/things/{serial_number}/settings"
        result = await self._rest_api_call(url=url, method=HTTPMethod.GET)
        return DeviceSettings.from_dict(result)

    async def websocket_connect(
        self,
        serial_number: str,
    ) -> None:
        """Connect to the websocket of the machine."""

        try:
            async with await self._client.ws_connect(
                f"wss://{BASE_URL}/ws/connect",
                timeout=ClientWSTimeout(ws_receive=None, ws_close=10.0),
            ) as ws:
                connect_msg = encode_stomp_ws_message(
                    StompMessageType.CONNECT,
                    {
                        "host": BASE_URL,
                        "accept-version": "1.2,1.1,1.0",
                        "heart-beat": "0,0",
                        "Authorization": f"Bearer {await self.async_get_access_token()}",
                    },
                )
                print(connect_msg)
                await ws.send_str(connect_msg)
                msg = await ws.receive()
                print(msg.data)
                result, _, _ = decode_stomp_ws_message(str(msg.data))
                if result is not StompMessageType.CONNECTED:
                    raise ClientConnectionError("No connected message")
                subscribe_msg = encode_stomp_ws_message(
                    StompMessageType.SUBSCRIBE,
                    {
                        "destination": f"/ws/sn/{serial_number}/dashboard",
                        "ack": "auto",
                        "id": str(uuid.uuid4()),
                        "content-length": "0",
                    },
                )
                print(subscribe_msg)
                await ws.send_str(subscribe_msg)
                self.websocket = ws
                if self.websocket_disconnected:
                    _LOGGER.warning("Websocket reconnected")
                    self.websocket_disconnected = False
                async for msg in ws:
                    if msg.type in (WSMsgType.CLOSING, WSMsgType.CLOSED):
                        _LOGGER.warning("Websocket disconnected gracefully")
                        self.websocket_disconnected = True
                        break
                    if msg.type == WSMsgType.ERROR:
                        _LOGGER.warning(
                            "Websocket disconnected with error %s", ws.exception()
                        )
                        self.websocket_disconnected = True
                        break
                    _LOGGER.debug("Received websocket message: %s", msg)
                    try:
                        msg_type, _, data = decode_stomp_ws_message(str(msg.data))
                        if msg_type is not StompMessageType.MESSAGE:
                            _LOGGER.warning("Non MESSAGE-type message: %s", msg.data)
                        else:
                            self.parse_websocket_message(data)
                    except Exception as ex:  # pylint: disable=broad-except
                        _LOGGER.exception("Error during callback: %s", ex)
        except TimeoutError as err:
            if not self.websocket_disconnected:
                _LOGGER.warning("Websocket disconnected: Connection timed out")
                self.websocket_disconnected = True
            _LOGGER.debug("Websocket timeout: %s", err)
        except ClientConnectionError as err:
            if not self.websocket_disconnected:
                _LOGGER.warning("Websocket disconnected: Could not connect: %s", err)
                self.websocket_disconnected = True
            _LOGGER.debug("Websocket disconnected: Could not connect: %s", err)
        except InvalidURL:
            _LOGGER.error("Invalid URL for websocket.")

    def parse_websocket_message(self, message: str | None) -> None:
        """Parse the websocket message."""
        if message is None:
            return
        config = DashboardWSConfig.from_json(message)
        if self.notification_callback is not None:
            self.notification_callback(config)

    async def set_power(
        self,
        serial_number: str,
        enabled: bool,
    ) -> CommandResponse:
        """Turn power of machine on or off"""

        mode = "BrewingMode" if enabled else "StandBy"

        data = {"mode": mode}
        url = (
            f"{CUSTOMER_APP_URL}/things/{serial_number}/command/CoffeeMachineChangeMode"
        )
        response = await self._rest_api_call(url=url, method=HTTPMethod.POST, data=data)
        return CommandResponse.from_dict(response)

    async def set_steam(
        self,
        serial_number: str,
        enabled: bool,
        boiler_index: int = 1,
    ) -> CommandResponse:
        """Turn Steamboiler on or off"""

        data = {
            "boilerIndex": boiler_index,
            "enabled": enabled,
        }
        url = f"{CUSTOMER_APP_URL}/things/{serial_number}/command/CoffeeMachineSettingSteamBoilerEnabled"
        response = await self._rest_api_call(url=url, method=HTTPMethod.POST, data=data)
        return CommandResponse.from_dict(response)

    # async def async_get_access_token(self) -> str:
    #     """Return a valid access token."""
    #     if self._access_token is None or self._access_token.expires_in < time.time():
    #         return await self._async_get_access_token()
    #     if self._access_token.expires_in < time.time() + 300:
    #         return await self._async_get_refresh_token()
    #     return self._access_token.access_token

    # async def _async_get_access_token(self) -> str:
    #     """Get a new access token."""
    #     data = {
    #         "username": self._username,
    #         "password": self._password,
    #         "grant_type": "password",
    #         "client_id": DEFAULT_CLIENT_ID,
    #         "client_secret": DEFAULT_CLIENT_SECRET,
    #     }
    #     _LOGGER.debug("Getting new access token, data: %s", data)
    #     return await self.__async_get_token(data)

    # async def _async_get_refresh_token(self) -> str:
    #     """Refresh the access token."""
    #     assert self._access_token is not None
    #     data = {
    #         "refresh_token": self._access_token.refresh_token,
    #         "grant_type": "refresh_token",
    #         "client_id": DEFAULT_CLIENT_ID,
    #         "client_secret": DEFAULT_CLIENT_SECRET,
    #     }
    #     _LOGGER.debug("Refreshing access token, data: %s", data)
    #     return await self.__async_get_token(data)

    # async def __async_get_token(self, data: dict[str, Any]) -> str:
    #     """Wrapper for a token request."""
    #     headers = {"Content-Type": "application/x-www-form-urlencoded"}
    #     try:
    #         response = await self._client.post(TOKEN_URL, data=data, headers=headers)
    #     except ClientError as ex:
    #         raise RequestNotSuccessful(
    #             "Error during HTTP request."
    #             + f"Request to endpoint {TOKEN_URL} failed with error: {ex}"
    #         ) from ex
    #     if is_success(response):
    #         json_response = await response.json()
    #         self._access_token = AccessToken(
    #             access_token=json_response["access_token"],
    #             refresh_token=json_response["refresh_token"],
    #             expires_in=time.time() + json_response["expires_in"],
    #         )
    #         _LOGGER.debug("Got new access token: %s", json_response)
    #         return json_response["access_token"]

    #     if response.status == 401:
    #         raise AuthFail("Invalid username or password")

    #     raise RequestNotSuccessful(
    #         f"Request to endpoint {TOKEN_URL} failed with status code {response.status}"
    #         + f"response: {await response.text()}"
    #     )

    # async def async_logout(self) -> None:
    #     """Logout from the cloud."""
    #     if self._access_token is None:
    #         return
    #     try:
    #         response = await self._client.post(LOGOUT_URL, data={})
    #     except ClientError as ex:
    #         raise RequestNotSuccessful(
    #             "Error during HTTP request."
    #             + f"Request to endpoint {LOGOUT_URL} failed with error: {ex}"
    #         ) from ex
    #     if not is_success(response):
    #         raise RequestNotSuccessful(
    #             f"Request to endpoint {LOGOUT_URL} failed with status code {response.status},"
    #             + "response: {await response.text()}"
    #         )
    #     self._access_token = None

    # async def get_customer_fleet(self) -> dict[str, LaMarzoccoDeviceInfo]:
    #     """Get basic machine info from the customer endpoint."""

    #     machine_info: dict[str, LaMarzoccoDeviceInfo] = {}

    #     data = await self._rest_api_call(url=CUSTOMER_URL, method=HTTPMethod.GET)
    #     fleet = data.get("fleet", [])
    #     for machine_data in fleet:
    #         key = machine_data.get("communicationKey")
    #         name = machine_data.get("name")

    #         machine = machine_data.get("machine", {})
    #         serial_number = machine.get("serialNumber")
    #         model_name = machine.get("model", {}).get("name")

    #         machine_info[serial_number] = LaMarzoccoDeviceInfo(
    #             serial_number=serial_number,
    #             name=name,
    #             communication_key=key,
    #             model=model_name,
    #         )

    #     return machine_info

    # async def get_config(self, serial_number: str) -> dict[str, Any]:
    #     """Get configuration from cloud"""

    #     url = f"{GW_MACHINE_BASE_URL}/{serial_number}/configuration"
    #     return await self._rest_api_call(url=url, method=HTTPMethod.GET)

    # async def set_temp(
    #     self,
    #     serial_number: str,
    #     boiler: BoilerType,
    #     temperature: float,
    # ) -> bool:
    #     """Set boiler temperature (in Celsius)."""

    #     data = {"identifier": boiler.value, "value": temperature}
    #     url = f"{GW_MACHINE_BASE_URL}/{serial_number}/target-boiler"
    #     response = await self._rest_api_call(url=url, method=HTTPMethod.POST, data=data)
    #     if await self._check_cloud_command_status(serial_number, response):
    #         return True

    #     return False

    # async def set_prebrew_mode(
    #     self,
    #     serial_number: str,
    #     mode: PrebrewMode,
    # ) -> bool:
    #     """Enable/Disable Pre-Brew or Pre-Infusion (mutually exclusive)."""

    #     url = f"{GW_MACHINE_BASE_URL}/{serial_number}/enable-preinfusion"
    #     data = {"mode": mode.value}
    #     response = await self._rest_api_call(url=url, method=HTTPMethod.POST, data=data)
    #     if await self._check_cloud_command_status(serial_number, response):
    #         return True
    #     return False

    # async def configure_pre_brew_infusion_time(
    #     self,
    #     serial_number: str,
    #     on_time: float,
    #     off_time: float,
    #     key: PhysicalKey,
    # ) -> bool:
    #     """Set Pre-Brew details. Also used for preinfusion (prebrewOnTime=0, prebrewOnTime=ms)."""

    #     on_time = round(on_time, 1) * 1000
    #     off_time = round(off_time, 1) * 1000
    #     button = f"Dose{key.name}"

    #     url = f"{GW_MACHINE_BASE_URL}/{serial_number}/setting-preinfusion"
    #     data = {
    #         "button": button,
    #         "group": "Group1",
    #         "holdTimeMs": int(off_time),
    #         "wetTimeMs": int(on_time),
    #     }
    #     response = await self._rest_api_call(url=url, method=HTTPMethod.POST, data=data)
    #     if await self._check_cloud_command_status(serial_number, response):
    #         return True
    #     return False

    # async def enable_plumbin(
    #     self,
    #     serial_number: str,
    #     enable: bool,
    # ) -> bool:
    #     """Enable or disable plumbin mode"""

    #     data = {"enable": enable}
    #     url = f"{GW_MACHINE_BASE_URL}/{serial_number}/enable-plumbin"
    #     response = await self._rest_api_call(url=url, method=HTTPMethod.POST, data=data)
    #     if await self._check_cloud_command_status(serial_number, response):
    #         return True
    #     return False

    # async def set_dose(
    #     self,
    #     serial_number: str,
    #     key: PhysicalKey,
    #     value: int,
    # ) -> bool:
    #     """Set the value for a dose"""

    #     dose_index = f"Dose{key.name}"

    #     url = f"{GW_MACHINE_BASE_URL}/{serial_number}/dose"
    #     data = {
    #         "dose_index": dose_index,
    #         "dose_type": "PulsesType",
    #         "group": "Group1",
    #         "value": value,
    #     }

    #     response = await self._rest_api_call(url=url, method=HTTPMethod.POST, data=data)
    #     if await self._check_cloud_command_status(serial_number, response):
    #         return True
    #     return False

    # async def set_dose_hot_water(
    #     self,
    #     serial_number: str,
    #     value: int,
    # ) -> bool:
    #     """Set the value for the hot water dose"""

    #     url = f"{GW_MACHINE_BASE_URL}/{serial_number}/dose-tea"
    #     data = {"dose_index": "DoseA", "value": value}
    #     response = await self._rest_api_call(url=url, method=HTTPMethod.POST, data=data)
    #     if await self._check_cloud_command_status(serial_number, response):
    #         return True
    #     return False

    # # async def set_schedule(
    # #     self,
    # #     serial_number: str,
    # #     schedule: LaMarzoccoCloudSchedule,
    # # ) -> bool:
    # #     """Set auto-on/off schedule"""

    # #     url = f"{GW_MACHINE_BASE_URL}/{serial_number}/scheduling"
    # #     response = await self._rest_api_call(
    # #         url=url, method=HTTPMethod.POST, data=dict(schedule)
    # #     )
    # #     if await self._check_cloud_command_status(serial_number, response):
    # #         return True
    # #     return False

    # async def set_wake_up_sleep(
    #     self, serial_number: str, wake_up_sleep_entry: LaMarzoccoWakeUpSleepEntry
    # ) -> bool:
    #     """Enable or disable wake-up sleep mode"""

    #     url = f"{GW_MACHINE_BASE_URL}/{serial_number}/wake-up-sleep/{wake_up_sleep_entry.entry_id}"
    #     data = {
    #         "days": [day.value for day in wake_up_sleep_entry.days],
    #         "enable": wake_up_sleep_entry.enabled,
    #         "id": wake_up_sleep_entry.entry_id,
    #         "steam": wake_up_sleep_entry.steam,
    #         "timeOff": wake_up_sleep_entry.time_off,
    #         "timeOn": wake_up_sleep_entry.time_on,
    #     }
    #     response = await self._rest_api_call(url=url, method=HTTPMethod.PUT, data=data)
    #     if await self._check_cloud_command_status(serial_number, response):
    #         return True
    #     return False

    # async def set_smart_standby(
    #     self,
    #     serial_number: str,
    #     enabled: bool,
    #     minutes: int,
    #     mode: SmartStandbyMode,
    # ) -> bool:
    #     """Set the smart standby configuration"""

    #     url = f"{GW_MACHINE_BASE_URL}/{serial_number}/smart-standby"
    #     response = await self._rest_api_call(
    #         url=url,
    #         method=HTTPMethod.POST,
    #         data={
    #             "enabled": enabled,
    #             "minutes": minutes,
    #             "mode": mode.value,
    #         },
    #     )
    #     if await self._check_cloud_command_status(serial_number, response):
    #         return True
    #     return False

    # async def start_backflush(self, serial_number: str) -> None:
    #     """Send command to start backflushing"""

    #     url = f"{GW_MACHINE_BASE_URL}/{serial_number}/enable-backflush"
    #     data = {"enable": True}
    #     await self._rest_api_call(url=url, method=HTTPMethod.POST, data=data)

    # async def token_command(self, serial_number: str) -> None:
    #     """Send token request command to cloud. This is needed when the local API returns 403."""

    #     url = f"{GW_MACHINE_BASE_URL}/{serial_number}/token-request"
    #     response = await self._rest_api_call(url=url, method=HTTPMethod.GET)
    #     await self._check_cloud_command_status(serial_number, response)

    # async def get_firmware(
    #     self,
    #     serial_number: str,
    # ) -> dict[FirmwareType, LaMarzoccoFirmware]:
    #     """Get Firmware details."""

    #     url = f"{GW_MACHINE_BASE_URL}/{serial_number}/firmware/"
    #     result = await self._rest_api_call(url=url, method=HTTPMethod.GET)
    #     firmware: dict[FirmwareType, LaMarzoccoFirmware] = {}
    #     for component in FirmwareType:
    #         current_version = result.get(f"{component}_firmware", {}).get("version")
    #         latest_version = result.get(f"{component}_firmware", {}).get(
    #             "targetVersion"
    #         )
    #         firmware[component] = LaMarzoccoFirmware(
    #             current_version=current_version,
    #             latest_version=latest_version,
    #         )
    #     return firmware

    # async def update_firmware(
    #     self, serial_number: str, component: FirmwareType
    # ) -> bool:
    #     """Update Firmware."""

    #     _LOGGER.debug("Updating firmware for component %s", component)
    #     url = f"{GW_MACHINE_BASE_URL}/{serial_number}/firmware/{component.value}/update"
    #     await self._rest_api_call(url=url, method=HTTPMethod.POST, data={})
    #     retry_counter = 0
    #     while retry_counter <= 20:
    #         firmware = await self.get_firmware(serial_number)

    #         if (
    #             firmware[component].current_version
    #             == firmware[component].latest_version
    #         ):
    #             _LOGGER.debug("Firmware update for component %s successful", component)
    #             return True
    #         _LOGGER.debug(
    #             "Firmware update for component %s still in progress", component
    #         )
    #         await asyncio.sleep(15)
    #         retry_counter += 1
    #     _LOGGER.debug(
    #         "Firmware update for component %s timed out waiting to finish",
    #         component,
    #     )
    #     return False

    # async def get_statistics(self, serial_number: str) -> list[dict[str, Any]]:
    #     """Get statistics from cloud."""

    #     _LOGGER.debug("Getting statistics from cloud")

    #     url = f"{GW_MACHINE_BASE_URL}/{serial_number}/statistics/counters"

    #     return await self._rest_api_call(url=url, method=HTTPMethod.GET)

    # async def get_daily_statistics(
    #     self,
    #     serial_number: str,
    #     start_date: datetime,
    #     end_date: datetime,
    #     timezone_offset: int,
    #     timezone: str,
    # ) -> list[dict[str, Any]]:
    #     """Get daily statistics from cloud."""

    #     _LOGGER.debug("Getting daily statistics from cloud")

    #     url = (
    #         f"{GW_MACHINE_BASE_URL}/{serial_number}/statistics/daily"
    #         + f"?startDate={start_date.isoformat()}"
    #         + f"&endDate={end_date.isoformat()}"
    #         + f"&timezoneOffset={timezone_offset}"
    #         + f"&timezone={timezone}"
    #     )

    #     return await self._rest_api_call(url=url, method=HTTPMethod.GET, timeout=60)

    # async def set_scale_target(
    #     self,
    #     serial_number: str,
    #     key: PhysicalKey,
    #     target: int,
    # ) -> bool:
    #     """Set the scale target."""

    #     dose_index = f"Dose{key.name}"

    #     url = f"{GW_MACHINE_BASE_URL}/{serial_number}/scale/target-dose"
    #     data = {
    #         "group": "Group1",
    #         "dose_index": dose_index,
    #         "dose_type": "MassType",
    #         "value": target,
    #     }
    #     response = await self._rest_api_call(url=url, method=HTTPMethod.POST, data=data)
    #     if await self._check_cloud_command_status(serial_number, response):
    #         return True
    #     return False

    # async def set_bbw_recipes(
    #     self,
    #     serial_number: str,
    #     targets: dict[PhysicalKey, int],
    # ) -> bool:
    #     """Configure brew by weight recipes."""
    #     data = {
    #         "recipeId": "Recipe1",
    #         "doseMode": "Mass",
    #         "recipeDoses": [
    #             {"id": key.name, "target": value} for (key, value) in targets.items()
    #         ],
    #     }

    #     url = f"{GW_MACHINE_BASE_URL}/{serial_number}/recipes/"
    #     response = await self._rest_api_call(url=url, method=HTTPMethod.PUT, data=data)
    #     if await self._check_cloud_command_status(serial_number, response):
    #         return True
    #     return False

    # async def set_active_bbw_recipe(
    #     self,
    #     serial_number: str,
    #     key: PhysicalKey,
    # ) -> bool:
    #     """Set the active brew by weight recipe."""
    #     data = {
    #         "group": "Group1",
    #         "doseIndex": "DoseA",
    #         "recipeId": "Recipe1",
    #         "recipeDose": key.name,
    #     }
    #     url = f"{GW_MACHINE_BASE_URL}/{serial_number}/recipes/active-recipe"
    #     response = await self._rest_api_call(url=url, method=HTTPMethod.POST, data=data)
    #     if await self._check_cloud_command_status(serial_number, response):
    #         return True
    #     return False
