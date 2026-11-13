"""La Marzocco Cloud API Client."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from asyncio import Future, wait_for
from collections.abc import Callable
from http import HTTPMethod
from typing import Any

from aiohttp import (
    ClientConnectionError,
    ClientResponse,
    ClientSession,
    ClientTimeout,
    ClientWebSocketResponse,
    ClientWSTimeout,
    WSMessage,
    WSMsgType,
)
from aiohttp.client_exceptions import ClientError

from pylamarzocco.const import (
    BASE_URL,
    CUSTOMER_APP_URL,
    CommandStatus,
    DoseIndex,
    DoseMode,
    MachineMode,
    GrinderDoseMode,
    GrinderGrindWithMode,
    GrinderMode,
    GrinderSpeedLevelType,
    PreExtractionMode,
    ScaleType,
    SmartStandByType,
    SteamTargetLevel,
    StompMessageType,
    WeekDay,
    WidgetType,
)
from pylamarzocco.exceptions import (
    AuthFail,
    PolicyAcceptanceRequired,
    RequestNotSuccessful,
)
from pylamarzocco.models import (
    AccessToken,
    CoffeeAndFlushCounter,
    CoffeeAndFlushTrend,
    CommandResponse,
    LastCoffeeList,
    PourOverRecipe,
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
    InstallationKey,
    decode_stomp_ws_message,
    encode_stomp_ws_message,
    generate_extra_request_headers,
    generate_request_proof,
    is_success,
)

_LOGGER = logging.getLogger(__name__)


TOKEN_TIME_TO_REFRESH = 10 * 60  # 10 minutes before expiration
PENDING_COMMAND_TIMEOUT = 10


def _mask_bluetooth_token(data: Any) -> Any:
    """Return a copy of a JSON response with the Bluetooth token masked."""
    # json.loads calls object_hook for every decoded object, nested ones included
    return json.loads(
        json.dumps(data),
        object_hook=lambda obj: (
            obj | {"bleAuthToken": "**REDACTED**"} if obj.get("bleAuthToken") else obj
        ),
    )


class LaMarzoccoCloudClient:
    """La Marzocco Cloud Client."""

    _client: ClientSession

    def __init__(
        self,
        username: str,
        password: str,
        installation_key: InstallationKey,
        client: ClientSession | None = None,
    ) -> None:
        """Set the cloud client up."""
        self._client = ClientSession() if client is None else client
        self._username = username
        self._password = password
        self._installation_key = installation_key
        self._access_token: AccessToken | None = None
        self._access_token_lock = asyncio.Lock()
        self._pending_commands: dict[str, Future[CommandResponse]] = {}
        self.websocket = WebSocketDetails()

    # region Authentication
    async def async_register_client(self) -> None:
        """Register a new client."""

        headers = {
            "X-App-Installation-Id": self._installation_key.installation_id,
            "X-Request-Proof": generate_request_proof(
                self._installation_key.base_string, self._installation_key.secret
            ),
        }
        body = {
            "pk": self._installation_key.public_key_b64,
        }
        await self._request(
            HTTPMethod.POST,
            f"{CUSTOMER_APP_URL}/auth/init",
            headers=headers,
            data=body,
            auth_fail_message="Invalid username or password",
        )
        _LOGGER.info("Registration successful.")

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        async with self._access_token_lock:
            if (
                self._access_token is None
                or self._access_token.expires_at < time.time()
            ):
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
        response = await self._request(
            HTTPMethod.POST,
            url,
            headers=generate_extra_request_headers(self._installation_key),
            data=data,
            auth_fail_message="Invalid username or password",
        )
        return AccessToken.from_dict(await response.json())

    # endregion

    async def _rest_api_call(
        self,
        url: str,
        method: HTTPMethod,
        data: dict[str, Any] | None = None,
        timeout: int = 10,
    ) -> dict:
        """Wrapper for the API call."""

        access_token = await self.async_get_access_token()
        headers = {
            **generate_extra_request_headers(self._installation_key),
            "Authorization": f"Bearer {access_token}",
        }

        response = await self._request(
            method, url, headers=headers, data=data, timeout=timeout
        )
        if not (await response.read()).strip():
            _LOGGER.debug("Request to %s successful (empty response)", url)
            return {}
        json_response = await response.json()
        _LOGGER.debug("Request to %s successful", url)
        _LOGGER.debug("Response: %s", _mask_bluetooth_token(json_response))
        return json_response

    async def _request(
        self,
        method: HTTPMethod,
        url: str,
        headers: dict[str, str],
        data: dict[str, Any] | None = None,
        timeout: int = 10,
        auth_fail_message: str = "Authentication failed.",
    ) -> ClientResponse:
        """Send a request and map unsuccessful responses to exceptions."""
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

        if is_success(response):
            return response

        if response.status == 401:
            _LOGGER.debug("Authentication failed: %s", await response.text())
            raise AuthFail(auth_fail_message)

        if response.status == 403:
            text = await response.text()
            try:
                code = json.loads(text).get("code")
            except (ValueError, AttributeError):
                code = None
            if code == "USER_MUST_ACCEPT_POLICY":
                _LOGGER.debug("Policy acceptance required: %s", text)
                raise PolicyAcceptanceRequired(
                    "User must accept the latest privacy policy, "
                    "either in the La Marzocco app or via accept_privacy_policy()."
                )
            _LOGGER.debug("Access forbidden: %s", text)
            raise AuthFail("Access forbidden.")

        raise RequestNotSuccessful(
            f"Request to endpoint {response.url} failed with status code {response.status}.\n"
            + f"Full response: {await response.text()}"
        )

    # region user
    async def accept_privacy_policy(
        self,
        profile_policy: bool = False,
        commercial_policy: bool = False,
    ) -> None:
        """Accept the latest privacy policy.

        The optional profiling and commercial consents are sent alongside.
        """
        url = f"{CUSTOMER_APP_URL}/users/policy"
        data = {
            "profilePolicy": profile_policy,
            "commercialPolicy": commercial_policy,
        }
        await self._rest_api_call(url=url, method=HTTPMethod.PUT, data=data)

    # endregion

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
                    headers=generate_extra_request_headers(self._installation_key),
                ) as ws:
                    try:
                        await self.__setup_websocket_connection(ws, serial_number)
                        if connect_callback is not None:
                            connect_callback()
                        async for msg in ws:
                            if await self.__handle_websocket_message(
                                msg, notification_callback
                            ):
                                break
                    except asyncio.CancelledError:
                        _LOGGER.debug("WebSocket cancellation requested")
                        await self.websocket.disconnect()
                        raise
            except TimeoutError:
                _LOGGER.debug("Websocket disconnected: Connection timed out")
            except ClientError as err:
                _LOGGER.debug("Websocket disconnected: Could not connect: %s", err)
                auto_reconnect = False
            except asyncio.CancelledError:
                _LOGGER.debug("WebSocket cancellation successful")
                auto_reconnect = False
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Websocket disconnected with error")
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
        result, _, _ = decode_stomp_ws_message(str(msg.data))
        _LOGGER.debug("Received websocket message: %s", result)
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
        msg: WSMessage,
        notification_callback: Callable[[ThingDashboardWebsocketConfig], Any]
        | None = None,
    ) -> bool:
        """Handle receiving a websocket message. Return True for disconnect."""
        if msg.type in (WSMsgType.CLOSING, WSMsgType.CLOSED):
            _LOGGER.debug("Websocket disconnected gracefully")
            return True
        if msg.type == WSMsgType.ERROR:
            # aiohttp passes the error as msg.data; ws.exception() is unset for
            # protocol errors such as invalid UTF-8.
            _LOGGER.warning("Websocket disconnected with error: %s", msg.data)
            return True
        _LOGGER.debug("Received websocket message: %s", msg)
        try:
            msg_type, _, data = decode_stomp_ws_message(str(msg.data))
            if msg_type is StompMessageType.ERROR:
                _LOGGER.warning("Websocket error message: %s", data)
            elif msg_type is not StompMessageType.MESSAGE:
                _LOGGER.warning("Non MESSAGE-type message: %s", msg.data)
            else:
                self.__parse_websocket_message(data, notification_callback)
        except ValueError as ex:
            _LOGGER.warning(
                "Error parsing websocket message: %s. Message was: %s", ex, msg.data
            )
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.exception("Error during callback: %s", ex)
        return False

    def __parse_websocket_message(
        self,
        message: str,
        notification_callback: Callable[[ThingDashboardWebsocketConfig], Any]
        | None = None,
    ) -> None:
        """Parse the websocket message."""
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

    async def __set_enabled(
        self, serial_number: str, command: str, enabled: bool
    ) -> bool:
        """Execute a command that only toggles an enabled flag."""
        return await self.__execute_command(
            serial_number, command, {"enabled": enabled}
        )

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

        # if the websocket is closed we don't want to wait for confirmation.
        if not self.websocket.connected:
            return True

        future: Future[CommandResponse] = Future()
        self._pending_commands[cr.id] = future

        try:
            # Wait for the future to be completed or timeout
            pending_result = await wait_for(future, PENDING_COMMAND_TIMEOUT)
        except TimeoutError:
            _LOGGER.debug("Timed out waiting for websocket condition")
            return False
        finally:
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

    async def set_mode(
        self,
        serial_number: str,
        mode: MachineMode,
    ) -> bool:
        """Set the operating mode of the machine."""
        data = {"mode": str(mode)}
        return await self.__execute_command(
            serial_number, "CoffeeMachineChangeMode", data
        )

    async def set_power(
        self,
        serial_number: str,
        enabled: bool,
    ) -> bool:
        """Turn power of machine on or off"""
        return await self.set_mode(serial_number, MachineMode.from_power(enabled))

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
        return await self.__set_target_temperature(
            serial_number,
            "CoffeeMachineSettingCoffeeBoilerTargetTemperature",
            target_temperature,
            boiler_index,
        )

    async def set_steam_target_temperature(
        self, serial_number: str, target_temperature: float, boiler_index: int = 1
    ) -> bool:
        """Set the target temperature for the steam boiler."""
        return await self.__set_target_temperature(
            serial_number,
            "CoffeeMachineSettingSteamBoilerTargetTemperature",
            target_temperature,
            boiler_index,
        )

    async def __set_target_temperature(
        self,
        serial_number: str,
        command: str,
        target_temperature: float,
        boiler_index: int,
    ) -> bool:
        """Set the target temperature of a boiler."""
        data = {
            "boilerIndex": boiler_index,
            "targetTemperature": round(target_temperature, 1),
        }
        return await self.__execute_command(serial_number, command, data)

    async def set_auto_flush(self, serial_number: str, enabled: bool) -> bool:
        """Enable or disable automatic group flushing."""
        return await self.__set_enabled(
            serial_number, "CoffeeMachineSettingAutoFlushEnabled", enabled
        )

    async def set_steam_flush(self, serial_number: str, enabled: bool) -> bool:
        """Enable or disable automatic steam wand flushing."""
        return await self.__set_enabled(
            serial_number, "CoffeeMachineSettingSteamFlushEnabled", enabled
        )

    async def set_rinse_flush(self, serial_number: str, enabled: bool) -> bool:
        """Enable or disable automatic rinse flushing."""
        return await self.__set_enabled(
            serial_number, "CoffeeMachineSettingRinseFlushEnabled", enabled
        )

    async def set_hot_water_dose_enabled(
        self, serial_number: str, enabled: bool
    ) -> bool:
        """Enable or disable the hot water dose."""
        return await self.__set_enabled(
            serial_number, "CoffeeMachineSettingHotWaterDoseEnabled", enabled
        )

    async def set_cup_warmer(self, serial_number: str, enabled: bool) -> bool:
        """Enable or disable the cup warmer."""
        return await self.__set_enabled(
            serial_number, "CoffeeMachineSettingCupWarmerEnabled", enabled
        )

    async def set_group_mode(
        self, serial_number: str, mode: MachineMode, group_index: int = 1
    ) -> bool:
        """Set the operating mode of a single group."""
        data = {"groupIndex": group_index, "mode": mode.value}
        return await self.__execute_command(
            serial_number, "CoffeeMachineGroupChangeMode", data
        )

    async def set_coffee_boiler(
        self, serial_number: str, enabled: bool, boiler_index: int = 1
    ) -> bool:
        """Enable or disable the coffee boiler."""
        data = {"boilerIndex": boiler_index, "enabled": enabled}
        return await self.__execute_command(
            serial_number, "CoffeeMachineSettingCoffeeBoilerEnabled", data
        )

    async def set_rinse_flush_time(self, serial_number: str, seconds: float) -> bool:
        """Set the duration of the automatic rinse flush."""
        data = {"timeSeconds": round(seconds, 1)}
        return await self.__execute_command(
            serial_number, "CoffeeMachineSettingRinseFlushTime", data
        )

    async def set_hot_water_dose(
        self, serial_number: str, dose: float, dose_index: DoseIndex
    ) -> bool:
        """Set a hot water dose value."""
        data = {"doseIndex": dose_index.value, "dose": round(dose, 1)}
        return await self.__execute_command(
            serial_number, "CoffeeMachineSettingHotWaterDose", data
        )

    async def set_group_dose_mode(
        self, serial_number: str, mode: DoseMode, group_index: int = 1
    ) -> bool:
        """Set the dose mode of a group."""
        data = {"groupIndex": group_index, "mode": mode.value}
        return await self.__execute_command(
            serial_number, "CoffeeMachineGroupDoseChangeMode", data
        )

    async def set_group_dose(
        self,
        serial_number: str,
        mode: DoseMode,
        dose_index: DoseIndex,
        dose: float,
        group_index: int = 1,
    ) -> bool:
        """Set a group dose value for a given mode and dose index."""
        data = {
            "groupIndex": group_index,
            "mode": mode.value,
            "doseIndex": dose_index.value,
            "dose": round(dose, 1),
        }
        return await self.__execute_command(
            serial_number, "CoffeeMachineGroupDoseSettingDose", data
        )

    async def set_brewing_pressure(
        self, serial_number: str, pressure: float, group_index: int = 1
    ) -> bool:
        """Set the brewing pressure of a group."""
        data = {"groupIndex": group_index, "pressure": round(pressure, 1)}
        return await self.__execute_command(
            serial_number,
            "CoffeeMachineGroupDoseSettingGroupBrewingPressure",
            data,
        )

    async def set_continuous_dose_enabled(
        self, serial_number: str, enabled: bool, group_index: int = 1
    ) -> bool:
        """Enable or disable the continuous (rinse) dose of a group."""
        data = {"groupIndex": group_index, "rinseEnabled": enabled}
        return await self.__execute_command(
            serial_number,
            "CoffeeMachineGroupDoseSettingContinuousDoseEnabled",
            data,
        )

    async def set_continuous_dose(
        self, serial_number: str, seconds: float, group_index: int = 1
    ) -> bool:
        """Set the continuous (rinse) dose duration of a group."""
        data = {"groupIndex": group_index, "rinseSeconds": round(seconds, 1)}
        return await self.__execute_command(
            serial_number,
            "CoffeeMachineGroupDoseSettingContinuousDose",
            data,
        )

    async def set_mirror_group1(
        self, serial_number: str, enabled: bool, group_index: int = 2
    ) -> bool:
        """Make a group mirror group 1's doses.

        Args:
            group_index: The group that should mirror group 1. Defaults to 2,
                since group 1 cannot mirror itself.
        """
        data = {"groupIndex": group_index, "enabled": enabled}
        return await self.__execute_command(
            serial_number,
            "CoffeeMachineGroupDoseSettingMirrorGroup1",
            data,
        )

    async def set_plumb_in(self, serial_number: str, enabled: bool) -> bool:
        """Enable or disable plumb-in mode."""
        return await self.__set_enabled(
            serial_number, "CoffeeMachineSettingPlumbIn", enabled
        )

    async def start_backflush_cleaning(
        self,
        serial_number: str,
    ) -> bool:
        """Start backflush cleaning"""
        return await self.__set_enabled(
            serial_number, "CoffeeMachineBackFlushStartCleaning", True
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
            serial_number, "CoffeeMachinePreBrewingSettingTimes", times.to_dict()
        )

    async def change_pre_infusion_mode(
        self,
        serial_number: str,
        mode: PreExtractionMode,
        group_index: int = 1,
    ) -> bool:
        """Change the pre-infusion mode of a group (CMPreInfusion widget)."""
        data = {"groupIndex": group_index, "mode": mode.value}
        return await self.__execute_command(
            serial_number, "CoffeeMachinePreInfusionChangeMode", data
        )

    async def change_pre_infusion_times(
        self,
        serial_number: str,
        seconds_in: float,
        seconds_out: float,
        dose_index: DoseIndex = DoseIndex.BY_GROUP,
        group_index: int = 1,
    ) -> bool:
        """Change the pre-infusion times of a group (CMPreInfusion widget)."""
        data = {
            "groupIndex": group_index,
            "doseIndex": dose_index.value,
            "times": {"In": round(seconds_in, 1), "Out": round(seconds_out, 1)},
        }
        return await self.__execute_command(
            serial_number, "CoffeeMachinePreInfusionSettingTimes", data
        )

    async def set_pre_infusion_enabled(self, serial_number: str, enabled: bool) -> bool:
        """Enable or disable pre-infusion (CMPreInfusionEnable widget)."""
        return await self.__set_enabled(
            serial_number, "CoffeeMachinePreInfusionEnable", enabled
        )

    async def set_time_zone(self, serial_number: str, zone: str) -> bool:
        """Set the time zone of the machine (e.g. "Europe/Rome")."""
        data = {"zone": zone}
        return await self.__execute_command(
            serial_number, "CoffeeMachineSettingTimeZone", data
        )

    async def set_auto_steam_dose(
        self,
        serial_number: str,
        dose: float,
        dose_index: DoseIndex,
        steam_index: int = 1,
    ) -> bool:
        """Set an automatic steam dose."""
        data = {
            "steamIndex": steam_index,
            "doseIndex": dose_index.value,
            "dose": round(dose, 1),
        }
        return await self.__execute_command(
            serial_number, "CoffeeMachineSettingAutoSteamDose", data
        )

    async def set_baby_milk(
        self, serial_number: str, enabled: bool, steam_index: int = 1
    ) -> bool:
        """Enable or disable the baby milk function."""
        data = {"steamIndex": steam_index, "enabled": enabled}
        return await self.__execute_command(
            serial_number, "CoffeeMachineBabyMilkSettingEnabled", data
        )

    async def set_baby_milk_target_temperature(
        self, serial_number: str, target_temperature: float, steam_index: int = 1
    ) -> bool:
        """Set the target temperature of the baby milk function."""
        data = {
            "steamIndex": steam_index,
            "targetTemperature": round(target_temperature, 1),
        }
        return await self.__execute_command(
            serial_number, "CoffeeMachineBabyMilkSettingTargetTemperature", data
        )

    async def calibrate_scale(
        self,
        serial_number: str,
        scale_name: ScaleType = ScaleType.ACAIA_LUNAR,
        force: bool | None = None,
    ) -> bool:
        """Calibrate the scale paired with the machine."""
        data: dict[str, Any] = {"scaleName": scale_name.value}
        if force is not None:
            data["force"] = force
        return await self.__execute_command(
            serial_number, "ThingScaleSettingPosition", data
        )

    async def set_smart_standby(
        self, serial_number: str, enabled: bool, minutes: int, after: SmartStandByType
    ) -> bool:
        """Set smart standby"""

        data = {"enabled": enabled, "minutes": minutes, "after": after.value}
        return await self.__execute_command(
            serial_number, "CoffeeMachineSettingSmartStandBy", data
        )

    async def set_auto_on_off(
        self,
        serial_number: str,
        on_time_minutes: int,
        off_time_minutes: int,
        close_day: WeekDay | None = None,
    ) -> bool:
        """Set the auto on/off times (minutes after midnight).

        Args:
            close_day: Optional day on which the machine stays off.
        """
        data: dict[str, Any] = {
            "onTimeMinutes": on_time_minutes,
            "offTimeMinutes": off_time_minutes,
        }
        if close_day is not None:
            data["closeDay"] = close_day.value
        return await self.__execute_command(
            serial_number, "CoffeeMachineSettingAutoOnOff", data
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
            serial_number, "CoffeeMachineSettingWakeUpSchedule", schedule.to_dict()
        )

    async def set_auto_on_off_enabled(self, serial_number: str, enabled: bool) -> bool:
        """Enable or disable auto on/off."""
        return await self.__set_enabled(
            serial_number, "CoffeeMachineSettingAutoOnOffEnabled", enabled
        )

    async def set_early_start(self, serial_number: str, enabled: bool) -> bool:
        """Enable or disable early start (smart scheduling)."""
        return await self.__set_enabled(
            serial_number, "CoffeeMachineSettingEarlyStart", enabled
        )

    async def set_eco_mode_timeout(self, serial_number: str, minutes: int) -> bool:
        """Set the minutes of inactivity after which the machine enters eco mode."""
        data = {"timeoutMinutes": minutes}
        return await self.__execute_command(
            serial_number, "CoffeeMachineSettingEcoModeTimeout", data
        )

    async def set_eco_mode_offset(self, serial_number: str, offset: float) -> bool:
        """Set the boiler temperature offset applied in eco mode."""
        data = {"offset": round(offset, 1)}
        return await self.__execute_command(
            serial_number, "CoffeeMachineSettingEcoModeOffset", data
        )

    async def set_weekly_schedule_enabled(
        self, serial_number: str, enabled: bool
    ) -> bool:
        """Enable or disable the weekly schedule."""
        return await self.__set_enabled(
            serial_number, "CoffeeMachineSettingWeeklyEnabled", enabled
        )

    async def set_weekly_schedule_day(
        self,
        serial_number: str,
        day: WeekDay,
        enabled: bool,
        on_time_minutes: int,
        off_time_minutes: int,
    ) -> bool:
        """Set the weekly schedule of a single day.

        Times are given in minutes after midnight.
        """
        data = {
            "day": day.value,
            "enabled": enabled,
            "onTimeMinutes": on_time_minutes,
            "offTimeMinutes": off_time_minutes,
        }
        return await self.__execute_command(
            serial_number, "CoffeeMachineSettingWeeklyDay", data
        )

    async def set_grinder_mode(
        self,
        serial_number: str,
        mode: GrinderMode,
    ) -> bool:
        """Set the grinder mode (GrindingMode wakes it, StandBy puts it to sleep)."""
        data = {"mode": mode.value}
        return await self.__execute_command(serial_number, "GrinderChangeMode", data)

    async def set_grinder_barista_light(
        self,
        serial_number: str,
        enabled: bool,
    ) -> bool:
        """Enable or disable the barista light of a grinder."""
        return await self.__set_enabled(
            serial_number, "GrinderSettingBaristaLightEnabled", enabled
        )

    async def set_grinder_grind_with(
        self,
        serial_number: str,
        mode: GrinderGrindWithMode,
    ) -> bool:
        """Set the grind-with mode of a grinder."""
        data = {"mode": str(mode)}
        return await self.__execute_command(
            serial_number, "GrinderSettingGrindWithMode", data
        )

    async def set_grinder_dose(
        self,
        serial_number: str,
        dose_index: DoseIndex,
        dose: float,
        mode: GrinderDoseMode,
    ) -> bool:
        """Set a grinder dose."""
        data = {"mode": str(mode), "doseIndex": str(dose_index), "dose": dose}
        return await self.__execute_command(serial_number, "GrinderSettingDose", data)

    async def set_grinder_more_dose(
        self,
        serial_number: str,
        revolutions: float,
    ) -> bool:
        """Set the additional ("more dose") revolutions of a grinder."""
        data = {"revolutions": revolutions}
        return await self.__execute_command(
            serial_number, "GrinderSettingMoreDose", data
        )

    async def set_grinder_single_dose_mode(
        self,
        serial_number: str,
        enabled: bool,
    ) -> bool:
        """Enable or disable the single dose mode of a grinder."""
        return await self.__set_enabled(
            serial_number, "GrinderSettingSingleDoseModeEnabled", enabled
        )

    async def set_grinder_mirror_doses(
        self,
        serial_number: str,
        enabled: bool,
    ) -> bool:
        """Enable or disable mirroring the doses of a grinder."""
        return await self.__set_enabled(
            serial_number, "GrinderSettingMirrorDosesEnabled", enabled
        )

    async def set_grinder_speed(
        self,
        serial_number: str,
        dose_index: DoseIndex,
        speed_level: GrinderSpeedLevelType,
    ) -> bool:
        """Set the speed level of a grinder dose."""
        data = {"doseIndex": str(dose_index), "speedLevel": str(speed_level)}
        return await self.__execute_command(
            serial_number, "GrinderSettingSpeedForDose", data
        )

    async def set_grinder_auto_speed_enabled(
        self,
        serial_number: str,
        dose_index: DoseIndex,
        enabled: bool,
        group_index: int = 1,
    ) -> bool:
        """Enable or disable the automatic speed of a grinder dose.

        The automatic speed follows the extraction of the given group of the
        coffee machine in the same coffee station.
        """
        data = {
            "doseIndex": str(dose_index),
            "groupIndex": group_index,
            "enabled": enabled,
        }
        return await self.__execute_command(
            serial_number, "GrinderSettingAutoSpeedDoseEnabled", data
        )

    async def set_grinder_auto_speed_reference(
        self,
        serial_number: str,
        dose_mode: DoseMode,
        extraction_seconds: float | None = None,
        dose_mass: float | None = None,
        dose_pulses: float | None = None,
        rate_lock: bool = False,
    ) -> bool:
        """Set the reference extraction the automatic grinder speed adapts to."""
        data = {
            "doseMode": str(dose_mode),
            "extractionSeconds": extraction_seconds,
            "doseMass": dose_mass,
            "dosePulses": dose_pulses,
            "rateLock": rate_lock,
        }
        return await self.__execute_command(
            serial_number, "GrinderSettingAutoSpeedDose", data
        )

    async def set_grinder_auto_standby(
        self,
        serial_number: str,
        minutes: int,
    ) -> bool:
        """Set the minutes of inactivity after which a grinder goes to standby."""
        data = {"standByMinutes": minutes}
        return await self.__execute_command(
            serial_number, "GrinderSettingAutoStandBy", data
        )

    async def change_brew_by_weight_dose_mode(
        self,
        serial_number: str,
        mode: DoseMode,
    ) -> bool:
        """Change the brew by weight dose mode (Linea Mini models only)."""
        data = {"mode": mode.value}
        return await self.__execute_command(
            serial_number, "CoffeeMachineBrewByWeightChangeMode", data
        )

    async def set_brew_by_weight_dose(
        self,
        serial_number: str,
        dose_1: float,
        dose_2: float,
    ) -> bool:
        """Set the brew by weight doses (Linea Mini models only)."""
        data = {
            "doses": {
                "Dose1": round(dose_1, 1),
                "Dose2": round(dose_2, 1),
            }
        }
        return await self.__execute_command(
            serial_number, "CoffeeMachineBrewByWeightSettingDoses", data
        )

    async def set_module_mode(self, serial_number: str, mode: MachineMode) -> bool:
        """Set the mode of the Modbar pour-over module."""
        data = {"mode": mode.value}
        return await self.__execute_command(
            serial_number, "CoffeeMachineModuleChangeMode", data
        )

    async def set_tap_mode(
        self, serial_number: str, mode: MachineMode, tap_index: int = 1
    ) -> bool:
        """Set the mode of a Modbar pour-over tap."""
        data = {"tapIndex": tap_index, "mode": mode.value}
        return await self.__execute_command(
            serial_number, "CoffeeMachineTapChangeMode", data
        )

    async def set_module_target_temperature(
        self, serial_number: str, target_temperature: float
    ) -> bool:
        """Set the target temperature of the Modbar pour-over module."""
        data = {"targetTemperature": round(target_temperature, 1)}
        return await self.__execute_command(
            serial_number, "CoffeeMachineSettingModuleTargetTemperature", data
        )

    async def set_tap_target_temperature_offset(
        self, serial_number: str, offset: float, tap_index: int = 1
    ) -> bool:
        """Set the target temperature offset of a Modbar pour-over tap."""
        data = {"tapIndex": tap_index, "targetOffsetTemperature": round(offset, 1)}
        return await self.__execute_command(
            serial_number, "CoffeeMachineSettingTapTargetTemperature", data
        )

    async def change_pour_over_recipe(
        self, serial_number: str, recipe: PourOverRecipe
    ) -> bool:
        """Change a recipe of the Modbar pour-over machine."""
        return await self.__execute_command(
            serial_number, "CoffeeMachineChangeRecipe", recipe.to_dict()
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
