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
from .helpers import parse_preinfusion_settings

_logger = logging.getLogger(__name__)


class LMLocalAPI:
    """Class to interact with machine via local API."""

    def __init__(
        self,
        host: str,
        local_bearer: str,
        local_port: int = 8081,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._host = host
        self._local_port = local_port
        self._local_bearer = local_bearer

        self._timestamp_last_websocket_msg: datetime | None = None
        self._status: dict[str, Any] = {}
        self._status[BREW_ACTIVE] = False
        self._status[BREW_ACTIVE_DURATION] = 0
        self._websocket_connected = False
        self._terminating: bool = False
        if client is None:
            self._client = httpx.AsyncClient()
        else:
            self._client = client

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
    def websocket_connected(self) -> bool:
        """Return whether the websocket is connected."""
        return self._websocket_connected

    @property
    def timestamp_last_websocket_msg(self) -> datetime | None:
        """Return the timestamp of the last websocket message."""
        return self._timestamp_last_websocket_msg

    async def local_get_config(self) -> dict[str, Any]:
        """Get current config of machine from local API."""
        headers = {"Authorization": f"Bearer {self._local_bearer}"}

        try:
            response = await self._client.get(
                f"http://{self._host}:{self._local_port}/api/v1/config", headers=headers
            )
        except httpx.RequestError as exc:
            raise RequestNotSuccessful(
                f"Requesting local API failed with exception: {exc}"
            ) from exc
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
                self._websocket_connected = True
                # Process messages received on the connection.
                async for message in websocket:
                    if self._terminating:
                        return
                    try:
                        for (
                            property_updated,
                            value,
                        ) in await self.handle_websocket_message(message):
                            if callback is not None and property_updated is not None:
                                try:
                                    callback(property_updated, value)
                                except Exception as e:  # pylint: disable=broad-except
                                    _logger.exception(
                                        "Error during callback: %s", e, exc_info=True
                                    )
                    except UnknownWebSocketMessage as e:
                        _logger.warning("Unknown websocket message received")
                        _logger.debug(e)
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
    ) -> list[tuple[str | None, Any | None]]:
        """Handle a message received on the websocket."""
        self._timestamp_last_websocket_msg = datetime.now()
        message = json.loads(message)

        if isinstance(message, dict):
            if "MachineConfiguration" in message:
                # got machine configuration
                value = json.loads(message["MachineConfiguration"])
                self._status["machineConfiguration"] = value
                return [("machineConfiguration", value)]

            if "SystemInfo" in message:
                value = json.loads(message["SystemInfo"])
                self._status["systemInfo"] = value
                return [("systemInfo", value)]

        if isinstance(message, list):
            for msg in message:
                updates: list[tuple[str | None, Any | None]] = []
                if "KeepAlive" in msg:
                    updates.append((None, None))

                elif "SteamBoilerUpdateTemperature" in msg:
                    value = msg["SteamBoilerUpdateTemperature"]
                    updates.append(("steam_temp", value))

                elif "CoffeeBoiler1UpdateTemperature" in msg:
                    value = msg["CoffeeBoiler1UpdateTemperature"]
                    updates.append(("coffee_temp", value))

                elif "Sleep" in msg:
                    self._status["power"] = False
                    self._status["sleepCause"] = msg["Sleep"]
                    updates.append(("power", False))

                elif "SteamBoilerEnabled" in msg:
                    value = msg["SteamBoilerEnabled"]
                    updates.append(("steam_boiler_enable", value))

                elif "WakeUp" in msg:
                    self._status["wakeupCause"] = msg["WakeUp"]
                    updates.append(("power", True))

                elif "MachineStatistics" in msg:
                    value = json.loads(msg["MachineStatistics"])
                    updates.append(("statistics", value))

                elif "BrewingUpdateGroup1Time" in msg:
                    self._status[BREW_ACTIVE] = True
                    value = msg["BrewingUpdateGroup1Time"]
                    self._status[BREW_ACTIVE_DURATION] = value
                    updates.append((BREW_ACTIVE_DURATION, value))

                elif "BrewingStartedGroup1StopType" in msg:
                    self._status[BREW_ACTIVE] = True
                    updates.append((BREW_ACTIVE, True))

                elif "BrewingStoppedGroup1StopType" in msg:
                    self._status[BREW_ACTIVE] = False
                    updates.append((BREW_ACTIVE, False))

                elif "BrewingSnapshotGroup1" in msg:
                    self._status[BREW_ACTIVE] = False
                    self._status["brewingSnapshot"] = json.loads(
                        msg["BrewingSnapshotGroup1"]
                    )
                    updates.append((BREW_ACTIVE, False))

                elif "SteamBoilerUpdateSetPoint" in msg:
                    value = msg["SteamBoilerUpdateSetPoint"]
                    updates.append(("steam_set_temp", value))

                elif "CoffeeBoiler1UpdateSetPoint" in msg:
                    value = msg["CoffeeBoiler1UpdateSetPoint"]
                    updates.append(("coffee_set_temp", value))

                elif "BoilersTargetTemperature" in msg:
                    boilers = json.loads(msg["BoilersTargetTemperature"])
                    for boiler in boilers:
                        if boiler["id"] == "CoffeeBoiler1":
                            updates.append(("coffee_set_temp", boiler["value"]))
                        elif boiler["id"] == "SteamBoiler":
                            updates.append(("steam_set_temp", boiler["value"]))

                elif "Boilers" in msg:
                    boilers = json.loads(msg["Boilers"])
                    for boiler in boilers:
                        is_enabled = boiler["isEnabled"]
                        current_temp = boiler["current"]
                        target_temp = boiler["target"]
                        if boiler["id"] == "CoffeeBoiler1":
                            updates.append(("power", is_enabled))
                            updates.append(("coffee_temp", current_temp))
                            updates.append(("coffee_set_temp", target_temp))
                        elif boiler["id"] == "SteamBoiler":
                            updates.append(("steam_boiler_enable", is_enabled))
                            updates.append(("steam_temp", current_temp))
                            updates.append(("steam_set_temp", target_temp))

                elif "PreinfusionSettings" in msg:
                    settings: dict[str, Any] = {}
                    settings["preinfusionSettings"] = json.loads(
                        msg["PreinfusionSettings"]
                    )
                    mode = settings["preinfusionSettings"].get("mode", "Disabled")
                    if mode == "Enabled":
                        updates.append(("enable_prebrewing", True))
                        updates.append(("enable_preinfusion", False))
                    elif mode == "TypeB":
                        updates.append(("enable_prebrewing", False))
                        updates.append(("enable_preinfusion", True))
                    else:
                        updates.append(("enable_prebrewing", False))
                        updates.append(("enable_preinfusion", False))

                    parsed = parse_preinfusion_settings(settings)
                    for key, value in parsed.items():
                        updates.append((key, value))

                if updates:
                    return updates

        raise UnknownWebSocketMessage(f"Unknown websocket message: {message}")
