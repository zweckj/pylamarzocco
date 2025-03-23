"""Testing the cloud client."""

from aioresponses import aioresponses
from syrupy import SnapshotAssertion

from pylamarzocco.const import CUSTOMER_APP_URL
from pylamarzocco.clients.cloud import LaMarzoccoCloudClient

from .conftest import load_fixture


async def test_get_thing_dashboard(
    mock_aioresponse: aioresponses, snapshot: SnapshotAssertion
) -> None:
    """Test getting the dashboard for a thing."""

    serial = "MR123456"

    mock_aioresponse.get(
        url=f"{CUSTOMER_APP_URL}/things/{serial}/dashboard",
        status=200,
        payload=load_fixture("machine", "dashboard_micra.json"),
    )

    client = LaMarzoccoCloudClient("test", "test")
    result = await client.get_thing_dashboard(serial)
    assert result.to_dict() == snapshot


async def test_get_thing_settings(
    mock_aioresponse: aioresponses, snapshot: SnapshotAssertion
) -> None:
    """Test getting the settings for a thing."""

    serial = "MR123456"

    mock_aioresponse.get(
        url=f"{CUSTOMER_APP_URL}/things/{serial}/settings",
        status=200,
        payload=load_fixture("machine", "settings_micra.json"),
    )

    client = LaMarzoccoCloudClient("test", "test")
    result = await client.get_thing_settings(serial)
    assert result.to_dict() == snapshot

async def test_list_things(
    mock_aioresponse: aioresponses, snapshot: SnapshotAssertion
) -> None:
    """Test getting the list of things."""

    mock_aioresponse.get(
        url=f"{CUSTOMER_APP_URL}/things",
        status=200,
        payload=[load_fixture("machine", "settings_micra.json")],
    )

    client = LaMarzoccoCloudClient("test", "test")
    result = await client.list_things()
    assert result[0].to_dict() == snapshot

async def test_set_power(
    mock_aioresponse: aioresponses
) -> None:
    """Test setting the power for a thing."""

    serial = "MR123456"

    mock_aioresponse.post(
        url=f"{CUSTOMER_APP_URL}/things/{serial}/command/CoffeeMachineChangeMode",
        status=200,
        body={
            "mode": "StandBy"
        },
        payload={
            "id": "mock-id",
            "status": "Pending",
            "error_code": None,
        },
    )

    client = LaMarzoccoCloudClient("test", "test")
    result = await client.set_power(serial, False)
    assert result.status == "Pending"
    assert result.error_code is None

async def test_set_steam(
    mock_aioresponse: aioresponses
) -> None:
    """Test setting the steam for a thing."""

    serial = "MR123456"

    mock_aioresponse.post(
        url=f"{CUSTOMER_APP_URL}/things/{serial}/command/CoffeeMachineSettingSteamBoilerEnabled",
        status=200,
        body={
            "boilerIndex": 1,
            "enabled": True,
        },
        payload={
            "id": "mock-id",
            "status": "Pending",
            "error_code": None,
        },
    )

    client = LaMarzoccoCloudClient("test", "test")
    result = await client.set_steam(serial, True)
    assert result.status == "Pending"
    assert result.error_code is None