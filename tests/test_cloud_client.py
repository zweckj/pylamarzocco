"""Testing the cloud client."""

from __future__ import annotations

from collections.abc import Generator
from http import HTTPMethod
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aioresponses import aioresponses
from syrupy import SnapshotAssertion
from yarl import URL

from pylamarzocco.clients import LaMarzoccoCloudClient
from pylamarzocco.const import (
    CUSTOMER_APP_URL,
    CommandStatus,
    PreExtractionMode,
    SmartStandByType,
    SteamTargetLevel,
    WeekDay,
)
from pylamarzocco.models import (
    CommandResponse,
    PrebrewSettingTimes,
    SecondsInOut,
    WakeUpScheduleSettings,
)

from .conftest import load_fixture

MOCK_COMMAND_RESPONSE = [
    {
        "id": "mock-id",
        "status": "Pending",
        "error_code": None,
    }
]


@pytest.fixture(name="mock_ws_command_response")
def websocket_command_response() -> CommandResponse:
    """Mock websocket command response."""
    return CommandResponse(
        id="mock-id",
        status=CommandStatus.SUCCESS,
    )


@pytest.fixture(name="mock_wait_for_ws_command_response")
def wait_for_ws_command_response(
    mock_ws_command_response: CommandResponse,
) -> Generator[AsyncMock]:
    """Mock the wait for."""
    with patch(
        "pylamarzocco.clients._cloud.wait_for",
        new=AsyncMock(return_value=mock_ws_command_response),
    ) as mock_wait_for:
        yield mock_wait_for


@pytest.fixture(name="mock_websocket")
def websocket_mock() -> Generator[MagicMock]:
    """Return a mocked websocket"""
    mock_ws = MagicMock()
    mock_ws.connected = True

    with patch("pylamarzocco.clients._cloud.WebSocketDetails", return_value=mock_ws):
        yield mock_ws


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

    with patch("pylamarzocco.clients._cloud.TOKEN_TIME_TO_REFRESH", new=432001):
        result = await client.async_get_access_token()

    assert result == "new-token"


@pytest.mark.parametrize("model", ["micra", "gs3av", "mini", "minir"])
async def test_get_thing_dashboard(
    mock_aioresponse: aioresponses,
    model: str,
    serial: str,
    snapshot: SnapshotAssertion,
) -> None:
    """Test getting the dashboard for a thing."""

    mock_aioresponse.get(
        url=f"{CUSTOMER_APP_URL}/things/{serial}/dashboard",
        status=200,
        payload=load_fixture("machine", f"dashboard_{model}.json"),
    )

    client = LaMarzoccoCloudClient("test", "test")
    result = await client.get_thing_dashboard(serial)
    assert result.to_dict() == snapshot


async def test_get_thing_settings(
    mock_aioresponse: aioresponses, serial: str, snapshot: SnapshotAssertion
) -> None:
    """Test getting the settings for a thing."""

    mock_aioresponse.get(
        url=f"{CUSTOMER_APP_URL}/things/{serial}/settings",
        status=200,
        payload=load_fixture("machine", "settings_micra.json"),
    )

    client = LaMarzoccoCloudClient("test", "test")
    result = await client.get_thing_settings(serial)
    assert result.to_dict() == snapshot


async def test_get_thing_schedule(
    mock_aioresponse: aioresponses, serial: str, snapshot: SnapshotAssertion
) -> None:
    """Test getting the schedule for a thing."""

    mock_aioresponse.get(
        url=f"{CUSTOMER_APP_URL}/things/{serial}/scheduling",
        status=200,
        payload=load_fixture("machine", "schedule.json"),
    )

    client = LaMarzoccoCloudClient("test", "test")
    result = await client.get_thing_schedule(serial)
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


async def test_get_statistics(
    mock_aioresponse: aioresponses, serial: str, snapshot: SnapshotAssertion
) -> None:
    """Test getting the list of things."""

    mock_aioresponse.get(
        url=f"{CUSTOMER_APP_URL}/things/{serial}/stats",
        status=200,
        payload=load_fixture("machine", "statistics.json"),
    )

    client = LaMarzoccoCloudClient("test", "test")
    result = await client.get_thing_statistics(serial)
    assert result.to_dict() == snapshot


