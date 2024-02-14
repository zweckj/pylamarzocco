"""Fixtures for the tests."""

# pylint: disable=W0212, W0613

import json
from collections.abc import Generator
from http import HTTPMethod
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from bleak import BLEDevice, BleakError
from httpx import Response

from lmcloud.client_bluetooth import LaMarzoccoBluetoothClient
from lmcloud.client_cloud import LaMarzoccoCloudClient
from lmcloud.client_local import LaMarzoccoLocalClient

from . import (
    MACHINE_SERIAL,
    GRINDER_SERIAL,
)


def load_fixture(device_type: str, file_name: str) -> dict:
    """Load a fixture."""
    with open(
        f"{Path(__file__).parent}/fixtures/{device_type}/{file_name}", encoding="utf-8"
    ) as f:
        return json.load(f)


def get_mock_response(*args, **kwargs) -> Response:
    """Get a mock response from HTTP request."""
    method: HTTPMethod = args[0]
    url: str = str(args[1])

    if MACHINE_SERIAL in url:
        device_type = "machine"
    elif GRINDER_SERIAL in url:
        device_type = "grinder"
    else:
        raise ValueError(f"Unknown device in URL: {url}")

    data: dict = {"data": {"commandId": "123456"}}
    if "configuration" in url:
        data = load_fixture(device_type, "config.json")
    elif "firmware" in url:
        data = load_fixture(device_type, "firmware.json")
    elif "counters" in url:
        data = load_fixture(device_type, "counters.json")
    elif "/commands/" in url:
        data["data"] = {"status": "COMPLETED", "responsePayload": {"status": "success"}}

    if method == HTTPMethod.GET:
        return Response(200, json=data)
    return Response(204, json=data)


@pytest.fixture(autouse=True)
def mock_asyncio_sleep():
    """Mock asyncio.sleep to speed up tests."""

    with patch("asyncio.sleep", new_callable=AsyncMock):
        yield


def get_local_machine_mock_response(*args, **kwargs) -> Response:
    """Get a mock response from local API."""

    data = load_fixture("machine", "config.json")["data"]
    return Response(200, json=data)


@pytest.fixture
def cloud_client() -> Generator[LaMarzoccoCloudClient, None, None]:
    """Fixture for a cloud client."""

    client = LaMarzoccoCloudClient("username", "password")

    oauth_client = AsyncMock()
    oauth_client.request.side_effect = get_mock_response

    client._oauth_client = oauth_client
    yield client


@pytest.fixture
def local_machine_client() -> Generator[LaMarzoccoLocalClient, None, None]:
    """Fixure for a local client"""
    httpx_client = AsyncMock()
    httpx_client.get.side_effect = get_local_machine_mock_response
    client = LaMarzoccoLocalClient("192.168.1.42", "secret", client=httpx_client)
    yield client


@pytest.fixture
def bluetooth_client() -> Generator[LaMarzoccoBluetoothClient, None, None]:
    """Fixture for a bluetooth client."""
    ble_device = BLEDevice(
        address="00:11:22:33:44:55",
        name="MyMachine",
        details={"path": "path/to/device"},
        rssi=50,
    )

    bt_client = LaMarzoccoBluetoothClient("username", "serial", "token", ble_device)
    bt_client._client = AsyncMock()
    bt_client._client.is_connected = True
    bt_client._client.write_gatt_char.side_effect = BleakError("Failed to write")
    yield bt_client
