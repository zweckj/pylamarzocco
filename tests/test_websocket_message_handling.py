"""Tests for websocket message handling in cloud client."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from aiohttp import WSMessage, WSMsgType

from pylamarzocco.clients import LaMarzoccoCloudClient
from pylamarzocco.const import StompMessageType
from pylamarzocco.util import InstallationKey, encode_stomp_ws_message
from pylamarzocco.models import WebSocketDetails
from cryptography.hazmat.primitives.asymmetric.ec import SECP256R1, generate_private_key


MOCK_SECRET_DATA = InstallationKey(
    secret=bytes(32),
    private_key=generate_private_key(SECP256R1()),
    installation_id="mock-installation-id",
)


class TestWebSocketMessageHandling:
    """Test websocket message handling functionality."""

    @pytest.fixture
    async def mock_client(self):
        """Create a mocked client with session."""
        mock_session = MagicMock()
        with patch('aiohttp.ClientSession', return_value=mock_session):
            client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA)
            yield client

    async def test_handle_websocket_message_closing(self, mock_client) -> None:
        """Test handling websocket CLOSING message."""
        mock_ws = MagicMock()
        msg = MagicMock()
        msg.type = WSMsgType.CLOSING
        
        result = await mock_client._LaMarzoccoCloudClient__handle_websocket_message(
            mock_ws, msg
        )
        
        assert result is True

    async def test_handle_websocket_message_closed(self, mock_client) -> None:
        """Test handling websocket CLOSED message."""
        mock_ws = MagicMock()
        msg = MagicMock()
        msg.type = WSMsgType.CLOSED
        
        result = await mock_client._LaMarzoccoCloudClient__handle_websocket_message(
            mock_ws, msg
        )
        
        assert result is True

    async def test_handle_websocket_message_error(self, mock_client) -> None:
        """Test handling websocket ERROR message."""
        mock_ws = MagicMock()
        mock_ws.exception.return_value = Exception("Connection error")
        msg = MagicMock()
        msg.type = WSMsgType.ERROR
        
        result = await mock_client._LaMarzoccoCloudClient__handle_websocket_message(
            mock_ws, msg
        )
        
        assert result is True

    async def test_handle_websocket_message_text_error(self, mock_client) -> None:
        """Test handling websocket text message with STOMP ERROR."""
        mock_ws = MagicMock()
        msg = MagicMock()
        msg.type = WSMsgType.TEXT
        
        # Create STOMP ERROR message
        error_msg = encode_stomp_ws_message(
            StompMessageType.ERROR,
            {"message": "Access denied"},
            "Authentication failed"
        )
        msg.data = error_msg
        
        result = await mock_client._LaMarzoccoCloudClient__handle_websocket_message(
            mock_ws, msg
        )
        
        assert result is False

    async def test_handle_websocket_message_non_message_type(self, mock_client) -> None:
        """Test handling websocket text with non-MESSAGE STOMP type."""
        mock_ws = MagicMock()
        msg = MagicMock()
        msg.type = WSMsgType.TEXT
        
        # Create STOMP CONNECTED message
        connected_msg = encode_stomp_ws_message(
            StompMessageType.CONNECTED,
            {"version": "1.2"},
            None
        )
        msg.data = connected_msg
        
        result = await mock_client._LaMarzoccoCloudClient__handle_websocket_message(
            mock_ws, msg
        )
        
        assert result is False

    async def test_handle_websocket_message_invalid_format(self, mock_client) -> None:
        """Test handling websocket message with invalid format."""
        mock_ws = MagicMock()
        msg = MagicMock()
        msg.type = WSMsgType.TEXT
        msg.data = "invalid message format"
        
        result = await mock_client._LaMarzoccoCloudClient__handle_websocket_message(
            mock_ws, msg
        )
        
        assert result is False

    async def test_handle_websocket_message_with_valid_message(self, mock_client) -> None:
        """Test handling websocket message with valid STOMP MESSAGE."""
        mock_ws = MagicMock()
        msg = MagicMock()
        msg.type = WSMsgType.TEXT
        
        # Create simple valid STOMP MESSAGE
        simple_msg = encode_stomp_ws_message(
            StompMessageType.MESSAGE,
            {"destination": "/topic/test"},
            '{"test": "data"}'
        )
        msg.data = simple_msg
        
        # Mock the parse method to prevent actual parsing
        with patch.object(mock_client, '_LaMarzoccoCloudClient__parse_websocket_message') as mock_parse:
            result = await mock_client._LaMarzoccoCloudClient__handle_websocket_message(
                mock_ws, msg
            )
            
            mock_parse.assert_called_once_with('{"test": "data"}', None)
        
        assert result is False

    def test_parse_websocket_message_none(self, mock_client) -> None:
        """Test parsing None websocket message."""
        # Should not raise exception
        mock_client._LaMarzoccoCloudClient__parse_websocket_message(None, None)

    def test_parse_websocket_message_with_callback(self, mock_client) -> None:
        """Test parsing websocket message with notification callback."""
        config_json = '{"connected": true, "commands": [], "widgets": []}'
        callback = MagicMock()
        
        with patch('pylamarzocco.models.ThingDashboardWebsocketConfig.from_json') as mock_from_json:
            mock_config = MagicMock()
            mock_config.commands = []
            mock_from_json.return_value = mock_config
            
            mock_client._LaMarzoccoCloudClient__parse_websocket_message(config_json, callback)
            
            callback.assert_called_once_with(mock_config)

    def test_parse_websocket_message_pending_command(self, mock_client) -> None:
        """Test parsing websocket message with pending command."""
        command_id = "test-command-id"
        mock_future = MagicMock()
        mock_client._pending_commands[command_id] = mock_future
        
        config_json = '{"connected": true, "commands": [], "widgets": []}'
        
        with patch('pylamarzocco.models.ThingDashboardWebsocketConfig.from_json') as mock_from_json:
            mock_config = MagicMock()
            mock_command = MagicMock()
            mock_command.id = command_id
            mock_config.commands = [mock_command]
            mock_from_json.return_value = mock_config
            
            mock_client._LaMarzoccoCloudClient__parse_websocket_message(config_json, None)
            
            mock_future.set_result.assert_called_once_with(mock_command)

    async def test_websocket_setup_connection_basic(self, mock_client) -> None:
        """Test basic websocket setup connection."""
        mock_ws = MagicMock()
        mock_ws.send_str = AsyncMock()
        mock_ws.receive = AsyncMock()
        mock_ws.closed = False
        
        # Mock the CONNECTED response
        connected_response = MagicMock()
        connected_response.data = encode_stomp_ws_message(
            StompMessageType.CONNECTED,
            {"version": "1.2"},
            None
        )
        mock_ws.receive.return_value = connected_response
        
        with patch.object(mock_client, 'async_get_access_token', return_value="mock-token"):
            await mock_client._LaMarzoccoCloudClient__setup_websocket_connection(
                mock_ws, "MR123456"
            )
        
        # Verify CONNECT and SUBSCRIBE messages were sent
        assert mock_ws.send_str.call_count == 2
        
        # Verify websocket details were set
        assert mock_client.websocket is not None
        assert mock_client.websocket.connected

    async def test_websocket_setup_connection_authentication_failure(self, mock_client) -> None:
        """Test websocket setup when authentication fails."""
        mock_ws = MagicMock()
        mock_ws.send_str = AsyncMock()
        mock_ws.receive = AsyncMock()
        
        # Mock an ERROR response instead of CONNECTED
        error_response = MagicMock()
        error_response.data = encode_stomp_ws_message(
            StompMessageType.ERROR,
            {"message": "Authentication failed"},
            None
        )
        mock_ws.receive.return_value = error_response
        
        with patch.object(mock_client, 'async_get_access_token', return_value="mock-token"):
            with pytest.raises(Exception):  # Should raise ClientConnectionError
                await mock_client._LaMarzoccoCloudClient__setup_websocket_connection(
                    mock_ws, "MR123456"
                )

    async def test_websocket_connect_error_handling(self, mock_client) -> None:
        """Test websocket connection error handling."""
        with patch.object(mock_client._client, 'ws_connect') as mock_ws_connect:
            mock_ws_connect.side_effect = Exception("Connection failed")
            
            # Should not raise, should handle exception gracefully
            await mock_client.websocket_connect("MR123456", auto_reconnect=False)

    def test_websocket_details_disconnect_functionality(self) -> None:
        """Test WebSocketDetails disconnect functionality."""
        mock_ws = MagicMock()
        mock_ws.closed = False
        disconnect_callback = MagicMock()
        
        details = WebSocketDetails(ws=mock_ws, disconnect_callback=disconnect_callback)
        
        assert details.connected
        
        # Test disconnect without callback
        details_no_callback = WebSocketDetails(ws=mock_ws)
        assert details_no_callback.connected