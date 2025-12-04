"""Comprehensive tests for websocket utility functions."""

import pytest

from pylamarzocco.const import StompMessageType
from pylamarzocco.util import decode_stomp_ws_message, encode_stomp_ws_message


class TestWebSocketUtilsComprehensive:
    """Comprehensive tests for websocket utility functions."""

    def test_encode_stomp_ws_message_basic(self) -> None:
        """Test basic STOMP message encoding."""
        headers = {"destination": "/topic/test", "content-type": "application/json"}
        body = '{"message": "test"}'
        
        result = encode_stomp_ws_message(StompMessageType.MESSAGE, headers, body)
        
        assert isinstance(result, str)
        assert result.startswith("MESSAGE\n")
        assert "destination:/topic/test" in result
        assert "content-type:application/json" in result
        assert result.endswith('{"message": "test"}\x00')

    def test_encode_stomp_ws_message_no_body(self) -> None:
        """Test STOMP message encoding without body."""
        headers = {"destination": "/topic/test"}
        
        result = encode_stomp_ws_message(StompMessageType.CONNECT, headers)
        
        assert result.startswith("CONNECT\n")
        assert "destination:/topic/test" in result
        assert result.endswith("\n\n\x00")

    def test_encode_stomp_ws_message_empty_headers(self) -> None:
        """Test STOMP message encoding with empty headers."""
        result = encode_stomp_ws_message(StompMessageType.UNSUBSCRIBE, {}, "body")
        
        assert result == "UNSUBSCRIBE\n\nbody\x00"

    def test_encode_stomp_ws_message_empty_body(self) -> None:
        """Test STOMP message encoding with empty body."""
        headers = {"test": "value"}
        
        result = encode_stomp_ws_message(StompMessageType.MESSAGE, headers, "")
        
        assert "test:value" in result
        assert result.endswith("\n\n\x00")

    def test_encode_stomp_ws_message_all_message_types(self) -> None:
        """Test encoding with all supported message types."""
        headers = {"test": "header"}
        body = "test body"
        
        for msg_type in StompMessageType:
            result = encode_stomp_ws_message(msg_type, headers, body)
            assert result.startswith(f"{msg_type.value}\n")
            assert "test:header" in result
            assert result.endswith("test body\x00")

    def test_encode_stomp_ws_message_special_characters(self) -> None:
        """Test encoding with special characters in headers and body."""
        headers = {
            "header1": "value:with:colons",
            "unicode": "üñíçødé"
        }
        body = "Body with\nspecial:characters\nand üñíçødé"
        
        result = encode_stomp_ws_message(StompMessageType.MESSAGE, headers, body)
        
        assert "header1:value:with:colons" in result
        assert "unicode:üñíçødé" in result
        assert body in result

    def test_decode_stomp_ws_message_basic(self) -> None:
        """Test basic STOMP message decoding."""
        message = "MESSAGE\ndestination:/topic/test\ncontent-type:application/json\n\n{\"message\": \"test\"}\x00"
        
        msg_type, headers, body = decode_stomp_ws_message(message)
        
        assert msg_type == StompMessageType.MESSAGE
        assert headers == {"destination": "/topic/test", "content-type": "application/json"}
        assert body == '{"message": "test"}'

    def test_decode_stomp_ws_message_no_body(self) -> None:
        """Test decoding STOMP message without body."""
        message = "CONNECT\ndestination:/topic/test\n\n\x00"
        
        msg_type, headers, body = decode_stomp_ws_message(message)
        
        assert msg_type == StompMessageType.CONNECT
        assert headers == {"destination": "/topic/test"}
        assert body == ""

    def test_decode_stomp_ws_message_empty_headers(self) -> None:
        """Test decoding STOMP message with empty headers."""
        message = "UNSUBSCRIBE\n\nbody content\x00"
        
        msg_type, headers, body = decode_stomp_ws_message(message)
        
        assert msg_type == StompMessageType.UNSUBSCRIBE
        assert headers == {}
        assert body == "body content"

    def test_decode_stomp_ws_message_no_null_terminator(self) -> None:
        """Test decoding STOMP message without null terminator."""
        message = "MESSAGE\ntest:header\n\nbody content"
        
        msg_type, headers, body = decode_stomp_ws_message(message)
        
        assert msg_type == StompMessageType.MESSAGE
        assert headers == {"test": "header"}
        assert body == "body content"

    def test_decode_stomp_ws_message_multiple_colons_in_header_value(self) -> None:
        """Test decoding headers with multiple colons in values."""
        message = "MESSAGE\nurl:https://example.com:8080/path\n\nbody\x00"
        
        msg_type, headers, body = decode_stomp_ws_message(message)
        
        assert msg_type == StompMessageType.MESSAGE
        assert headers == {"url": "https://example.com:8080/path"}
        assert body == "body"

    def test_decode_stomp_ws_message_all_message_types(self) -> None:
        """Test decoding all supported message types."""
        for msg_type in StompMessageType:
            message = f"{msg_type.value}\ntest:header\n\ntest body\x00"
            
            decoded_type, headers, body = decode_stomp_ws_message(message)
            
            assert decoded_type == msg_type
            assert headers == {"test": "header"}
            assert body == "test body"

    def test_decode_stomp_ws_message_special_characters(self) -> None:
        """Test decoding with special characters."""
        message = "MESSAGE\nheader1:value:with:colons\nunicode:üñíçødé\n\nBody with\nspecial:characters\nand üñíçødé\x00"
        
        msg_type, headers, body = decode_stomp_ws_message(message)
        
        assert msg_type == StompMessageType.MESSAGE
        assert headers["header1"] == "value:with:colons"
        assert headers["unicode"] == "üñíçødé"
        assert body == "Body with\nspecial:characters\nand üñíçødé"

    def test_encode_decode_roundtrip(self) -> None:
        """Test that encoding and then decoding produces original message."""
        original_headers = {
            "destination": "/topic/test",
            "content-type": "application/json",
            "custom": "value:with:colons"
        }
        original_body = '{"test": "message", "unicode": "üñíçødé"}'
        original_type = StompMessageType.MESSAGE
        
        # Encode
        encoded = encode_stomp_ws_message(original_type, original_headers, original_body)
        
        # Decode
        decoded_type, decoded_headers, decoded_body = decode_stomp_ws_message(encoded)
        
        # Verify roundtrip
        assert decoded_type == original_type
        assert decoded_headers == original_headers
        assert decoded_body == original_body

    def test_encode_decode_roundtrip_no_body(self) -> None:
        """Test roundtrip with no body."""
        original_headers = {"test": "header"}
        original_type = StompMessageType.CONNECT
        
        encoded = encode_stomp_ws_message(original_type, original_headers)
        decoded_type, decoded_headers, decoded_body = decode_stomp_ws_message(encoded)
        
        assert decoded_type == original_type
        assert decoded_headers == original_headers
        assert decoded_body == ""

    def test_encode_decode_roundtrip_empty_headers(self) -> None:
        """Test roundtrip with empty headers."""
        original_body = "test body"
        original_type = StompMessageType.MESSAGE
        
        encoded = encode_stomp_ws_message(original_type, {}, original_body)
        decoded_type, decoded_headers, decoded_body = decode_stomp_ws_message(encoded)
        
        assert decoded_type == original_type
        assert decoded_headers == {}
        assert decoded_body == original_body

    def test_decode_malformed_message_no_double_newline(self) -> None:
        """Test decoding malformed message without double newline separator."""
        message = "SEND\nheader:value\nbody"
        
        with pytest.raises(ValueError):
            decode_stomp_ws_message(message)

    def test_decode_invalid_message_type(self) -> None:
        """Test decoding with invalid message type."""
        message = "INVALID_TYPE\nheader:value\n\nbody\x00"
        
        with pytest.raises(ValueError):
            decode_stomp_ws_message(message)

    def test_encode_decode_large_message(self) -> None:
        """Test encoding/decoding large messages."""
        large_body = "x" * 10000  # 10KB body
        large_headers = {f"header{i}": f"value{i}" * 100 for i in range(10)}
        
        encoded = encode_stomp_ws_message(StompMessageType.MESSAGE, large_headers, large_body)
        decoded_type, decoded_headers, decoded_body = decode_stomp_ws_message(encoded)
        
        assert decoded_type == StompMessageType.MESSAGE
        assert decoded_headers == large_headers
        assert decoded_body == large_body

    def test_encode_decode_binary_like_content(self) -> None:
        """Test encoding/decoding content that looks like binary."""
        binary_like_body = "\x01\x02\x03\x04\x05"
        headers = {"content-type": "application/octet-stream"}
        
        encoded = encode_stomp_ws_message(StompMessageType.MESSAGE, headers, binary_like_body)
        decoded_type, decoded_headers, decoded_body = decode_stomp_ws_message(encoded)
        
        assert decoded_type == StompMessageType.MESSAGE
        assert decoded_headers == headers
        assert decoded_body == binary_like_body