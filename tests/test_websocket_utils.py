"""Tests for websocket utility functions."""

import pytest

from pylamarzocco.const import StompMessageType
from pylamarzocco.util import decode_stomp_ws_message, encode_stomp_ws_message


@pytest.mark.parametrize(
    ("msg_type", "headers", "body", "wire"),
    [
        (
            StompMessageType.MESSAGE,
            {"destination": "/topic/test", "id": "123"},
            "test body",
            "MESSAGE\ndestination:/topic/test\nid:123\n\ntest body\x00",
        ),
        (
            StompMessageType.SUBSCRIBE,
            {"destination": "/topic/test"},
            None,
            "SUBSCRIBE\ndestination:/topic/test\n\n\x00",
        ),
        (StompMessageType.CONNECT, {}, "test", "CONNECT\n\ntest\x00"),
    ],
)
def test_encode_stomp_ws_message(
    msg_type: StompMessageType, headers: dict[str, str], body: str | None, wire: str
) -> None:
    """Test encoding STOMP messages."""
    assert encode_stomp_ws_message(msg_type, headers, body) == wire


@pytest.mark.parametrize(
    ("wire", "msg_type", "headers", "body"),
    [
        (
            "MESSAGE\ndestination:/topic/test\nid:123\n\ntest body\x00",
            StompMessageType.MESSAGE,
            {"destination": "/topic/test", "id": "123"},
            "test body",
        ),
        (
            "SUBSCRIBE\ndestination:/topic/test\n\n\x00",
            StompMessageType.SUBSCRIBE,
            {"destination": "/topic/test"},
            "",
        ),
        (
            "CONNECT\nhost:example.com\n\nconnection data",
            StompMessageType.CONNECT,
            {"host": "example.com"},
            "connection data",
        ),
        (
            "CONNECT\nauth:Bearer token:with:colons\n\n\x00",
            StompMessageType.CONNECT,
            {"auth": "Bearer token:with:colons"},
            "",
        ),
        (
            "ERROR\nmessage:Invalid destination\n\nError details\x00",
            StompMessageType.ERROR,
            {"message": "Invalid destination"},
            "Error details",
        ),
    ],
)
def test_decode_stomp_ws_message(
    wire: str, msg_type: StompMessageType, headers: dict[str, str], body: str
) -> None:
    """Test decoding STOMP messages."""
    assert decode_stomp_ws_message(wire) == (msg_type, headers, body)


@pytest.mark.parametrize(
    "wire",
    [
        "",
        "MESSAGE\ndestination:/topic/test",
        "INVALID_TYPE\n\n",
        "MESSAGE\ninvalid_header_line\n\nbody",
    ],
)
def test_decode_stomp_ws_message_invalid(wire: str) -> None:
    """Test decoding malformed STOMP messages raises."""
    with pytest.raises(ValueError):
        decode_stomp_ws_message(wire)


@pytest.mark.parametrize("msg_type", list(StompMessageType))
@pytest.mark.parametrize(
    ("headers", "body"),
    [
        (
            {
                "destination": "/ws/sn/MR123456/dashboard",
                "id": "sub-123",
                "subscription": "test-sub",
            },
            '{"test": "data", "number": 42}',
        ),
        (
            {"destination": "/topic/test", "content-type": "application/json"},
            '{"message": "Hello\\nWorld\\tWith\\rSpecial\\x00Chars"}',
        ),
        ({"destination": "/topic/test"}, '{"message": "Hello 世界 🌍"}'),
        ({f"header_{i}": f"value_{i}" for i in range(100)}, "test body"),
        ({"destination": "/topic/test", "long_header": "x" * 10000}, "test body"),
        ({"destination": "/topic/test"}, "x" * 100000),
        (
            {
                "authorization": "Bearer token:with:multiple:colons:here",
                "url": "https://example.com:8080/path",
            },
            "test",
        ),
        ({"destination": "/topic/test"}, ""),
    ],
    ids=[
        "json",
        "escapes",
        "unicode",
        "many_headers",
        "long_header",
        "large_body",
        "colons",
        "empty_body",
    ],
)
def test_encode_decode_round_trip(
    msg_type: StompMessageType, headers: dict[str, str], body: str
) -> None:
    """Test decoding an encoded message returns the original parts."""
    encoded = encode_stomp_ws_message(msg_type, headers, body)
    assert decode_stomp_ws_message(encoded) == (msg_type, headers, body)


def test_encode_decode_none_body() -> None:
    """Test a message without body decodes to an empty body."""
    encoded = encode_stomp_ws_message(
        StompMessageType.MESSAGE, {"destination": "/topic/test"}, None
    )
    assert decode_stomp_ws_message(encoded) == (
        StompMessageType.MESSAGE,
        {"destination": "/topic/test"},
        "",
    )