async def test_set_power(
    mock_aioresponse: aioresponses,
    serial: str,
) -> None:
    """Test setting the power for a thing."""

    url = f"{CUSTOMER_APP_URL}/things/{serial}/command/CoffeeMachineChangeMode"

    mock_aioresponse.post(
        url=url,
        status=200,
        payload=MOCK_COMMAND_RESPONSE,
    )

    client = LaMarzoccoCloudClient("test", "test")

    result = await client.set_power(serial, False)

    call = mock_aioresponse.requests[(HTTPMethod.POST, URL(url))][0]
    assert call.kwargs["json"] == {"mode": "StandBy"}
    assert result is True


@pytest.mark.usefixtures("mock_websocket", "mock_wait_for_ws_command_response")
async def test_set_power_with_ws_validation(
    mock_aioresponse: aioresponses,
    serial: str,
) -> None:
    """Test setting the power for a thing, validate the command from ws."""

    url = f"{CUSTOMER_APP_URL}/things/{serial}/command/CoffeeMachineChangeMode"

    mock_aioresponse.post(
        url=url,
        status=200,
        payload=MOCK_COMMAND_RESPONSE,
    )

    client = LaMarzoccoCloudClient("test", "test")

    result = await client.set_power(serial, False)

    call = mock_aioresponse.requests[(HTTPMethod.POST, URL(url))][0]
    assert call.kwargs["json"] == {"mode": "StandBy"}
    assert result is True


@pytest.mark.usefixtures("mock_websocket", "mock_wait_for_ws_command_response")
async def test_failing_response_ws_validation(
    mock_aioresponse: aioresponses,
    mock_ws_command_response: CommandResponse,
    serial: str,
) -> None:
    """Tests failing response from websocket"""

    url = f"{CUSTOMER_APP_URL}/things/{serial}/command/CoffeeMachineChangeMode"

    mock_aioresponse.post(
        url=url,
        status=200,
        payload=MOCK_COMMAND_RESPONSE,
    )

    mock_ws_command_response.status = CommandStatus.ERROR

    client = LaMarzoccoCloudClient("test", "test")

    result = await client.set_power(serial, False)
    assert result is False


@pytest.mark.usefixtures("mock_websocket", "mock_wait_for_ws_command_response")
async def test_pending_command_ws_validation_timeout(
    mock_aioresponse: aioresponses,
    mock_wait_for_ws_command_response: AsyncMock,
    serial: str,
) -> None:
    """Tests failing response from websocket"""

    url = f"{CUSTOMER_APP_URL}/things/{serial}/command/CoffeeMachineChangeMode"

    mock_aioresponse.post(
        url=url,
        status=200,
        payload=MOCK_COMMAND_RESPONSE,
    )

    mock_wait_for_ws_command_response.side_effect = TimeoutError

    client = LaMarzoccoCloudClient("test", "test")

    result = await client.set_power(serial, False)
    assert result is False


async def test_disconnected_ws_returns_true(
    mock_aioresponse: aioresponses,
    mock_websocket: MagicMock,
    serial: str,
) -> None:
    """Test setting the power for a thing."""

    url = f"{CUSTOMER_APP_URL}/things/{serial}/command/CoffeeMachineChangeMode"

    mock_aioresponse.post(
        url=url,
        status=200,
        payload=MOCK_COMMAND_RESPONSE,
    )

    client = LaMarzoccoCloudClient("test", "test")

    mock_websocket.connected = False

    result = await client.set_power(serial, False)

    call = mock_aioresponse.requests[(HTTPMethod.POST, URL(url))][0]
    assert call.kwargs["json"] == {"mode": "StandBy"}
    assert result is True


