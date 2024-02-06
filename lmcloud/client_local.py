"""Interact with the local API of La Marzocco machines."""

import asyncio
import logging
import signal
from typing import Any, Callable

from httpx import AsyncClient, RequestError
import websockets

from .const import WEBSOCKET_RETRY_DELAY
from .exceptions import AuthFail, RequestNotSuccessful

_LOGGER = logging.getLogger(__name__)


class LaMarzoccoLocalClient:
    """Class to interact with machine via local API."""

    def __init__(
        self,
        host: str,
        local_bearer: str,
        local_port: int = 8081,
        client: AsyncClient | None = None,
    ) -> None:
        self._host = host
        self._local_port = local_port
        self._local_bearer = local_bearer

        self.websocket_connected = False
        self.terminating: bool = False

        if client is None:
            self._client = AsyncClient()
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
        client: AsyncClient,
        host: str,
        token: str,
        port: int = 8080,
    ) -> bool:
        """Validate the connection details to the local API."""
        try:
            await LaMarzoccoLocalClient._get_config(client, host, token, port)
        except AuthFail as exc:
            _LOGGER.error(exc)
            return False
        except RequestNotSuccessful as exc:
            _LOGGER.error(exc)
            return False
        return True

    @staticmethod
    async def _get_config(
        client: AsyncClient,
        host: str,
        token: str,
        port: int = 8080,
    ) -> dict[str, Any]:
        """Get current config of machine from local API."""
        headers = {"Authorization": f"Bearer {token}"}

        try:
            response = await client.get(
                f"http://{host}:{port}/api/v1/config", headers=headers
            )
        except RequestError as exc:
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
        callback: Callable[[str | bytes], None] | None = None,
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
                self.websocket_connected = True
                # Process messages received on the connection.
                async for message in websocket:
                    if self.terminating:
                        return
                    if callback is not None:
                        try:
                            callback(message)
                        except Exception as exc:  # pylint: disable=broad-except
                            _LOGGER.exception("Error during callback: %s", exc)
            except websockets.ConnectionClosed:
                if self.terminating:
                    return
                _LOGGER.debug(
                    "Websocket disconnected, reconnecting in %s", WEBSOCKET_RETRY_DELAY
                )
                await asyncio.sleep(WEBSOCKET_RETRY_DELAY)
                continue
            except websockets.WebSocketException as ex:
                _LOGGER.warning("Exception during websocket connection: %s", ex)
