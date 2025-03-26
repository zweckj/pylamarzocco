"""La Marzocco Cloud API Client."""

from __future__ import annotations

import logging
import time
import uuid
from asyncio import Future, wait_for
from collections.abc import Callable
from http import HTTPMethod
from typing import Any

from aiohttp import (
    ClientConnectionError,
    ClientSession,
    ClientTimeout,
    ClientWebSocketResponse,
    ClientWSTimeout,
    WSMessage,
    WSMsgType,
)
from aiohttp.client_exceptions import ClientError, InvalidURL

from pylamarzocco.const import (
    BASE_URL,
    CUSTOMER_APP_URL,
    CommandStatus,
    DoseIndexType,
    PreExtractionMode,
    SmartStandByType,
    SteamTargetLevel,
    StompMessageType,
)
from pylamarzocco.exceptions import AuthFail, RequestNotSuccessful
from pylamarzocco.models import (
    AccessToken,
    CommandResponse,
    DashboardDeviceConfig,
    DashboardWSConfig,
    PrebrewSettingTimes,
    RefreshTokenRequest,
    SecondsInOut,
    SigninTokenRequest,
    Statistics,
    Thing,
    ThingSettings,
    UpdateDetails,
    WakeUpScheduleSettings,
    WebSocketDetails,
)
from pylamarzocco.util import (
    decode_stomp_ws_message,
    encode_stomp_ws_message,
    is_success,
)

_LOGGER = logging.getLogger(__name__)


