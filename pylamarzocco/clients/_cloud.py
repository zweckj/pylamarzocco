"""La Marzocco Cloud API Client."""

from __future__ import annotations

import asyncio
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
    PreExtractionMode,
    SmartStandByType,
    SteamTargetLevel,
    StompMessageType,
    WidgetType,
)
from pylamarzocco.exceptions import AuthFail, RequestNotSuccessful
from pylamarzocco.models import (
    AccessToken,
    CoffeeAndFlushCounter,
    CoffeeAndFlushTrend,
    CommandResponse,
    LastCoffeeList,
    PrebrewSettingTimes,
    RefreshTokenRequest,
    SigninTokenRequest,
    Thing,
    ThingDashboardConfig,
    ThingDashboardWebsocketConfig,
    ThingSchedulingSettings,
    ThingSettings,
    ThingStatistics,
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


TOKEN_TIME_TO_REFRESH = 10 * 60  # 10 minutes before expiration
PENDING_COMMAND_TIMEOUT = 10


class LaMarzoccoCloudClient:
    """La Marzocco Cloud Client."""

    _client: ClientSession

    def __init__(
        self,
        username: str,
        password: str,
        client: ClientSession | None = None,
    ) -> None:
        """Set the cloud client up."""
        self._client = ClientSession() if client is None else client
        self._username = username
        self._password = password
        self._access_token: AccessToken | None = None
        self._access_token_lock = asyncio.Lock()
        self._pending_commands: dict[str, Future[CommandResponse]] = {}
        self.websocket = WebSocketDetails()

    # region Authentication
    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        async with self._access_token_lock:
            if self._access_token is None or self._access_token.expires_at < time.time():
                self._access_token = await self._async_sign_in()

            elif self._access_token.expires_at < time.time() + TOKEN_TIME_TO_REFRESH:
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
            _LOGGER.debug("Request to %s successful", url)
            _LOGGER.debug("Response: %s", json_response)
            return json_response

        if response.status == 401:
            raise AuthFail("Authentication failed.")

        raise RequestNotSuccessful(
            f"Request to endpoint {response.url} failed with status code {response.status}.\n"
            + f"Full response: {await response.text()}"
        )

    # region config
    async def list_things(self) -> list[Thing]:
        """Get all things."""
        url = f"{CUSTOMER_APP_URL}/things"
        result = await self._rest_api_call(url=url, method=HTTPMethod.GET)
        return [Thing.from_dict(device) for device in result]

    async def get_thing_dashboard(self, serial_number: str) -> ThingDashboardConfig:
        """Get the dashboard of a thing."""
        url = f"{CUSTOMER_APP_URL}/things/{serial_number}/dashboard"
        result = await self._rest_api_call(url=url, method=HTTPMethod.GET)
        return ThingDashboardConfig.from_dict(result)

    async def get_thing_settings(self, serial_number: str) -> ThingSettings:
        """Get the settings of a thing."""
        url = f"{CUSTOMER_APP_URL}/things/{serial_number}/settings"
        result = await self._rest_api_call(url=url, method=HTTPMethod.GET)
        return ThingSettings.from_dict(result)

    async def get_thing_statistics(self, serial_number: str) -> ThingStatistics:
        """Get the statistics of a thing."""
        url = f"{CUSTOMER_APP_URL}/things/{serial_number}/stats"
        result = await self._rest_api_call(url=url, method=HTTPMethod.GET)
        return ThingStatistics.from_dict(result)

    async def get_thing_firmware(self, serial_number: str) -> UpdateDetails:
        """Get the firmware settings of a thing."""
        url = f"{CUSTOMER_APP_URL}/things/{serial_number}/update-fw"
        result = await self._rest_api_call(url=url, method=HTTPMethod.GET)
        return UpdateDetails.from_dict(result)

    async def get_thing_schedule(self, serial_number: str) -> ThingSchedulingSettings:
        """Get the schedule of a thing."""
        url = f"{CUSTOMER_APP_URL}/things/{serial_number}/scheduling"
        result = await self._rest_api_call(url=url, method=HTTPMethod.GET)
        return ThingSchedulingSettings.from_dict(result)

    async def _get_thing_extended_statistics(
        self, serial_number: str, widget: WidgetType, **kwargs: Any
    ) -> dict:
        """Get the extended statistics of a thing."""
        url = f"{CUSTOMER_APP_URL}/things/{serial_number}/stats/{widget}/1"

        # Append query parameters if kwargs is provided
        if kwargs:
            query_params = "&".join(f"{key}={value}" for key, value in kwargs.items())
            url = f"{url}?{query_params}"

        result = await self._rest_api_call(url=url, method=HTTPMethod.GET, timeout=10)
        return result["output"]

    async def get_thing_coffee_and_flush_trend(
        self, serial_number: str, days: int, timezone: str
    ) -> CoffeeAndFlushTrend:
        """Get the last coffee and flush trend of a thing."""
        result = await self._get_thing_extended_statistics(
            serial_number=serial_number,
            widget=WidgetType.COFFEE_AND_FLUSH_TREND,
            days=days,
            timezone=timezone,
        )
        return CoffeeAndFlushTrend.from_dict(result)

    async def get_thing_last_coffee(
        self, serial_number: str, days: int
    ) -> LastCoffeeList:
        """Get the last coffee of a thing."""
        result = await self._get_thing_extended_statistics(
            serial_number=serial_number,
            widget=WidgetType.LAST_COFFEE,
            days=days,
        )
        return LastCoffeeList.from_dict(result)

    async def get_thing_coffee_and_flush_counter(
        self, serial_number: str
    ) -> CoffeeAndFlushCounter:
        """Get the coffee and flush counter of a thing."""
        result = await self._get_thing_extended_statistics(
            serial_number=serial_number,
            widget=WidgetType.COFFEE_AND_FLUSH_COUNTER,
        )
        return CoffeeAndFlushCounter.from_dict(result)

    # endregion

    # region websocket
    async def websocket_connect(
        self,
        serial_number: str,
        notification_callback: Callable[[ThingDashboardWebsocketConfig], Any]
        | None = None,
        connect_callback: Callable[[], Any] | None = None,
        disconnect_callback: Callable[[], Any] | None = None,
        auto_reconnect: bool = True,
    ) -> None:
        """Connect to the websocket of the machine."""
        while auto_reconnect:
            try:
                async with await self._client.ws_connect(
                    f"wss://{BASE_URL}/ws/connect",
                    timeout=ClientWSTimeout(ws_receive=None, ws_close=10.0),
                    heartbeat=15,
                ) as ws:
                    try:
                        await self.__setup_websocket_connection(ws, serial_number)
                        if connect_callback is not None:
                            connect_callback()
                        async for msg in ws:
                            if await self.__handle_websocket_message(
                                ws, msg, notification_callback
                            ):
                                break
                    except asyncio.CancelledError:
                        _LOGGER.debug("WebSocket cancellation requested")
                        await self.websocket.disconnect()
                        raise
            except TimeoutError:
                _LOGGER.warning("Websocket disconnected: Connection timed out")
            except ClientConnectionError as err:
                _LOGGER.error("Websocket disconnected: Could not connect: %s", err)
                auto_reconnect = False
            except InvalidURL:
                _LOGGER.error("Invalid URL for websocket.")
                auto_reconnect = False
            except asyncio.CancelledError:
                _LOGGER.debug("WebSocket cancellation successful")
                auto_reconnect = False
            finally:
                if disconnect_callback is not None:
                    disconnect_callback()

    async def __setup_websocket_connection(
        self,
        ws: ClientWebSocketResponse,
        serial_number: str,
    ) -> None:
        """Setup the websocket connection."""

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

        self.websocket = WebSocketDetails(ws, disconnect_websocket)

    async def __handle_websocket_message(
        self,
        ws: ClientWebSocketResponse,
        msg: WSMessage,
        notification_callback: Callable[[ThingDashboardWebsocketConfig], Any]
        | None = None,
    ) -> bool:
        """Handle receiving a websocket message. Return True for disconnect."""
        if msg.type in (WSMsgType.CLOSING, WSMsgType.CLOSED):
            _LOGGER.debug("Websocket disconnected gracefully")
            return True
        if msg.type == WSMsgType.ERROR:
            _LOGGER.warning("Websocket disconnected with error %s", ws.exception())
            return True
        _LOGGER.debug("Received websocket message: %s", msg)
        try:
            msg_type, _, data = decode_stomp_ws_message(str(msg.data))
            if msg_type is not StompMessageType.MESSAGE:
                _LOGGER.warning("Non MESSAGE-type message: %s", msg.data)
            else:
                self.__parse_websocket_message(data, notification_callback)
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.exception("Error during callback: %s", ex)
        return False

    def __parse_websocket_message(
        self,
        message: str | None,
        notification_callback: Callable[[ThingDashboardWebsocketConfig], Any]
        | None = None,
    ) -> None:
        """Parse the websocket message."""
        if message is None:
            return
        config = ThingDashboardWebsocketConfig.from_json(message)

        # notify if there is the result for a pending command
        for command in config.commands:
            if command.id in self._pending_commands:
                self._pending_commands[command.id].set_result(command)

        # notify any external listeners
        if notification_callback is not None:
            notification_callback(config)

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
        if not self.websocket.connected:
            return True

        try:
            # Wait for the future to be completed or timeout
            pending_result = await wait_for(future, PENDING_COMMAND_TIMEOUT)
        except TimeoutError:
            _LOGGER.debug("Timed out waiting for websocket condition")
            self._pending_commands.pop(cr.id, None)
            return False

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
    ) -> bool:
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
        """Turn steam boiler on or off"""

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
        """Set steam boiler target level"""

        data = {
            "boilerIndex": boiler_index,
            "targetLevel": target_level.value,
        }
        return await self.__execute_command(
            serial_number, "CoffeeMachineSettingSteamBoilerTargetLevel", data
        )

    async def set_coffee_target_temperature(
        self, serial_number: str, target_temperature: float, boiler_index: int = 1
    ) -> bool:
        """Set the target temperature for the coffee boiler."""
        data = {
            "boilerIndex": boiler_index,
            "targetTemperature": round(target_temperature, 1),
        }
        return await self.__execute_command(
            serial_number, "CoffeeMachineSettingCoffeeBoilerTargetTemperature", data
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
        times: PrebrewSettingTimes,
    ) -> bool:
        """Change pre-extraction times"""

        return await self.__execute_command(
            serial_number, "CoffeeMachinePreBrewingChangeTimes", times.to_dict()
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
