"""Tests for websocket edge cases and error scenarios."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from pylamarzocco.const import StompMessageType
from pylamarzocco.util import decode_stomp_ws_message, encode_stomp_ws_message
from pylamarzocco.models import WebSocketDetails


class TestWebSocketEdgeCases:
    """Test websocket edge cases and error scenarios."""

    def test_decode_stomp_message_empty_string(self) -> None:
        """Test decoding empty STOMP message."""
        with pytest.raises(ValueError):
            decode_stomp_ws_message("")

    def test_decode_stomp_message_no_double_newline(self) -> None:
        """Test decoding STOMP message without double newline separator."""
        with pytest.raises(ValueError):
            decode_stomp_ws_message("MESSAGE\ndestination:/topic/test")

    def test_decode_stomp_message_invalid_message_type(self) -> None:
        """Test decoding STOMP message with invalid message type."""
        with pytest.raises(ValueError):
            decode_stomp_ws_message("INVALID_TYPE\n\n")

    def test_decode_stomp_message_header_without_colon(self) -> None:
        """Test decoding STOMP message with header line without colon."""
        with pytest.raises(ValueError):
            decode_stomp_ws_message("MESSAGE\ninvalid_header_line\n\nbody")

    def test_encode_stomp_message_special_characters(self) -> None:
        """Test encoding STOMP message with special characters."""
        headers = {"destination": "/topic/test", "content-type": "application/json"}
        body = '{"message": "Hello\\nWorld\\tWith\\rSpecial\\x00Chars"}'
        
        result = encode_stomp_ws_message(StompMessageType.MESSAGE, headers, body)
        
        # Should contain all parts
        assert "MESSAGE" in result
        assert "destination:/topic/test" in result
        assert "content-type:application/json" in result
        assert body in result
        assert result.endswith("\x00")

    def test_encode_stomp_message_unicode_content(self) -> None:
        """Test encoding STOMP message with unicode content."""
        headers = {"destination": "/topic/test"}
        body = '{"message": "Hello 世界 🌍"}'
        
        result = encode_stomp_ws_message(StompMessageType.MESSAGE, headers, body)
        
        # Should handle unicode properly
        assert body in result
        
        # Test round trip
        msg_type, decoded_headers, decoded_body = decode_stomp_ws_message(result)
        assert msg_type == StompMessageType.MESSAGE
        assert decoded_headers == headers
        assert decoded_body == body

    def test_websocket_details_edge_cases(self) -> None:
        """Test WebSocketDetails edge cases."""
        # Test with None websocket
        details = WebSocketDetails(ws=None)
        assert not details.connected
        
        # Test with closed websocket
        mock_ws = MagicMock()
        mock_ws.closed = True
        details = WebSocketDetails(ws=mock_ws)
        assert not details.connected
        
        # Test state change
        mock_ws.closed = False
        assert details.connected

    async def test_websocket_details_disconnect_with_none_callback(self) -> None:
        """Test WebSocketDetails disconnect with None callback."""
        details = WebSocketDetails(ws=None, disconnect_callback=None)
        
        # Should not raise
        await details.disconnect()

    async def test_websocket_details_disconnect_callback_exception(self) -> None:
        """Test WebSocketDetails disconnect when callback raises exception."""
        def failing_callback():
            raise Exception("Callback failed")
        
        details = WebSocketDetails(disconnect_callback=failing_callback)
        
        # Should not suppress the exception
        with pytest.raises(Exception, match="Callback failed"):
            await details.disconnect()

    def test_stomp_message_types_coverage(self) -> None:
        """Test all STOMP message types can be encoded/decoded."""
        test_headers = {"test": "header"}
        test_body = "test body"
        
        # Test each message type
        for msg_type in StompMessageType:
            encoded = encode_stomp_ws_message(msg_type, test_headers, test_body)
            decoded_type, decoded_headers, decoded_body = decode_stomp_ws_message(encoded)
            
            assert decoded_type == msg_type
            assert decoded_headers == test_headers
            assert decoded_body == test_body

    def test_encode_stomp_message_large_headers(self) -> None:
        """Test encoding STOMP message with many headers."""
        headers = {f"header_{i}": f"value_{i}" for i in range(100)}
        body = "test body"
        
        result = encode_stomp_ws_message(StompMessageType.MESSAGE, headers, body)
        
        # Should handle large number of headers
        msg_type, decoded_headers, decoded_body = decode_stomp_ws_message(result)
        
        assert msg_type == StompMessageType.MESSAGE
        assert decoded_headers == headers
        assert decoded_body == body

    def test_encode_stomp_message_long_header_values(self) -> None:
        """Test encoding STOMP message with very long header values."""
        long_value = "x" * 10000
        headers = {"destination": "/topic/test", "long_header": long_value}
        body = "test body"
        
        result = encode_stomp_ws_message(StompMessageType.MESSAGE, headers, body)
        
        # Should handle long header values
        msg_type, decoded_headers, decoded_body = decode_stomp_ws_message(result)
        
        assert msg_type == StompMessageType.MESSAGE
        assert decoded_headers == headers
        assert decoded_body == body

    def test_decode_stomp_message_large_body(self) -> None:
        """Test decoding STOMP message with large body."""
        headers = {"destination": "/topic/test"}
        large_body = "x" * 100000  # 100KB body
        
        encoded = encode_stomp_ws_message(StompMessageType.MESSAGE, headers, large_body)
        msg_type, decoded_headers, decoded_body = decode_stomp_ws_message(encoded)
        
        assert msg_type == StompMessageType.MESSAGE
        assert decoded_headers == headers
        assert decoded_body == large_body

    def test_encode_decode_empty_body(self) -> None:
        """Test encoding/decoding STOMP message with empty body."""
        headers = {"destination": "/topic/test"}
        
        # Test with None body
        encoded_none = encode_stomp_ws_message(StompMessageType.MESSAGE, headers, None)
        msg_type, decoded_headers, decoded_body = decode_stomp_ws_message(encoded_none)
        
        assert msg_type == StompMessageType.MESSAGE
        assert decoded_headers == headers
        assert decoded_body == ""
        
        # Test with empty string body
        encoded_empty = encode_stomp_ws_message(StompMessageType.MESSAGE, headers, "")
        msg_type, decoded_headers, decoded_body = decode_stomp_ws_message(encoded_empty)
        
        assert msg_type == StompMessageType.MESSAGE
        assert decoded_headers == headers
        assert decoded_body == ""

    def test_header_with_multiple_colons(self) -> None:
        """Test header values containing multiple colons."""
        headers = {
            "destination": "/topic/test",
            "authorization": "Bearer token:with:multiple:colons:here",
            "url": "https://example.com:8080/path"
        }
        body = "test"
        
        encoded = encode_stomp_ws_message(StompMessageType.MESSAGE, headers, body)
        msg_type, decoded_headers, decoded_body = decode_stomp_ws_message(encoded)
        
        assert msg_type == StompMessageType.MESSAGE
        assert decoded_headers == headers
        assert decoded_body == body

    def test_websocket_connection_state_transitions(self) -> None:
        """Test WebSocketDetails connection state transitions."""
        mock_ws = MagicMock()
        details = WebSocketDetails(ws=mock_ws)
        
        # Initially open
        mock_ws.closed = False
        assert details.connected
        
        # Close it
        mock_ws.closed = True
        assert not details.connected
        
        # Reopen (simulating reconnection)
        mock_ws.closed = False
        assert details.connected