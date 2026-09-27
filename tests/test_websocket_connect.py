"""Test the cloud client's websocket connection loop against a local server."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import Any
from unittest.mock import MagicMock

import pytest
from aiohttp import ClientSession, ClientTimeout, WSMsgType, web
from aiointercept import CallbackResult, aiointercept
from cryptography.hazmat.primitives.asymmetric.ec import SECP256R1, generate_private_key
from yarl import URL

from pylamarzocco.clients import LaMarzoccoCloudClient
from pylamarzocco.const import BASE_URL, StompMessageType
from pylamarzocco.models import ThingDashboardWebsocketConfig
from pylamarzocco.util import (
    InstallationKey,
    decode_stomp_ws_message,
    encode_stomp_ws_message,
)

from .conftest import load_fixture

# aiointercept only restores the https scheme of intercepted requests, so the
# client's wss:// endpoint has to be registered under https://.
WEBSOCKET_URL = f"https://{BASE_URL}/ws/connect"
HANDSHAKE_KEY = ("GET", URL(WEBSOCKET_URL))

MOCK_SECRET_DATA = InstallationKey(
    secret=bytes(32),
    private_key=generate_private_key(SECP256R1()),
    installation_id="mock-installation-id",
)

StompFrame = tuple[StompMessageType, dict[str, str], str | None]


@pytest.fixture(name="client")
async def fixture_client() -> AsyncGenerator[LaMarzoccoCloudClient]:
    """Return a cloud client whose session is closed after the test."""
    async with ClientSession() as session:
        yield LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA, session)


def add_websocket_endpoint(
    mock: aiointercept,
    session: Callable[[web.WebSocketResponse], Awaitable[None]],
) -> asyncio.Event:
    """Serve one websocket connection from aiointercept's server.

    aiointercept can only build plain HTTP responses, so swap the handler it
    registers for one that upgrades the connection and runs ``session``. The
    server runs on its own thread, so the returned event signals when the
    session has ended.
    """
    loop = asyncio.get_running_loop()
    session_finished = asyncio.Event()

    async def handler(request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        try:
            await ws.prepare(request)
            await session(ws)
        finally:
            loop.call_soon_threadsafe(session_finished.set)
        return ws

    mock_response = mock.get(WEBSOCKET_URL)
    mock_response._handler = handler  # pylint: disable=protected-access
    return session_finished


async def receive_frame(ws: web.WebSocketResponse) -> StompFrame:
    """Receive and decode the next STOMP frame sent by the client."""
    return decode_stomp_ws_message(await ws.receive_str())


async def accept_stomp_connection(
    ws: web.WebSocketResponse, frames: list[StompFrame]
) -> None:
    """Answer the client's CONNECT and record it together with its SUBSCRIBE."""
    frames.append(await receive_frame(ws))
    await ws.send_str(
        encode_stomp_ws_message(StompMessageType.CONNECTED, {"version": "1.2"})
    )
    frames.append(await receive_frame(ws))


@pytest.mark.parametrize(
    "response",
    [
        {"status": 401},
        # aiohttp retries a dropped GET once, so drop every attempt.
        {"exception": True, "repeat": True},
    ],
    ids=["rejected", "dropped"],
)
async def test_websocket_handshake_failure_stops_reconnecting(
    mock_aiointercept: aiointercept,
    client: LaMarzoccoCloudClient,
    serial: str,
    response: dict[str, Any],
) -> None:
    """A failed websocket handshake ends the connection loop."""
    mock_aiointercept.get(WEBSOCKET_URL, **response)
    connect_callback = MagicMock()
    disconnect_callback = MagicMock()

    async with asyncio.timeout(5):
        await client.websocket_connect(
            serial,
            connect_callback=connect_callback,
            disconnect_callback=disconnect_callback,
        )

    connect_callback.assert_not_called()
    disconnect_callback.assert_called_once()


async def test_websocket_handshake_timeout_reconnects(
    mock_aiointercept: aiointercept, serial: str
) -> None:
    """A websocket handshake timeout triggers a reconnect."""
    release = asyncio.Event()

    async def stall_handshake(url: URL, **kwargs: Any) -> CallbackResult:
        await release.wait()
        return CallbackResult(status=504)

    mock_aiointercept.get(WEBSOCKET_URL, callback=stall_handshake)
    mock_aiointercept.get(WEBSOCKET_URL, status=401)
    disconnect_callback = MagicMock()

    async with ClientSession(timeout=ClientTimeout(total=0.2)) as session:
        client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA, session)
        try:
            async with asyncio.timeout(5):
                await client.websocket_connect(
                    serial, disconnect_callback=disconnect_callback
                )
        finally:
            release.set()

    assert len(mock_aiointercept.requests[HANDSHAKE_KEY]) == 2
    assert disconnect_callback.call_count == 2