async def test_set_steam(
    mock_aioresponse: aioresponses,
    serial: str,
) -> None:
    """Test setting the steam for a thing."""

    url = f"{CUSTOMER_APP_URL}/things/{serial}/command/CoffeeMachineSettingSteamBoilerEnabled"

    mock_aioresponse.post(
        url=url,
        status=200,
        payload=MOCK_COMMAND_RESPONSE,
    )

    client = LaMarzoccoCloudClient("test", "test")
    result = await client.set_steam(serial, True)

    call = mock_aioresponse.requests[(HTTPMethod.POST, URL(url))][0]
    assert call.kwargs["json"] == {
        "boilerIndex": 1,
        "enabled": True,
    }
    assert result is True


async def test_set_coffee_temperature(
    mock_aioresponse: aioresponses,
    serial: str,
) -> None:
    """Test setting the steam for a thing."""

    url = f"{CUSTOMER_APP_URL}/things/{serial}/command/CoffeeMachineSettingCoffeeBoilerTargetTemperature"

    mock_aioresponse.post(
        url=url,
        status=200,
        payload=MOCK_COMMAND_RESPONSE,
    )

    client = LaMarzoccoCloudClient("test", "test")
    result = await client.set_coffee_target_temperature(serial, 94.584)

    call = mock_aioresponse.requests[(HTTPMethod.POST, URL(url))][0]
    assert call.kwargs["json"] == {
        "boilerIndex": 1,
        "targetTemperature": 94.6,
    }
    assert result is True


async def test_set_steam_target_level(
    mock_aioresponse: aioresponses,
    serial: str,
) -> None:
    """Test setting the steam target level for a thing."""

    url = f"{CUSTOMER_APP_URL}/things/{serial}/command/CoffeeMachineSettingSteamBoilerTargetLevel"

    mock_aioresponse.post(
        url=url,
        status=200,
        payload=MOCK_COMMAND_RESPONSE,
    )

    client = LaMarzoccoCloudClient("test", "test")
    result = await client.set_steam_target_level(serial, SteamTargetLevel.LEVEL_1)
    call = mock_aioresponse.requests[(HTTPMethod.POST, URL(url))][0]
    assert call.kwargs["json"] == {
        "boilerIndex": 1,
        "targetLevel": "Level1",
    }
    assert result is True


async def test_start_backflush_cleaning(
    mock_aioresponse: aioresponses,
    serial: str,
) -> None:
    """Test starting backflush cleaning for a thing."""

    url = f"{CUSTOMER_APP_URL}/things/{serial}/command/CoffeeMachineBackFlushStartCleaning"
    mock_aioresponse.post(
        url=url,
        status=200,
        payload=MOCK_COMMAND_RESPONSE,
    )

    client = LaMarzoccoCloudClient("test", "test")
    result = await client.start_backflush_cleaning(serial)
    call = mock_aioresponse.requests[(HTTPMethod.POST, URL(url))][0]
    assert call.kwargs["json"] == {
        "enabled": True,
    }
    assert result is True


async def test_change_pre_extraction_mode(
    mock_aioresponse: aioresponses,
    serial: str,
) -> None:
    """Test changing the pre-extraction mode for a thing."""

    url = (
        f"{CUSTOMER_APP_URL}/things/{serial}/command/CoffeeMachinePreBrewingChangeMode"
    )
    mock_aioresponse.post(
        url=url,
        status=200,
        payload=MOCK_COMMAND_RESPONSE,
    )

    client = LaMarzoccoCloudClient("test", "test")
    result = await client.change_pre_extraction_mode(
        serial, PreExtractionMode.PREBREWING
    )
    call = mock_aioresponse.requests[(HTTPMethod.POST, URL(url))][0]
    assert call.kwargs["json"] == {
        "mode": "PreBrewing",
    }
    assert result is True


async def test_change_pre_extraction_times(
    mock_aioresponse: aioresponses,
    serial: str,
) -> None:
    """Test changing the pre-extraction times for a thing."""

    url = (
        f"{CUSTOMER_APP_URL}/things/{serial}/command/CoffeeMachinePreBrewingChangeTimes"
    )
    mock_aioresponse.post(
        url=url,
        status=200,
        payload=MOCK_COMMAND_RESPONSE,
    )

    client = LaMarzoccoCloudClient("test", "test")
    result = await client.change_pre_extraction_times(
        serial,
        PrebrewSettingTimes(times=SecondsInOut(seconds_in=5.12, seconds_out=5.03)),
    )
    call = mock_aioresponse.requests[(HTTPMethod.POST, URL(url))][0]
    assert call.kwargs["json"] == {
        "times": {"In": 5.1, "Out": 5.0},
        "groupIndex": 1,
        "doseIndex": "ByGroup",
    }
    assert result is True


