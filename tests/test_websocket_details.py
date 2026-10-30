"""Tests for WebSocketDetails model."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import ClientWebSocketResponse

from pylamarzocco.models import WebSocketDetails


def test_connected_without_websocket() -> None:
    """Test a details object without websocket is not connected."""
    assert not WebSocketDetails().connected


def test_connected_follows_websocket_state() -> None:
    """Test the connected property follows the websocket state."""
    mock_ws = MagicMock(spec=ClientWebSocketResponse)
    mock_ws.closed = False
    details = WebSocketDetails(ws=mock_ws)
    assert details.connected

    mock_ws.closed = True
    assert not details.connected

    # reconnected
    mock_ws.closed = False
    assert details.connected


async def test_disconnect_with_callback() -> None:
    """Test the disconnect callback is called on every disconnect."""
    mock_callback = AsyncMock()
    details = WebSocketDetails(disconnect_callback=mock_callback)

    await details.disconnect()
    await details.disconnect()

    assert mock_callback.call_count == 2


async def test_disconnect_without_callback() -> None:
    """Test disconnecting without callback does nothing."""
    await WebSocketDetails().disconnect()


async def test_disconnect_callback_exception() -> None:
    """Test exceptions of the disconnect callback are not suppressed."""

    async def failing_callback() -> None:
        raise Exception("Callback failed")  # pylint: disable=broad-exception-raised

    details = WebSocketDetails(disconnect_callback=failing_callback)
    with pytest.raises(Exception, match="Callback failed"):
        await details.disconnect()
