"""Interact with the local API of La Marzocco machines."""
import asyncio
import json
import logging
import signal
from datetime import datetime
from typing import Any, Callable

import httpx
import websockets

from .const import BREW_ACTIVE, BREW_ACTIVE_DURATION, WEBSOCKET_RETRY_DELAY
from .exceptions import AuthFail, RequestNotSuccessful, UnknownWebSocketMessage

_logger = logging.getLogger(__name__)


class LMLocalAPI:
    """Class to interact with machine via local API."""

    def __init__(self, host: str, local_bearer: str, local_port: int = 8081) -> None:
        self._host = host
        self._local_port = local_port
        self._local_bearer = local_bearer

        self._timestamp_last_websocket_msg: datetime | None = None
        self._status: dict[str, Any] = {}
        self._status[BREW_ACTIVE] = False
        self._status[BREW_ACTIVE_DURATION] = 0
        self._terminating: bool = False

    @property
    def local_port(self) -> int:
        """Return the local port of the machine."""
        return self._local_port

    @property
    def host(self) -> str:
        """Return the hostname of the machine."""
        return self._host

    @property
    def brew_active(self) -> bool:
        """Return whether the machine is currently brewing."""
        return self._status[BREW_ACTIVE]

    @property
    def brew_active_duration(self) -> int:
        """Return the duration of the current brew."""
        return self._status[BREW_ACTIVE_DURATION]

    @property
    def terminating(self) -> bool:
        """Return whether the websocket connection is terminating."""
        return self._terminating

    @terminating.setter
    def terminating(self, value: bool):
        self._terminating = value

    @property
    def timestamp_last_websocket_msg(self) -> datetime | None:
        """Return the timestamp of the last websocket message."""
        return self._timestamp_last_websocket_msg

    async def local_get_config(self) -> dict[str, Any]:
        """Get current config of machine from local API."""
        headers = {"Authorization": f"Bearer {self._local_bearer}"}
        async with httpx.AsyncClient(headers=headers) as client:
            response = await client.get(
                f"http://{self._host}:{self._local_port}/api/v1/config"
            )
            if response.is_success:
                return response.json()
            if response.status_code == 403:
                raise AuthFail("Local API returned 403.")
            raise RequestNotSuccessful(
                f"Querying local API failed with statuscode: {response.status_code}"
            )

    async def websocket_connect(
        self,
        callback: Callable[[str, Any], None] | None = None,
        use_sigterm_handler: bool = True,
    ) -> None:
        """Connect to the websocket of the machine."""
        headers = {"Authorization": f"Bearer {self._local_bearer}"}
        async for websocket in websockets.connect(
            f"ws://{self._host}:{self._local_port}/api/v1/streaming",
            extra_headers=headers,
        ):
            try:
                if use_sigterm_handler:
                    # Close the connection when receiving SIGTERM.
                    loop = asyncio.get_running_loop()
                    loop.add_signal_handler(
                        signal.SIGTERM, loop.create_task, websocket.close()
                    )
                # Process messages received on the connection.
                async for message in websocket:
                    if self._terminating:
                        return
                    try:
                        property_updated, value = await self.handle_websocket_message(
                            message
                        )
                        if callback is not None and property_updated is not None:
                            try:
                                callback(property_updated, value)
                            except Exception as e:  # pylint: disable=broad-except
                                _logger.exception(
                                    "Error during callback: %s", e, exc_info=True
                                )
                    except UnknownWebSocketMessage as e:
                        _logger.warning(e)
            except websockets.ConnectionClosed:
                if self._terminating:
                    return
                _logger.debug(
                    "Websocket disconnected, reconnecting in %s", WEBSOCKET_RETRY_DELAY
                )
                await asyncio.sleep(WEBSOCKET_RETRY_DELAY)
                continue
            except websockets.WebSocketException as ex:
                _logger.warning("Exception during websocket connection: %s", ex)

    async def handle_websocket_message(
        self, message: Any
    ) -> tuple[str | None, Any | None]:
        """Handle a message received on the websocket."""
        self._timestamp_last_websocket_msg = datetime.now()
        message = json.loads(message)

        if isinstance(message, dict):
            if "MachineConfiguration" in message:
                # got machine configuration
                value = json.loads(message["MachineConfiguration"])
                self._status["machineConfiguration"] = value
                return "machineConfiguration", value

            if "SystemInfo" in message:
                value = json.loads(message["SystemInfo"])
                self._status["systemInfo"] = value
                return "systemInfo", value

        if isinstance(message, list):
            if "KeepAlive" in message[0]:
                return None, None

            if "SteamBoilerUpdateTemperature" in message[0]:
                value = message[0]["SteamBoilerUpdateTemperature"]
                self._status["steamTemperature"] = value
                return "steam_temp", value

            if "CoffeeBoiler1UpdateTemperature" in message[0]:
                value = message[0]["CoffeeBoiler1UpdateTemperature"]
                self._status["coffeeTemperature"] = value
                return "coffee_temp", value

            if "Sleep" in message[0]:
                self._status["power"] = False
                self._status["sleepCause"] = message[0]["Sleep"]
                return "power", False

            if "SteamBoilerEnabled" in message[0]:
                value = message[0]["SteamBoilerEnabled"]
                self._status["steamBoilerEnabled"] = value
                return "steam_boiler_enable", value

            if "WakeUp" in message[0]:
                self._status["power"] = True
                self._status["wakeupCause"] = message[0]["WakeUp"]
                return "power", True

            if "MachineStatistics" in message[0]:
                value = json.loads(message[0]["MachineStatistics"])
                self._status["statistics"] = value
                return "statistics", value

            if "BrewingUpdateGroup1Time" in message[0]:
                self._status[BREW_ACTIVE] = True
                value = message[0]["BrewingUpdateGroup1Time"]
                self._status[BREW_ACTIVE_DURATION] = value
                return BREW_ACTIVE_DURATION, value

            if "BrewingStartedGroup1StopType" in message[0]:
                self._status[BREW_ACTIVE] = True
                return BREW_ACTIVE, True

            if "BrewingStoppedGroup1StopType" in message[0]:
                self._status[BREW_ACTIVE] = False
                return BREW_ACTIVE, False

            if "BrewingSnapshotGroup1" in message[0]:
                self._status[BREW_ACTIVE] = False
                self._status["brewingSnapshot"] = json.loads(
                    message[0]["BrewingSnapshotGroup1"]
                )
                return BREW_ACTIVE, False

        raise UnknownWebSocketMessage(f"Unknown websocket message: {message}")