async def test_setting_smart_standby(
    mock_aioresponse: aioresponses,
    serial: str,
) -> None:
    """Test setting the smart standby for a thing."""

    url = f"{CUSTOMER_APP_URL}/things/{serial}/command/CoffeeMachineSettingSmartStandBy"
    mock_aioresponse.post(
        url=url,
        status=200,
        payload=MOCK_COMMAND_RESPONSE,
    )

    client = LaMarzoccoCloudClient("test", "test")
    result = await client.set_smart_standby(
        serial, False, 20, SmartStandByType.LAST_BREW
    )
    call = mock_aioresponse.requests[(HTTPMethod.POST, URL(url))][0]
    assert call.kwargs["json"] == {
        "enabled": False,
        "minutes": 20,
        "after": "LastBrewing",
    }
    assert result is True


async def test_set_wake_up_schedule(
    mock_aioresponse: aioresponses,
    serial: str,
) -> None:
    """Test setting the wake up schedule for a thing."""

    url = f"{CUSTOMER_APP_URL}/things/{serial}/command/CoffeeMachineSetWakeUpSchedule"
    mock_aioresponse.post(
        url=url,
        status=200,
        payload=MOCK_COMMAND_RESPONSE,
        repeat=2,
    )

    client = LaMarzoccoCloudClient("test", "test")

    # new schedule
    result = await client.set_wakeup_schedule(
        serial,
        WakeUpScheduleSettings(
            enabled=True,
            on_time_minutes=50,
            off_time_minutes=1439,
            steam_boiler=False,
            days=[WeekDay.MONDAY, WeekDay.FRIDAY],
        ),
    )
    call = mock_aioresponse.requests[(HTTPMethod.POST, URL(url))][0]
    expected_output = {
        "enabled": True,
        "onTimeMinutes": 50,
        "offTimeMinutes": 1439,
        "days": [
            "Monday",
            "Friday",
        ],
        "steamBoiler": False,
    }
    assert call.kwargs["json"] == expected_output
    assert result is True

    # existing schedule
    result = await client.set_wakeup_schedule(
        serial,
        WakeUpScheduleSettings(
            identifier="aBc23d",
            enabled=True,
            on_time_minutes=50,
            off_time_minutes=1439,
            steam_boiler=False,
            days=[WeekDay.MONDAY, WeekDay.FRIDAY],
        ),
    )
    call = mock_aioresponse.requests[(HTTPMethod.POST, URL(url))][1]
    assert call.kwargs["json"] == {
        "id": "aBc23d",
        **expected_output,
    }
    assert result is True


async def test_get_update_details(
    mock_aioresponse: aioresponses, serial: str, snapshot: SnapshotAssertion
) -> None:
    """Test getting the update details for a thing."""

    url = f"{CUSTOMER_APP_URL}/things/{serial}/update-fw"
    mock_aioresponse.get(
        url=url,
        status=200,
        payload={
            "status": "ToUpdate",
            "commandStatus": "InProgress",
            "progressInfo": "download",
            "progressPercentage": 10,
        },
    )

    client = LaMarzoccoCloudClient("test", "test")
    result = await client.get_thing_firmware(serial)
    assert result.to_dict() == snapshot


async def test_start_update(
    mock_aioresponse: aioresponses, serial: str, snapshot: SnapshotAssertion
) -> None:
    """Test getting the update details for a thing."""

    url = f"{CUSTOMER_APP_URL}/things/{serial}/update-fw"
    mock_aioresponse.post(
        url=url,
        status=200,
        payload={
            "status": "ToUpdate",
            "commandStatus": "InProgress",
            "progressInfo": "starting process",
            "progressPercentage": None,
        },
    )

    client = LaMarzoccoCloudClient("test", "test")
    result = await client.update_firmware(serial)
    assert result.to_dict() == snapshot
