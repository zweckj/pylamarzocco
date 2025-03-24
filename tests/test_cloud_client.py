"""Testing the cloud client."""

from unittest.mock import patch

from aioresponses import aioresponses
from syrupy import SnapshotAssertion

from pylamarzocco.clients.cloud import LaMarzoccoCloudClient
from pylamarzocco.const import CUSTOMER_APP_URL, SteamTargetLevel

from .conftest import load_fixture


async def test_access_token(mock_aioresponse: aioresponses) -> None:
    """Test getting the dashboard for a thing."""

    mock_aioresponse.post(
        url=f"{CUSTOMER_APP_URL}/auth/signin",
        status=200,
        body={
            "username": "test",
            "password": "test",
        },
        payload={
            "id": "mock-id",
            "accessToken": "mock-access",
            "refreshToken": "mock-refresh",
            "tokenType": "Bearer",
            "username": "mock-username",
            "email": "mock-email",
        },
    )

    client = LaMarzoccoCloudClient("test", "test")
    result = await client.async_get_access_token()
    assert result == "mock-access"

    # now get one again to get from cache
    mock_aioresponse.post(
        url=f"{CUSTOMER_APP_URL}/auth/signin",
        status=200,
        payload={
            "accessToken": "new-new-token",
            "refreshToken": "mock-refresh",
        },
    )
    result = await client.async_get_access_token()
    assert result == "mock-access"

    # now get one from refresh token
    mock_aioresponse.post(
        url=f"{CUSTOMER_APP_URL}/auth/refreshtoken",
        body={
            "username": "test",
            "refreshToken": "mock-refresh",
        },
        payload={
            "accessToken": "new-token",
            "refreshToken": "new-refresh",
            "tokenType": "Bearer",
        },
    )

    with patch("pylamarzocco.clients.cloud.TOKEN_TIME_TO_REFRESH", new=432001):
        result = await client.async_get_access_token()

    assert result == "new-token"


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


async def test_set_power(mock_aioresponse: aioresponses) -> None:
    """Test setting the power for a thing."""

    serial = "MR123456"

    mock_aioresponse.post(
        url=f"{CUSTOMER_APP_URL}/things/{serial}/command/CoffeeMachineChangeMode",
        status=200,
        body={"mode": "StandBy"},
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


async def test_set_steam(mock_aioresponse: aioresponses) -> None:
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


async def test_set_steam_target_level(mock_aioresponse: aioresponses) -> None:
    """Test setting the steam target level for a thing."""

    serial = "MR123456"

    mock_aioresponse.post(
        url=f"{CUSTOMER_APP_URL}/things/{serial}/command/CoffeeMachineSettingSteamBoilerTargetLevel",
        status=200,
        body={
            "boilerIndex": 1,
            "targetLevel": "Level1",
        },
        payload={
            "id": "mock-id",
            "status": "Pending",
            "error_code": None,
        },
    )

    client = LaMarzoccoCloudClient("test", "test")
    result = await client.set_steam_target_level(serial, SteamTargetLevel.LEVEL_1)
    assert result.status == "Pending"
    assert result.error_code is None
