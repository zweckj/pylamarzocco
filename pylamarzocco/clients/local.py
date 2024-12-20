"""Interact with the local API of La Marzocco machines."""

import logging
from typing import Any, Callable

from aiohttp import ClientSession, ClientWebSocketResponse
from aiohttp.client_exceptions import ClientError, InvalidURL

from pylamarzocco.clients.cloud import LaMarzoccoCloudClient
from pylamarzocco.const import DEFAULT_PORT
from pylamarzocco.exceptions import AuthFail, RequestNotSuccessful
from pylamarzocco.helpers import is_success

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

        headers = {"Authorization": f"Bearer {self._local_bearer}"}
        try:
            async with await self._client.ws_connect(
                f"ws://{self._host}:{self._local_port}/api/v1/streaming",
                headers=headers,
            ) as ws:
                self.websocket = ws
                async for msg in ws:
                    _LOGGER.debug("Received websocket message: %s", msg)
                    if callback is not None:
                        try:
                            callback(msg.data)
                        except Exception as ex:  # pylint: disable=broad-except
                            _LOGGER.exception("Error during callback: %s", ex)
        except InvalidURL:
            _LOGGER.error("Invalid URI passed to websocket connection: %s", self._host)
        except (TimeoutError, OSError, ClientError) as ex:
            _LOGGER.error("Error establishing the websocket connection: %s", ex)
