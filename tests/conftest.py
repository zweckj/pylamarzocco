"""Setting up pytest fixtures for the tests."""

import asyncio
import json
from collections.abc import AsyncGenerator, Awaitable, Callable
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from aiohttp import ClientSession, web
from aiointercept import aiointercept
from cryptography.hazmat.primitives.asymmetric.ec import SECP256R1, generate_private_key
from yarl import URL

from pylamarzocco import LaMarzoccoBluetoothClient, LaMarzoccoCloudClient
from pylamarzocco.const import (
    BASE_URL,
    CUSTOMER_APP_URL,
    MachineMode,
    MachineState,
    StompMessageType,
    WidgetType,
)
from pylamarzocco.models import (
    BluetoothCommandStatus,
    MachineStatus,
    ThingDashboardWebsocketConfig,
    Widget,
)
from pylamarzocco.util import (
    InstallationKey,
    decode_stomp_ws_message,
    encode_stomp_ws_message,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# aiointercept only restores the https scheme of intercepted requests, so the
# client's wss:// endpoint has to be registered under https://.
WEBSOCKET_URL = f"https://{BASE_URL}/ws/connect"
HANDSHAKE_KEY = ("GET", URL(WEBSOCKET_URL))

StompFrame = tuple[StompMessageType, dict[str, str], str | None]

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


def add_websocket_endpoint(
    mock: aiointercept,
    session: Callable[[web.WebSocketResponse], Awaitable[None]],
) -> asyncio.Event:
    """Serve one websocket connection from aiointercept's server.

    aiointercept can only build plain HTTP responses, so swap the handler it
    registers for one that upgrades the connection and runs ``session``. The
    server runs on its own thread, so the returned event signals when the
    session has ended.
    """
    loop = asyncio.get_running_loop()
    session_finished = asyncio.Event()

    async def handler(request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        try:
            await ws.prepare(request)
            await session(ws)
        finally:
            loop.call_soon_threadsafe(session_finished.set)
        return ws

    mock_response = mock.get(WEBSOCKET_URL)
    mock_response._handler = handler  # pylint: disable=protected-access
    return session_finished


async def receive_frame(ws: web.WebSocketResponse) -> StompFrame:
    """Receive and decode the next STOMP frame sent by the client."""
    return decode_stomp_ws_message(await ws.receive_str())


async def accept_stomp_connection(
    ws: web.WebSocketResponse, frames: list[StompFrame]
) -> None:
    """Answer the client's CONNECT and record it together with its SUBSCRIBE."""
    frames.append(await receive_frame(ws))
    await ws.send_str(
        encode_stomp_ws_message(StompMessageType.CONNECTED, {"version": "1.2"})
    )
    frames.append(await receive_frame(ws))


def dashboard_message(serial: str, update: dict[str, Any]) -> str:
    """Encode a dashboard update as the STOMP MESSAGE the cloud pushes."""
    return encode_stomp_ws_message(
        StompMessageType.MESSAGE,
        {"destination": f"/ws/sn/{serial}/dashboard"},
        json.dumps(update),
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
