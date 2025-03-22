"""Tests for websocket related functionality."""

from pylamarzocco.models.config import DeviceConfig
from pylamarzocco.const import StompMessageType
from pylamarzocco.util import encode_stomp_ws_message, decode_stomp_ws_message
from .conftest import load_fixture

import json

from syrupy import SnapshotAssertion

async def test_encode_stomp_ws_message(snapshot: SnapshotAssertion) -> None:
    """Test the encode_stomp_ws_message function."""
    
    fixture = load_fixture("machine", "config_micra.json")
    device_config = DeviceConfig.from_dict(fixture)
    headers = {
        "destination": "/topic/test",
        "id": "test-id",
        "subscription": "test-subscription",
    }
    message = encode_stomp_ws_message(StompMessageType.MESSAGE, headers, json.dumps(fixture))
    assert message == snapshot

    msg_type, headers_decoded, body = decode_stomp_ws_message(message)

    assert body
    assert msg_type is StompMessageType.MESSAGE
    assert headers_decoded == headers
    assert DeviceConfig.from_json(body) == device_config

