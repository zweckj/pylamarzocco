"""Tests for websocket message handling in cloud client."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import WebSocketError, WSCloseCode, WSMessage, WSMsgType

from pylamarzocco.clients import LaMarzoccoCloudClient
from pylamarzocco.const import StompMessageType
from pylamarzocco.util import encode_stomp_ws_message

from .conftest import MOCK_SECRET_DATA


@pytest.fixture(name="mock_client")
def fixture_mock_client() -> LaMarzoccoCloudClient:
    """Return a client with a mocked session."""
    return LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA, MagicMock())


def _text_message(data: str) -> WSMessage:
    return WSMessage(WSMsgType.TEXT, data, None)


@pytest.mark.parametrize("msg_type", [WSMsgType.CLOSING, WSMsgType.CLOSED])
async def test_handle_websocket_message_closed(
    mock_client: LaMarzoccoCloudClient, msg_type: WSMsgType
) -> None:
    """Test a closing or closed websocket stops the message loop."""
    msg = WSMessage(msg_type, None, None)
    assert await mock_client._LaMarzoccoCloudClient__handle_websocket_message(msg)


async def test_handle_websocket_message_error(
    mock_client: LaMarzoccoCloudClient, caplog: pytest.LogCaptureFixture
) -> None:
    """Test handling websocket ERROR message."""
    msg = WSMessage(
        WSMsgType.ERROR,
        WebSocketError(WSCloseCode.INVALID_TEXT, "Invalid UTF-8 text message"),
        None,
    )

    assert await mock_client._LaMarzoccoCloudClient__handle_websocket_message(msg)
    assert "disconnected with error: Invalid UTF-8 text message" in caplog.text


@pytest.mark.parametrize(
    "data",
    [
        encode_stomp_ws_message(
            StompMessageType.ERROR, {"message": "Access denied"}, "Authentication failed"
        ),
        encode_stomp_ws_message(StompMessageType.CONNECTED, {"version": "1.2"}, None),
        "invalid message format",
    ],
    ids=["stomp_error", "non_message", "invalid_format"],
)
async def test_handle_websocket_message_ignored(
    mock_client: LaMarzoccoCloudClient, data: str
) -> None:
    """Test text frames that are not dashboard messages keep the loop running."""
    result = await mock_client._LaMarzoccoCloudClient__handle_websocket_message(
        _text_message(data)
    )
    assert result is False


async def test_handle_websocket_message_with_valid_message(
    mock_client: LaMarzoccoCloudClient,
) -> None:
    """Test handling websocket message with valid STOMP MESSAGE."""
    msg = _text_message(
        encode_stomp_ws_message(
            StompMessageType.MESSAGE, {"destination": "/topic/test"}, '{"test": "data"}'
        )
    )

    with patch.object(
        mock_client, "_LaMarzoccoCloudClient__parse_websocket_message"
    ) as mock_parse:
        result = await mock_client._LaMarzoccoCloudClient__handle_websocket_message(
            msg
        )

    mock_parse.assert_called_once_with('{"test": "data"}', None)
    assert result is False


def test_parse_websocket_message_none(mock_client: LaMarzoccoCloudClient) -> None:
    """Test parsing None websocket message."""
    # Should not raise exception
    mock_client._LaMarzoccoCloudClient__parse_websocket_message(None, None)


def test_parse_websocket_message_with_callback(
    mock_client: LaMarzoccoCloudClient,
) -> None:
    """Test parsing websocket message with notification callback."""
    config_json = '{"connected": true, "commands": [], "widgets": []}'
    callback = MagicMock()

    with patch(
        "pylamarzocco.models.ThingDashboardWebsocketConfig.from_json"
    ) as mock_from_json:
        mock_config = MagicMock()
        mock_config.commands = []
        mock_from_json.return_value = mock_config

        mock_client._LaMarzoccoCloudClient__parse_websocket_message(
            config_json, callback
        )

    callback.assert_called_once_with(mock_config)


def test_parse_websocket_message_pending_command(
    mock_client: LaMarzoccoCloudClient,
) -> None:
    """Test parsing websocket message with pending command."""
    command_id = "test-command-id"
    mock_future = MagicMock()
    mock_client._pending_commands[command_id] = mock_future

    config_json = '{"connected": true, "commands": [], "widgets": []}'

    with patch(
        "pylamarzocco.models.ThingDashboardWebsocketConfig.from_json"
    ) as mock_from_json:
        mock_config = MagicMock()
        mock_command = MagicMock()
        mock_command.id = command_id
        mock_config.commands = [mock_command]
        mock_from_json.return_value = mock_config

        mock_client._LaMarzoccoCloudClient__parse_websocket_message(config_json, None)

    mock_future.set_result.assert_called_once_with(mock_command)


def _mock_ws(response_type: StompMessageType, headers: dict[str, str]) -> MagicMock:
    mock_ws = MagicMock()
    mock_ws.send_str = AsyncMock()
    mock_ws.closed = False
    mock_ws.receive = AsyncMock(
        return_value=MagicMock(
            data=encode_stomp_ws_message(response_type, headers, None)
        )
    )
    return mock_ws


async def test_websocket_setup_connection_basic(
    mock_client: LaMarzoccoCloudClient,
) -> None:
    """Test basic websocket setup connection."""
    mock_ws = _mock_ws(StompMessageType.CONNECTED, {"version": "1.2"})

    with patch.object(mock_client, "async_get_access_token", return_value="token"):
        await mock_client._LaMarzoccoCloudClient__setup_websocket_connection(
            mock_ws, "MR123456"
        )

    # CONNECT and SUBSCRIBE frames were sent
    assert mock_ws.send_str.call_count == 2
    assert mock_client.websocket.connected


async def test_websocket_setup_connection_authentication_failure(
    mock_client: LaMarzoccoCloudClient,
) -> None:
    """Test websocket setup when authentication fails."""
    mock_ws = _mock_ws(StompMessageType.ERROR, {"message": "Authentication failed"})

    with (
        patch.object(mock_client, "async_get_access_token", return_value="token"),
        pytest.raises(Exception),  # pylint: disable=broad-exception-caught
    ):
        await mock_client._LaMarzoccoCloudClient__setup_websocket_connection(
            mock_ws, "MR123456"
        )
