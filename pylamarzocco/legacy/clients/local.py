"""Interact with the local API of La Marzocco machines."""

import logging
from typing import Any, Callable

from aiohttp import (
    ClientSession,
    ClientWebSocketResponse,
    WSMsgType,
    ClientWSTimeout,
    ClientConnectionError,
)
from aiohttp.client_exceptions import ClientError, InvalidURL

from pylamarzocco.legacy.clients.cloud import LaMarzoccoCloudClient
from pylamarzocco.legacy.const import DEFAULT_PORT
from pylamarzocco.legacy.exceptions import AuthFail, RequestNotSuccessful
from pylamarzocco.legacy.helpers import is_success

_LOGGER = logging.getLogger(__name__)


class LaMarzoccoLocalClient:
    """Class to interact with machine via local API."""

    def __init__(
        self,
        host: str,
        local_bearer: str,
        local_port: int = DEFAULT_PORT,
        client: ClientSession | None = None,
    ) -> None:
        self._host = host
        self._local_port = local_port
        self._local_bearer = local_bearer

        self.websocket: ClientWebSocketResponse | None = None
        self.websocket_disconnected = False

        if client is None:
            self._client = ClientSession()
        else:
            self._client = client

    async def get_config(self) -> dict[str, Any]:
        """Get current config of machine from local API."""
        return await self._get_config(
            self._client,
            self._host,
            self._local_bearer,
            self._local_port,
        )

    @staticmethod
    async def validate_connection(
        client: ClientSession,
        host: str,
        token: str,
        port: int = DEFAULT_PORT,
        cloud_details: tuple[LaMarzoccoCloudClient, str] | None = None,
    ) -> bool:
        """Validate the connection details to the local API."""
        try:
            await LaMarzoccoLocalClient._get_config(client, host, token, port)
        except AuthFail:
            # try to activate the local API
            if cloud_details is not None:
                cloud_client, serial = cloud_details
                try:
                    await cloud_client.token_command(serial)
                    await LaMarzoccoLocalClient._get_config(client, host, token, port)
                except (AuthFail, RequestNotSuccessful) as ex:
                    _LOGGER.error(ex)
                    return False
        except RequestNotSuccessful as ex:
            _LOGGER.error(ex)
            return False
        return True

    @staticmethod
    async def _get_config(
        client: ClientSession,
        host: str,
        token: str,
        port: int = DEFAULT_PORT,
    ) -> dict[str, Any]:
        """Get current config of machine from local API."""
        headers = {"Authorization": f"Bearer {token}"}

        try:
            response = await client.get(
                f"http://{host}:{port}/api/v1/config", headers=headers
            )
        except ClientError as ex:
            raise RequestNotSuccessful(
                f"Requesting local API failed with exception: {ex}"
            ) from ex
        if is_success(response):
            return await response.json()
        if response.status == 403:
            raise AuthFail("Local API returned 403.")
        raise RequestNotSuccessful(
            f"Querying local API failed with statuscode: {response.status}"
            + f"response: {await response.text()}"
        )

    async def websocket_connect(
        self,
        callback: Callable[[str | bytes], None] | None = None,
    ) -> None:
        """Connect to the websocket of the machine."""

        try:
            async with await self._client.ws_connect(
                f"ws://{self._host}:{self._local_port}/api/v1/streaming",
                headers={"Authorization": f"Bearer {self._local_bearer}"},
                timeout=ClientWSTimeout(ws_receive=25, ws_close=10.0),
            ) as ws:
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
                    if callback is not None:
                        try:
                            callback(msg.data)
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
