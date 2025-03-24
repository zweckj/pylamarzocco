"""La Marzocco Cloud API Client."""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable
from http import HTTPMethod
from typing import Any

from aiohttp import (
    ClientConnectionError,
    ClientSession,
    ClientTimeout,
    ClientWebSocketResponse,
    ClientWSTimeout,
    WSMsgType,
    WSMessage,
)
from aiohttp.client_exceptions import ClientError, InvalidURL

from pylamarzocco.const import (
    BASE_URL,
    CUSTOMER_APP_URL,
    SteamTargetLevel,
    StompMessageType,
    PreExtractionMode,
    DoseIndexType,
    SmartStandByType,
)
from pylamarzocco.exceptions import AuthFail, RequestNotSuccessful
from pylamarzocco.models.authentication import (
    AccessToken,
    RefreshTokenRequest,
    SigninTokenRequest,
)
from pylamarzocco.models.config import (
    DashboardDeviceConfig,
    DashboardWSConfig,
    Device,
    DeviceSettings,
    SecondsInOut,
    PrebrewSettingTimes,
)
from pylamarzocco.models.schedule import WakeUpScheduleSettings
from pylamarzocco.models.statistics import Statistics
from pylamarzocco.models.general import CommandResponse, WebSocketDetails
from pylamarzocco.util import (
    decode_stomp_ws_message,
    encode_stomp_ws_message,
    is_success,
)

_LOGGER = logging.getLogger(__name__)


TOKEN_TIME_TO_REFRESH = 4 * 60 * 60  # 4 hours


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

    async def get_thing_statistics(self, serial_number: str) -> Statistics:
        """Get the statistics of a thing."""
        url = f"{CUSTOMER_APP_URL}/things/{serial_number}/stats"
        result = await self._rest_api_call(url=url, method=HTTPMethod.GET)
        return Statistics.from_dict(result)

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

    async def __handle_websocket_message(self, ws: ClientWebSocketResponse, msg: WSMessage) -> bool:
        """Handle receiving a websocket message. Return True for disconnect."""
        if msg.type in (WSMsgType.CLOSING, WSMsgType.CLOSED):
            _LOGGER.debug("Websocket disconnected gracefully")
            self.websocket.disconnected = True
            return True
        if msg.type == WSMsgType.ERROR:
            _LOGGER.warning(
                "Websocket disconnected with error %s", ws.exception()
            )
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
        if self.notification_callback is not None:
            self.notification_callback(config)

    # endregion
    # region Commands
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
        return CommandResponse.from_dict(response[0])

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
        return CommandResponse.from_dict(response[0])

    async def set_steam_target_level(
        self,
        serial_number: str,
        target_level: SteamTargetLevel,
        boiler_index: int = 1,
    ) -> CommandResponse:
        """Set Steamboiler target level"""

        data = {
            "boilerIndex": boiler_index,
            "targetLevel": target_level.value,
        }
        url = f"{CUSTOMER_APP_URL}/things/{serial_number}/command/CoffeeMachineSettingSteamBoilerTargetLevel"
        response = await self._rest_api_call(url=url, method=HTTPMethod.POST, data=data)
        return CommandResponse.from_dict(response[0])

    async def start_backflush_cleaning(
        self,
        serial_number: str,
    ) -> CommandResponse:
        """Start backflush cleaning"""

        data = {"enabled": True}
        url = f"{CUSTOMER_APP_URL}/things/{serial_number}/command/CoffeeMachineBackFlushStartCleaning"
        response = await self._rest_api_call(url=url, method=HTTPMethod.POST, data=data)
        return CommandResponse.from_dict(response[0])

    async def change_pre_extraction_mode(
        self, serial_number: str, prebrew_mode: PreExtractionMode
    ) -> CommandResponse:
        """Change pre-extraction mode"""

        data = {
            "mode": prebrew_mode.value,
        }
        url = f"{CUSTOMER_APP_URL}/things/{serial_number}/command/CoffeeMachinePreBrewingChangeMode"
        response = await self._rest_api_call(url=url, method=HTTPMethod.POST, data=data)
        return CommandResponse.from_dict(response[0])

    async def change_pre_extraction_times(
        self,
        serial_number: str,
        seconds_in: float,
        seconds_out: float,
        group_index: int = 1,
        dose_index: DoseIndexType = DoseIndexType.BY_GROUP,
    ) -> CommandResponse:
        """Change pre-extraction times"""

        data = PrebrewSettingTimes(
            times=SecondsInOut(
                seconds_in=round(seconds_in, 1),
                seconds_out=round(seconds_out, 1),
            ),
            group_index=group_index,
            dose_index=dose_index,
        )
        url = f"{CUSTOMER_APP_URL}/things/{serial_number}/command/CoffeeMachinePreBrewingChangeTimes"
        response = await self._rest_api_call(
            url=url, method=HTTPMethod.POST, data=data.to_dict()
        )
        return CommandResponse.from_dict(response[0])

    async def set_smart_standby(
        self, serial_number: str, enabled: bool, minutes: 10, after: SmartStandByType
    ) -> CommandResponse:
        """Set smart standby"""

        data = {"enabled": enabled, "minutes": minutes, "after": after.value}
        url = f"{CUSTOMER_APP_URL}/things/{serial_number}/command/CoffeeMachineSettingSmartStandBy"
        response = await self._rest_api_call(url=url, method=HTTPMethod.POST, data=data)
        return CommandResponse.from_dict(response[0])

    async def delete_wakeup_schedule(
        self,
        serial_number: str,
        schedule_id: str,
    ) -> CommandResponse:
        """Delete a smart wakeup schedule"""
        data = {"id": schedule_id}
        url = f"{CUSTOMER_APP_URL}/things/{serial_number}/command/CoffeeMachineDeleteWakeUpSchedule"
        response = await self._rest_api_call(url=url, method=HTTPMethod.POST, data=data)
        return CommandResponse.from_dict(response[0])

    async def set_wakeup_schedule(
        self,
        serial_number: str,
        schedule: WakeUpScheduleSettings,
    ) -> CommandResponse:
        """Set smart wakeup schedule"""
        url = f"{CUSTOMER_APP_URL}/things/{serial_number}/command/CoffeeMachineSetWakeUpSchedule"
        response = await self._rest_api_call(
            url=url, method=HTTPMethod.POST, data=schedule.to_dict()
        )
        return CommandResponse.from_dict(response[0])


# endregion
