"""Tests for websocket utility functions."""

import pytest

from pylamarzocco.const import StompMessageType
from pylamarzocco.util import decode_stomp_ws_message, encode_stomp_ws_message


class TestWebSocketUtils:
    """Test websocket utility functions."""

    def test_encode_stomp_ws_message_basic(self) -> None:
        """Test basic STOMP message encoding."""
        headers = {"destination": "/topic/test", "id": "123"}
        body = "test body"
        
        result = encode_stomp_ws_message(StompMessageType.MESSAGE, headers, body)
        
        expected = "MESSAGE\ndestination:/topic/test\nid:123\n\ntest body\x00"
        assert result == expected

    def test_encode_stomp_ws_message_no_body(self) -> None:
        """Test STOMP message encoding without body."""
        headers = {"destination": "/topic/test"}
        
        result = encode_stomp_ws_message(StompMessageType.SUBSCRIBE, headers)
        
        expected = "SUBSCRIBE\ndestination:/topic/test\n\n\x00"
        assert result == expected

    def test_encode_stomp_ws_message_empty_headers(self) -> None:
        """Test STOMP message encoding with empty headers."""
        headers: dict[str, str] = {}
        body = "test"
        
        result = encode_stomp_ws_message(StompMessageType.CONNECT, headers, body)
        
        expected = "CONNECT\n\ntest\x00"
        assert result == expected

    def test_decode_stomp_ws_message_with_body(self) -> None:
        """Test STOMP message decoding with body."""
        message = "MESSAGE\ndestination:/topic/test\nid:123\n\ntest body\x00"
        
        msg_type, headers, body = decode_stomp_ws_message(message)
        
        assert msg_type == StompMessageType.MESSAGE
        assert headers == {"destination": "/topic/test", "id": "123"}
        assert body == "test body"

    def test_decode_stomp_ws_message_no_body(self) -> None:
        """Test STOMP message decoding without body."""
        message = "SUBSCRIBE\ndestination:/topic/test\n\n\x00"
        
        msg_type, headers, body = decode_stomp_ws_message(message)
        
        assert msg_type == StompMessageType.SUBSCRIBE
        assert headers == {"destination": "/topic/test"}
        assert body == ""

    def test_decode_stomp_ws_message_no_null_terminator(self) -> None:
        """Test STOMP message decoding without null terminator."""
        message = "CONNECT\nhost:example.com\n\nconnection data"
        
        msg_type, headers, body = decode_stomp_ws_message(message)
        
        assert msg_type == StompMessageType.CONNECT
        assert headers == {"host": "example.com"}
        assert body == "connection data"

    def test_decode_stomp_ws_message_header_with_colon(self) -> None:
        """Test STOMP message decoding with header containing colon."""
        message = "CONNECT\nauth:Bearer token:with:colons\n\n\x00"
        
        msg_type, headers, body = decode_stomp_ws_message(message)
        
        assert msg_type == StompMessageType.CONNECT
        assert headers == {"auth": "Bearer token:with:colons"}
        assert body == ""

    def test_encode_decode_round_trip(self) -> None:
        """Test encoding and decoding round trip."""
        original_headers = {
            "destination": "/ws/sn/MR123456/dashboard",
            "id": "sub-123",
            "subscription": "test-sub"
        }
        original_body = '{"test": "data", "number": 42}'
        
        # Encode
        encoded = encode_stomp_ws_message(
            StompMessageType.MESSAGE, original_headers, original_body
        )
        
        # Decode
        msg_type, decoded_headers, decoded_body = decode_stomp_ws_message(encoded)
        
        # Verify
        assert msg_type == StompMessageType.MESSAGE
        assert decoded_headers == original_headers
        assert decoded_body == original_body

    def test_all_stomp_message_types(self) -> None:
        """Test encoding/decoding all STOMP message types."""
        headers = {"test": "header"}
        
        for msg_type in StompMessageType:
            encoded = encode_stomp_ws_message(msg_type, headers, "body")
            decoded_type, decoded_headers, decoded_body = decode_stomp_ws_message(encoded)
            
            assert decoded_type == msg_type
            assert decoded_headers == headers
            assert decoded_body == "body"

    def test_decode_stomp_ws_message_error_type(self) -> None:
        """Test decoding ERROR message type."""
        message = "ERROR\nmessage:Invalid destination\n\nError details\x00"
        
        msg_type, headers, body = decode_stomp_ws_message(message)
        
        assert msg_type == StompMessageType.ERROR
        assert headers == {"message": "Invalid destination"}
        assert body == "Error details"