TOKEN_TIME_TO_REFRESH = 4 * 60 * 60  # 4 hours
PENDING_COMMAND_TIMEOUT = 10


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
        self.websocket = WebSocketDetails()
        self.notification_callback: Callable[[DashboardWSConfig], Any] | None = (
            notification_callback
        )
        self._pending_commands: dict[str, Future[CommandResponse]] = {}

    # region Authentication
    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        if self._access_token is None or self._access_token.expires_at < time.time():
            self._access_token = await self._async_sign_in()

        if self._access_token.expires_at < time.time() + TOKEN_TIME_TO_REFRESH:
            self._access_token = await self._async_refresh_token()

        return self._access_token.access_token

    async def _async_sign_in(self) -> AccessToken:
        """Get a new access token."""
        _LOGGER.debug("Getting new access token")
        return await self.__async_get_token(
            f"{CUSTOMER_APP_URL}/auth/signin",
            SigninTokenRequest(
                username=self._username, password=self._password
            ).to_dict(),
        )

    async def _async_refresh_token(self) -> AccessToken:
        """Refresh a access token."""
        if not self._access_token:
            raise ValueError("No access token available")
        _LOGGER.debug("Refreshing access token")
        return await self.__async_get_token(
            f"{CUSTOMER_APP_URL}/auth/refreshtoken",
            RefreshTokenRequest(
                username=self._username, refresh_token=self._access_token.refresh_token
            ).to_dict(),
        )

    async def __async_get_token(self, url: str, data: dict[str, Any]) -> AccessToken:
        """Wrapper for a token request."""
        try:
            response = await self._client.post(url=url, json=data)
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

    # endregion

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

    # region config
    async def list_things(self) -> list[Thing]:
        """Get all things."""
        url = f"{CUSTOMER_APP_URL}/things"
        result = await self._rest_api_call(url=url, method=HTTPMethod.GET)
        return [Thing.from_dict(device) for device in result]

    async def get_thing_dashboard(self, serial_number: str) -> DashboardDeviceConfig:
        """Get the dashboard of a thing."""
        url = f"{CUSTOMER_APP_URL}/things/{serial_number}/dashboard"
        result = await self._rest_api_call(url=url, method=HTTPMethod.GET)
        return DashboardDeviceConfig.from_dict(result)

    async def get_thing_settings(self, serial_number: str) -> ThingSettings:
        """Get the settings of a thing."""
        url = f"{CUSTOMER_APP_URL}/things/{serial_number}/settings"
        result = await self._rest_api_call(url=url, method=HTTPMethod.GET)
        return ThingSettings.from_dict(result)

    async def get_thing_statistics(self, serial_number: str) -> Statistics:
        """Get the statistics of a thing."""
        url = f"{CUSTOMER_APP_URL}/things/{serial_number}/stats"
        result = await self._rest_api_call(url=url, method=HTTPMethod.GET)
        return Statistics.from_dict(result)

    async def get_thing_firmware(self, serial_number: str) -> UpdateDetails:
        """Get the firmware settings of a thing."""
        url = f"{CUSTOMER_APP_URL}/things/{serial_number}/update-fw"
        result = await self._rest_api_call(url=url, method=HTTPMethod.GET)
        return UpdateDetails.from_dict(result)

    # endregion

    # region websocket
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
                await self.__setup_websocket_connection(ws, serial_number)
                async for msg in ws:
                    if await self.__handle_websocket_message(ws, msg):
                        break
        except TimeoutError as err:
            if not self.websocket.disconnected:
                _LOGGER.warning("Websocket disconnected: Connection timed out")
                self.websocket.disconnected = True
            _LOGGER.debug("Websocket timeout: %s", err)
        except ClientConnectionError as err:
            if not self.websocket.disconnected:
                _LOGGER.warning("Websocket disconnected: Could not connect: %s", err)
                self.websocket.disconnected = True
            _LOGGER.debug("Websocket disconnected: Could not connect: %s", err)
        except InvalidURL:
            _LOGGER.error("Invalid URL for websocket.")

    async def __setup_websocket_connection(
        self, ws: ClientWebSocketResponse, serial_number: str
    ) -> None:
        """Setup the websocket connection."""
        self.websocket.ws = ws

        connect_msg = encode_stomp_ws_message(
            StompMessageType.CONNECT,
            {
                "host": BASE_URL,
                "accept-version": "1.2,1.1,1.0",
                "heart-beat": "0,0",
                "Authorization": f"Bearer {await self.async_get_access_token()}",
            },
        )
        _LOGGER.debug("Connecting to websocket.")
        await ws.send_str(connect_msg)

        msg = await ws.receive()
        _LOGGER.debug("Received websocket message: %s", msg.data)
        result, _, _ = decode_stomp_ws_message(str(msg.data))
        if result is not StompMessageType.CONNECTED:
            raise ClientConnectionError("No connected message")

        _LOGGER.debug("Subscribing to websocket.")
        subscription_id = str(uuid.uuid4())
        subscribe_msg = encode_stomp_ws_message(
            StompMessageType.SUBSCRIBE,
            {
                "destination": f"/ws/sn/{serial_number}/dashboard",
                "ack": "auto",
                "id": subscription_id,
                "content-length": "0",
            },
        )
        await ws.send_str(subscribe_msg)

        async def disconnect_websocket() -> None:
            _LOGGER.debug("Disconnecting websocket")
            if ws.closed:
                return
            disconnect_msg = encode_stomp_ws_message(
                StompMessageType.UNSUBSCRIBE,
                {
                    "id": subscription_id,
                },
            )
            await ws.send_str(disconnect_msg)
            await ws.close()

        self.websocket.disconnect_callback = disconnect_websocket
        if self.websocket.disconnected:
            _LOGGER.warning("Websocket reconnected")
            self.websocket.disconnected = False

    async def __handle_websocket_message(
        self, ws: ClientWebSocketResponse, msg: WSMessage
    ) -> bool:
        """Handle receiving a websocket message. Return True for disconnect."""
        if msg.type in (WSMsgType.CLOSING, WSMsgType.CLOSED):
            _LOGGER.debug("Websocket disconnected gracefully")
            self.websocket.disconnected = True
            return True
        if msg.type == WSMsgType.ERROR:
            _LOGGER.warning("Websocket disconnected with error %s", ws.exception())
            self.websocket.disconnected = True
            return True
        _LOGGER.debug("Received websocket message: %s", msg)
        try:
            msg_type, _, data = decode_stomp_ws_message(str(msg.data))
            if msg_type is not StompMessageType.MESSAGE:
                _LOGGER.warning("Non MESSAGE-type message: %s", msg.data)
            else:
                self.__parse_websocket_message(data)
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.exception("Error during callback: %s", ex)
        return False

    def __parse_websocket_message(self, message: str | None) -> None:
        """Parse the websocket message."""
        if message is None:
            return
        config = DashboardWSConfig.from_json(message)

        # notify if there is the result for a pending command
        for command in config.commands:
            if command.id in self._pending_commands:
                self._pending_commands[command.id].set_result(command)

        # notify any external listeners
        if self.notification_callback is not None:
            self.notification_callback(config)

    # endregion
    # region commands

    async def __execute_command(
        self, serial_number: str, command: str, data: dict[str, Any] | None = None
    ) -> bool:
        """Execute a command on a machine."""
        response = await self._rest_api_call(
            url=f"{CUSTOMER_APP_URL}/things/{serial_number}/command/{command}",
            method=HTTPMethod.POST,
            data=data,
        )
        cr = CommandResponse.from_dict(response[0])
        future: Future[CommandResponse] = Future()
        self._pending_commands[cr.id] = future

        # if the websocket is closed we don't want to wait for confirmation
        if self.websocket.ws is None or self.websocket.ws.closed:
            return True

        try:
            # Wait for the future to be completed or timeout
            pending_result = await wait_for(future, PENDING_COMMAND_TIMEOUT)
        except TimeoutError:
            _LOGGER.debug("Timed out waiting for websocket condition")
            return False
        finally:
            # Clean up the future if it's still in the dictionary
            self._pending_commands.pop(cr.id, None)

        if pending_result.status is CommandStatus.SUCCESS:
            return True
        _LOGGER.debug(
            "Command to %s failed with status %s, error_details: %s",
            command,
            pending_result.status,
            pending_result.error_code or "",
        )
        return False

    async def set_power(
        self,
        serial_number: str,
        enabled: bool,
    ) -> CommandResponse:
        """Turn power of machine on or off"""

        mode = "BrewingMode" if enabled else "StandBy"

        data = {"mode": mode}
        return await self.__execute_command(
            serial_number, "CoffeeMachineChangeMode", data
        )

    async def set_steam(
        self,
        serial_number: str,
        enabled: bool,
        boiler_index: int = 1,
    ) -> bool:
        """Turn Steamboiler on or off"""

        data = {
            "boilerIndex": boiler_index,
            "enabled": enabled,
        }
        return await self.__execute_command(
            serial_number, "CoffeeMachineSettingSteamBoilerEnabled", data
        )

    async def set_steam_target_level(
        self,
        serial_number: str,
        target_level: SteamTargetLevel,
        boiler_index: int = 1,
    ) -> bool:
        """Set Steamboiler target level"""

        data = {
            "boilerIndex": boiler_index,
            "targetLevel": target_level.value,
        }
        return await self.__execute_command(
            serial_number, "CoffeeMachineSettingSteamBoilerTargetLevel", data
        )

    async def start_backflush_cleaning(
        self,
        serial_number: str,
    ) -> bool:
        """Start backflush cleaning"""

        data = {"enabled": True}
        return await self.__execute_command(
            serial_number, "CoffeeMachineBackFlushStartCleaning", data
        )

    async def change_pre_extraction_mode(
        self, serial_number: str, prebrew_mode: PreExtractionMode
    ) -> bool:
        """Change pre-extraction mode"""

        data = {
            "mode": prebrew_mode.value,
        }
        return await self.__execute_command(
            serial_number, "CoffeeMachinePreBrewingChangeMode", data
        )

    async def change_pre_extraction_times(
        self,
        serial_number: str,
        seconds_in: float,
        seconds_out: float,
        group_index: int = 1,
        dose_index: DoseIndexType = DoseIndexType.BY_GROUP,
    ) -> bool:
        """Change pre-extraction times"""

        data = PrebrewSettingTimes(
            times=SecondsInOut(
                seconds_in=round(seconds_in, 1),
                seconds_out=round(seconds_out, 1),
            ),
            group_index=group_index,
            dose_index=dose_index,
        )
        return await self.__execute_command(
            serial_number, "CoffeeMachinePreBrewingChangeTimes", data.to_dict()
        )

    async def set_smart_standby(
        self, serial_number: str, enabled: bool, minutes: int, after: SmartStandByType
    ) -> bool:
        """Set smart standby"""

        data = {"enabled": enabled, "minutes": minutes, "after": after.value}
        return await self.__execute_command(
            serial_number, "CoffeeMachineSettingSmartStandBy", data
        )

    async def delete_wakeup_schedule(
        self,
        serial_number: str,
        schedule_id: str,
    ) -> bool:
        """Delete a smart wakeup schedule"""
        data = {"id": schedule_id}
        return await self.__execute_command(
            serial_number, "CoffeeMachineDeleteWakeUpSchedule", data
        )

    async def set_wakeup_schedule(
        self,
        serial_number: str,
        schedule: WakeUpScheduleSettings,
    ) -> bool:
        """Set smart wakeup schedule"""
        return await self.__execute_command(
            serial_number, "CoffeeMachineSetWakeUpSchedule", schedule.to_dict()
        )

    async def update_firmware(
        self,
        serial_number: str,
    ) -> UpdateDetails:
        """Install firmware update."""
        url = f"{CUSTOMER_APP_URL}/things/{serial_number}/update-fw"
        response = await self._rest_api_call(url=url, method=HTTPMethod.POST)
        return UpdateDetails.from_dict(response)


# endregion
