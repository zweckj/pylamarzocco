"""Tests for websocket related functionality."""

import json

from syrupy import SnapshotAssertion

from pylamarzocco.const import CommandStatus, StompMessageType
from pylamarzocco.models import ThingDashboardWebsocketConfig
from pylamarzocco.util import decode_stomp_ws_message, encode_stomp_ws_message

from .conftest import load_fixture


async def test_encode_stomp_ws_message(snapshot: SnapshotAssertion) -> None:
    """Test the encode_stomp_ws_message function."""

    fixture = load_fixture("machine", "config_micra.json")
    device_config = ThingDashboardWebsocketConfig.from_dict(fixture)
    headers = {
        "destination": "/topic/test",
        "id": "test-id",
        "subscription": "test-subscription",
    }
    message = encode_stomp_ws_message(
        StompMessageType.MESSAGE, headers, json.dumps(fixture)
    )
    assert message == snapshot

    msg_type, headers_decoded, body = decode_stomp_ws_message(message)

    assert body
    assert msg_type is StompMessageType.MESSAGE
    assert headers_decoded == headers
    assert ThingDashboardWebsocketConfig.from_json(body) == device_config


async def test_websocket_config_parses_failed_command() -> None:
    """A dashboard update carrying a Failed command result parses."""

    fixture = load_fixture("machine", "config_micra.json") | {
        "commands": [{"id": "mock-id", "status": "Failed", "errorCode": None}]
    }
    config = ThingDashboardWebsocketConfig.from_dict(fixture)

    assert config.commands[0].status is CommandStatus.FAILED
