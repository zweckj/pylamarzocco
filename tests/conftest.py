"""Setting up pytest fixtures for the tests."""

import json
from collections.abc import AsyncGenerator
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from aiohttp import ClientSession
from aiointercept import aiointercept
from cryptography.hazmat.primitives.asymmetric.ec import SECP256R1, generate_private_key

from pylamarzocco import LaMarzoccoBluetoothClient, LaMarzoccoCloudClient
from pylamarzocco.const import CUSTOMER_APP_URL, MachineMode, MachineState, WidgetType
from pylamarzocco.models import (
    BluetoothCommandStatus,
    MachineStatus,
    ThingDashboardWebsocketConfig,
    Widget,
)
from pylamarzocco.util import InstallationKey

FIXTURES_DIR = Path(__file__).parent / "fixtures"

MOCK_SECRET_DATA = InstallationKey(
    secret=bytes(32),
    private_key=generate_private_key(SECP256R1()),
    installation_id="mock-installation-id",
)


def load_fixture(device_type: str, file_name: str) -> dict:
    """Load a fixture."""
    with open(FIXTURES_DIR / device_type / file_name, encoding="utf-8") as f:
        return json.load(f)


def machine_status(
    status: MachineState,
    brewing_start_time: datetime | None = None,
    mode: MachineMode = MachineMode.BREWING_MODE,
) -> MachineStatus:
    """Return a machine status widget."""
    return MachineStatus(
        status=status,
        available_modes=[MachineMode.BREWING_MODE, MachineMode.STANDBY],
        mode=mode,
        next_status=None,
        brewing_start_time=brewing_start_time,
    )


def websocket_config(status: MachineStatus | None) -> ThingDashboardWebsocketConfig:
    """Return a dashboard websocket update with the given machine status."""
    widgets = (
        [Widget(code=WidgetType.CM_MACHINE_STATUS, index=1, output=status)]
        if status is not None
        else []
    )
    return ThingDashboardWebsocketConfig(
        widgets=widgets,
        config={widget.code: widget.output for widget in widgets},
        connected=True,
        connection_date=0,
        uuid="uuid",
        commands=[],
    )


@pytest.fixture(name="mock_aiointercept")
async def fixture_mock_aiointercept() -> AsyncGenerator[aiointercept]:
    """Fixture for aiointercept."""
    async with aiointercept(mock_external_urls=True) as m:
        yield m


@pytest.fixture
def mock_access_token(mock_aiointercept: aiointercept) -> None:
    """Mock getting an access token."""
    mock_aiointercept.post(
        url=f"{CUSTOMER_APP_URL}/auth/signin",
        status=200,
        payload={
            "accessToken": "mock-access",
            "refreshToken": "mock-refresh",
        },
        repeat=True,
    )


@pytest.fixture(name="client")
async def fixture_client() -> AsyncGenerator[LaMarzoccoCloudClient]:
    """Return a cloud client whose session is closed after the test."""
    async with ClientSession() as session:
        yield LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA, session)


@pytest.fixture(name="mock_cloud_client")
def mock_lm_cloud_client() -> MagicMock:
    """Mock the LaMarzoccoCloudClient."""
    return MagicMock(spec=LaMarzoccoCloudClient)


@pytest.fixture(name="mock_bluetooth_client")
def mock_lm_bluetooth_client() -> MagicMock:
    """Mock the LaMarzoccoBluetoothClient with successful commands."""
    client = MagicMock(spec=LaMarzoccoBluetoothClient)
    client.set_power.return_value = BluetoothCommandStatus(
        id="ble", message="power on", status="success"
    )
    client.set_steam.return_value = BluetoothCommandStatus(
        id="ble", message="boiler enable success", status="success"
    )
    client.set_temp.return_value = BluetoothCommandStatus(
        id="ble", message="Setting Temperature Success", status="success"
    )
    client.set_smart_standby.return_value = BluetoothCommandStatus(
        id="ble", message="Success", status="success"
    )
    client.get_plumbed_in.return_value = False
    return client


@pytest.fixture(name="serial")
def mock_serial() -> str:
    """Return the serial number of the mocked machine."""
    return "MR123456"
