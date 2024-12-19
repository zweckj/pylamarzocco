"""Fixtures for the tests."""

# pylint: disable=W0212, W0613

import json
import re
from collections.abc import Generator
from pathlib import Path
from typing import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
from aiohttp import ClientSession
from aioresponses import aioresponses
from bleak import BleakError, BLEDevice

from pylamarzocco.clients.bluetooth import LaMarzoccoBluetoothClient
from pylamarzocco.clients.cloud import LaMarzoccoCloudClient
from pylamarzocco.clients.local import LaMarzoccoLocalClient
from pylamarzocco.const import GW_AWS_PROXY_BASE_URL, GW_MACHINE_BASE_URL, TOKEN_URL
from pylamarzocco.devices.machine import LaMarzoccoMachine

from . import GRINDER_SERIAL, MACHINE_SERIAL, init_machine


def load_fixture(device_type: str, file_name: str) -> dict:
    """Load a fixture."""
    with open(
        f"{Path(__file__).parent}/fixtures/{device_type}/{file_name}", encoding="utf-8"
    ) as f:
        return json.load(f)


@pytest.fixture(autouse=True)
def mock_response(mock_aioresponse: aioresponses) -> None:
    """Get a mock response from HTTP request."""

    # tokken
    mock_aioresponse.post(
        url=TOKEN_URL,
        status=200,
        payload={"access_token": "123", "refresh_token": "456", "expires_in": 3600},
    )
    # load config
    mock_aioresponse.get(
        url=f"{GW_MACHINE_BASE_URL}/{MACHINE_SERIAL}/configuration",
        status=200,
        payload=load_fixture("machine", "config.json"),
    )
    mock_aioresponse.get(
        url=f"{GW_MACHINE_BASE_URL}/{GRINDER_SERIAL}/configuration",
        status=200,
        payload=load_fixture("grinder", "config.json"),
    )

    # load firmware
    mock_aioresponse.get(
        url=f"{GW_MACHINE_BASE_URL}/{MACHINE_SERIAL}/firmware/",
        status=200,
        payload=load_fixture("machine", "firmware.json"),
    )
    # mock_aioresponse.get(
    #     url=f"{GW_MACHINE_BASE_URL}/{GRINDER_SERIAL}/firmware/",
    #     status=200,
    #     payload=load_fixture("grinder", "firmware.json"),
    # )

    # load statistics
    mock_aioresponse.get(
        url=f"{GW_MACHINE_BASE_URL}/{MACHINE_SERIAL}/statistics/counters",
        status=200,
        payload=load_fixture("machine", "counters.json"),
    )
    # mock_aioresponse.get(
    #     url=f"{GW_MACHINE_BASE_URL}/{GRINDER_SERIAL}/statistics/counters",
    #     status=200,
    #     payload=load_fixture("grinder", "firmware.json"),
    # )

    # post
    pattern = re.compile(rf"{GW_MACHINE_BASE_URL}/{MACHINE_SERIAL}/.*")
    mock_aioresponse.post(
        url=pattern,
        status=200,
        payload={"data": {"commandId": "123456"}},
    )

    # put
    mock_aioresponse.put(
        url=pattern,
        status=200,
        payload={"data": {"commandId": "123456"}},
    )

    # commands
    pattern = re.compile(rf"{GW_AWS_PROXY_BASE_URL}/{MACHINE_SERIAL}/commands/.*")
    mock_aioresponse.get(
        url=pattern,
        status=200,
        payload={
            "data": {"status": "COMPLETED", "responsePayload": {"status": "success"}}
        },
    )


@pytest.fixture(autouse=True)
def mock_asyncio_sleep() -> Generator[None, None, None]:
    """Mock asyncio.sleep to speed up tests."""

    with patch("pylamarzocco.clients.cloud.asyncio.sleep", new_callable=AsyncMock):
        yield


@pytest.fixture(name="mock_aioresponse")
def fixture_mock_aioresponse() -> Generator[aioresponses, None, None]:
    """Fixture for aioresponses."""
    with aioresponses() as m:
        yield m


@pytest.fixture(name="cloud_client")
async def fixture_cloud_client() -> AsyncGenerator[LaMarzoccoCloudClient, None]:
    """Fixture for a cloud client."""

    async with ClientSession() as session:
        _cloud_client = LaMarzoccoCloudClient(
            username="user", password="pass", client=session
        )
        yield _cloud_client


@pytest.fixture
async def local_machine_client() -> AsyncGenerator[LaMarzoccoLocalClient, None]:
    """Fixure for a local client"""
    async with ClientSession() as session:
        client = LaMarzoccoLocalClient("192.168.1.42", "secret", client=session)
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


@pytest.fixture
async def machine(cloud_client: LaMarzoccoCloudClient) -> LaMarzoccoMachine:
    """Get a lamarzocco machine"""
    return await init_machine(cloud_client)