async def test_websocket_session_survives_errors_and_reconnects(
    mock_aiointercept: aiointercept, client: LaMarzoccoCloudClient, serial: str
) -> None:
    """In-session errors are not fatal and a server close triggers a reconnect."""
    frames: list[StompFrame] = []
    update = load_fixture("machine", "config_micra.json")
    update_message = encode_stomp_ws_message(
        StompMessageType.MESSAGE,
        {"destination": f"/ws/sn/{serial}/dashboard"},
        json.dumps(update),
    )

    async def session(ws: web.WebSocketResponse) -> None:
        await accept_stomp_connection(ws, frames)
        await ws.send_str(
            encode_stomp_ws_message(StompMessageType.ERROR, {"message": "Hiccup"})
        )
        await ws.send_str(update_message)
        await ws.send_str(update_message)
        await ws.close()

    add_websocket_endpoint(mock_aiointercept, session)
    mock_aiointercept.get(WEBSOCKET_URL, status=401)
    notification_callback = MagicMock(
        side_effect=[RuntimeError("callback failed"), None]
    )
    connect_callback = MagicMock()
    disconnect_callback = MagicMock()

    async with asyncio.timeout(5):
        await client.websocket_connect(
            serial,
            notification_callback=notification_callback,
            connect_callback=connect_callback,
            disconnect_callback=disconnect_callback,
        )

    assert [frame[0] for frame in frames] == [
        StompMessageType.CONNECT,
        StompMessageType.SUBSCRIBE,
    ]
    assert frames[1][1]["destination"] == f"/ws/sn/{serial}/dashboard"
    assert notification_callback.call_count == 2
    notification_callback.assert_called_with(
        ThingDashboardWebsocketConfig.from_dict(update)
    )
    connect_callback.assert_called_once()
    assert len(mock_aiointercept.requests[HANDSHAKE_KEY]) == 2
    assert disconnect_callback.call_count == 2
    assert client.websocket.connected is False


async def test_websocket_protocol_error_reconnects(
    mock_aiointercept: aiointercept,
    client: LaMarzoccoCloudClient,
    serial: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A websocket protocol error is logged with its cause and triggers a reconnect.

    Disconnecting afterwards is a no-op because the socket is already closed.
    """

    async def session(ws: web.WebSocketResponse) -> None:
        await accept_stomp_connection(ws, [])
        await ws.send_frame(b"\xff", WSMsgType.TEXT)
        async for _ in ws:
            pass

    add_websocket_endpoint(mock_aiointercept, session)
    mock_aiointercept.get(WEBSOCKET_URL, status=401)
    connect_callback = MagicMock()
    disconnect_callback = MagicMock()

    async with asyncio.timeout(5):
        await client.websocket_connect(
            serial,
            connect_callback=connect_callback,
            disconnect_callback=disconnect_callback,
        )
        await client.websocket.disconnect()

    assert (
        "Websocket disconnected with error: Invalid UTF-8 text message" in caplog.text
    )
    connect_callback.assert_called_once()
    assert len(mock_aiointercept.requests[HANDSHAKE_KEY]) == 2
    assert disconnect_callback.call_count == 2
    assert client.websocket.connected is False


async def test_websocket_without_connected_frame_stops(
    mock_aiointercept: aiointercept, client: LaMarzoccoCloudClient, serial: str
) -> None:
    """A CONNECT that is not answered with CONNECTED ends the connection loop."""
    frames: list[StompFrame] = []

    async def session(ws: web.WebSocketResponse) -> None:
        frames.append(await receive_frame(ws))
        await ws.send_str(
            encode_stomp_ws_message(StompMessageType.ERROR, {"message": "Denied"})
        )
        async for msg in ws:
            frames.append(decode_stomp_ws_message(msg.data))

    add_websocket_endpoint(mock_aiointercept, session)
    connect_callback = MagicMock()
    disconnect_callback = MagicMock()

    async with asyncio.timeout(5):
        await client.websocket_connect(
            serial,
            connect_callback=connect_callback,
            disconnect_callback=disconnect_callback,
        )

    assert [frame[0] for frame in frames] == [StompMessageType.CONNECT]
    assert len(mock_aiointercept.requests[HANDSHAKE_KEY]) == 1
    connect_callback.assert_not_called()
    disconnect_callback.assert_called_once()


async def test_websocket_callback_error_stops(
    mock_aiointercept: aiointercept, client: LaMarzoccoCloudClient, serial: str
) -> None:
    """An error raised by a callback ends the connection loop without propagating."""

    async def session(ws: web.WebSocketResponse) -> None:
        await accept_stomp_connection(ws, [])
        async for _ in ws:
            pass

    add_websocket_endpoint(mock_aiointercept, session)
    connect_callback = MagicMock(side_effect=RuntimeError("callback failed"))
    disconnect_callback = MagicMock()

    async with asyncio.timeout(5):
        await client.websocket_connect(
            serial,
            connect_callback=connect_callback,
            disconnect_callback=disconnect_callback,
        )

    connect_callback.assert_called_once()
    assert len(mock_aiointercept.requests[HANDSHAKE_KEY]) == 1
    disconnect_callback.assert_called_once()


async def test_websocket_cancellation_unsubscribes(
    mock_aiointercept: aiointercept, client: LaMarzoccoCloudClient, serial: str
) -> None:
    """Cancelling the connection task unsubscribes and closes the websocket."""
    frames: list[StompFrame] = []
    connected = asyncio.Event()

    async def session(ws: web.WebSocketResponse) -> None:
        await accept_stomp_connection(ws, frames)
        async for msg in ws:
            frames.append(decode_stomp_ws_message(msg.data))

    session_finished = add_websocket_endpoint(mock_aiointercept, session)
    disconnect_callback = MagicMock()
    task = asyncio.create_task(
        client.websocket_connect(
            serial,
            connect_callback=connected.set,
            disconnect_callback=disconnect_callback,
        )
    )

    async with asyncio.timeout(5):
        await connected.wait()
        task.cancel()
        await task
        # A cancelled client closes without awaiting the server's close reply.
        await session_finished.wait()

    assert [frame[0] for frame in frames] == [
        StompMessageType.CONNECT,
        StompMessageType.SUBSCRIBE,
        StompMessageType.UNSUBSCRIBE,
    ]
    assert frames[2][1] == {"id": frames[1][1]["id"]}
    assert client.websocket.connected is False
    disconnect_callback.assert_called_once()
