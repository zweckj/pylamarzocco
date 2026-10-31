"""Testing the cloud client."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from http import HTTPMethod
from typing import Any
from unittest.mock import patch

import pytest
from aiohttp import ClientError, web
from aiointercept import aiointercept
from syrupy import SnapshotAssertion
from yarl import URL

from pylamarzocco.clients import LaMarzoccoCloudClient
from pylamarzocco.const import (
    CUSTOMER_APP_URL,
    DoseIndex,
    DoseMode,
    MachineMode,
    GrinderDoseMode,
    GrinderGrindWithMode,
    GrinderMode,
    GrinderSpeedLevelType,
    PreExtractionMode,
    SmartStandByType,
    SteamTargetLevel,
    WeekDay,
)
from pylamarzocco.exceptions import (
    AuthFail,
    PolicyAcceptanceRequired,
    RequestNotSuccessful,
)
from pylamarzocco.models import (
    PrebrewSettingTimes,
    SecondsInOut,
    WakeUpScheduleSettings,
)

from .conftest import (
    MOCK_SECRET_DATA,
    accept_stomp_connection,
    add_websocket_endpoint,
    dashboard_message,
    load_fixture,
)

pytestmark = pytest.mark.usefixtures("mock_access_token")

MOCK_COMMAND_RESPONSE = [
    {
        "id": "mock-id",
        "status": "Pending",
        "error_code": None,
    }
]


async def push_until_closed(ws: web.WebSocketResponse, frame: str) -> None:
    """Push ``frame`` every few milliseconds until the client closes the socket.

    A command result only resolves a command the client is already waiting for,
    so keep repeating it rather than racing the client's handling of the REST
    reply.
    """

    async def push() -> None:
        while not ws.closed:
            await ws.send_str(frame)
            await asyncio.sleep(0.01)

    pusher = asyncio.create_task(push())
    try:
        async for _ in ws:
            pass
    finally:
        pusher.cancel()
        with suppress(asyncio.CancelledError, ConnectionError):
            await pusher


@asynccontextmanager
async def websocket_pushing(
    mock_aiointercept: aiointercept,
    client: LaMarzoccoCloudClient,
    serial: str,
    commands: list[dict[str, Any]],
) -> AsyncIterator[None]:
    """Keep the client's websocket connected to a server pushing command results.

    The connection task is cancelled, and the server session awaited, on exit.
    """
    update = load_fixture("machine", "config_micra.json") | {"commands": commands}
    frame = dashboard_message(serial, update)

    async def session(ws: web.WebSocketResponse) -> None:
        await accept_stomp_connection(ws, [])
        await push_until_closed(ws, frame)

    session_finished = add_websocket_endpoint(mock_aiointercept, session)
    connected = asyncio.Event()
    task = asyncio.create_task(
        client.websocket_connect(serial, connect_callback=connected.set)
    )
    try:
        async with asyncio.timeout(5):
            await connected.wait()
        yield
    finally:
        task.cancel()
        async with asyncio.timeout(5):
            await task
            await session_finished.wait()


async def test_access_token(
    mock_aiointercept: aiointercept,
    client: LaMarzoccoCloudClient,
) -> None:
    """Test getting the dashboard for a thing."""

    # Drop the module-wide repeating sign-in handler; aiointercept rejects adding
    # one-shot handlers for the same URL on top of a repeat=True handler.
    mock_aiointercept.clear()

    mock_aiointercept.post(
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

    result = await client.async_get_access_token()
    assert result == "mock-access"

    # now get one again to get from cache
    mock_aiointercept.post(
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
    mock_aiointercept.post(
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


@pytest.mark.parametrize("model", ["micra", "gs3av", "mini", "minir", "stradax"])
async def test_get_thing_dashboard(
    mock_aiointercept: aiointercept,
    model: str,
    serial: str,
    snapshot: SnapshotAssertion,
    client: LaMarzoccoCloudClient,
) -> None:
    """Test getting the dashboard for a thing."""

    mock_aiointercept.get(
        url=f"{CUSTOMER_APP_URL}/things/{serial}/dashboard",
        status=200,
        payload=load_fixture("machine", f"dashboard_{model}.json"),
    )

    result = await client.get_thing_dashboard(serial)
    assert result.to_dict() == snapshot


async def test_policy_acceptance_required(
    mock_aiointercept: aiointercept,
    serial: str,
    client: LaMarzoccoCloudClient,
) -> None:
    """Test that a policy acceptance 403 raises a dedicated exception."""

    mock_aiointercept.get(
        url=f"{CUSTOMER_APP_URL}/things/{serial}/dashboard",
        status=403,
        payload={
            "success": False,
            "message": "User must accept latest policy",
            "code": "USER_MUST_ACCEPT_POLICY",
        },
    )

    with pytest.raises(PolicyAcceptanceRequired):
        await client.get_thing_dashboard(serial)


async def test_forbidden_raises_auth_fail(
    mock_aiointercept: aiointercept,
    serial: str,
    client: LaMarzoccoCloudClient,
) -> None:
    """Test that any other 403 raises AuthFail."""

    mock_aiointercept.get(
        url=f"{CUSTOMER_APP_URL}/things/{serial}/dashboard",
        status=403,
        payload={"success": False, "message": "Forbidden"},
    )

    with pytest.raises(AuthFail):
        await client.get_thing_dashboard(serial)


async def test_accept_privacy_policy(
    mock_aiointercept: aiointercept,
    client: LaMarzoccoCloudClient,
) -> None:
    """Test accepting the privacy policy."""

    url = f"{CUSTOMER_APP_URL}/users/policy"
    mock_aiointercept.put(url=url, status=200, body="")

    await client.accept_privacy_policy(profile_policy=True)

    call = mock_aiointercept.requests[(HTTPMethod.PUT, URL(url))][0]
    assert await call.json() == {"profilePolicy": True, "commercialPolicy": False}


async def test_get_grinder_dashboard(
    mock_aiointercept: aiointercept,
    snapshot: SnapshotAssertion,
    client: LaMarzoccoCloudClient,
) -> None:
    """Test getting the dashboard for a grinder."""

    serial = "GR123456"  # matches the fixture's serialNumber
    mock_aiointercept.get(
        url=f"{CUSTOMER_APP_URL}/things/{serial}/dashboard",
        status=200,
        payload=load_fixture("grinder", "dashboard_pico.json"),
    )

    result = await client.get_thing_dashboard(serial)
    assert result.to_dict() == snapshot


async def test_get_thing_settings(
    mock_aiointercept: aiointercept, serial: str, snapshot: SnapshotAssertion,
    client: LaMarzoccoCloudClient,
) -> None:
    """Test getting the settings for a thing."""

    mock_aiointercept.get(
        url=f"{CUSTOMER_APP_URL}/things/{serial}/settings",
        status=200,
        payload=load_fixture("machine", "settings_micra.json"),
    )

    result = await client.get_thing_settings(serial)
    assert result.to_dict() == snapshot


async def test_get_thing_schedule(
    mock_aiointercept: aiointercept, serial: str, snapshot: SnapshotAssertion,
    client: LaMarzoccoCloudClient,
) -> None:
    """Test getting the schedule for a thing."""

    mock_aiointercept.get(
        url=f"{CUSTOMER_APP_URL}/things/{serial}/scheduling",
        status=200,
        payload=load_fixture("machine", "schedule.json"),
    )

    result = await client.get_thing_schedule(serial)
    assert result.to_dict() == snapshot


async def test_list_things(
    mock_aiointercept: aiointercept, snapshot: SnapshotAssertion,
    client: LaMarzoccoCloudClient,
) -> None:
    """Test getting the list of things."""

    mock_aiointercept.get(
        url=f"{CUSTOMER_APP_URL}/things",
        status=200,
        payload=[load_fixture("machine", "settings_micra.json")],
    )

    result = await client.list_things()
    assert result[0].to_dict() == snapshot


async def test_debug_log_masks_bluetooth_token(
    mock_aiointercept: aiointercept, serial: str, caplog: pytest.LogCaptureFixture,
    client: LaMarzoccoCloudClient,
) -> None:
    """Test the Bluetooth token never ends up in the debug log."""
    caplog.set_level(logging.DEBUG, logger="pylamarzocco")
    thing = load_fixture("machine", "settings_micra.json") | {
        "bleAuthToken": "secret-token"
    }
    mock_aiointercept.get(
        url=f"{CUSTOMER_APP_URL}/things/{serial}/settings", status=200, payload=thing
    )
    mock_aiointercept.get(url=f"{CUSTOMER_APP_URL}/things", status=200, payload=[thing])

    settings = await client.get_thing_settings(serial)
    things = await client.list_things()

    assert settings.ble_auth_token == things[0].ble_auth_token == "secret-token"
    assert caplog.text.count("Response:") == 2
    assert "secret-token" not in caplog.text


async def test_get_statistics(
    mock_aiointercept: aiointercept, serial: str, snapshot: SnapshotAssertion,
    client: LaMarzoccoCloudClient,
) -> None:
    """Test getting the list of things."""

    mock_aiointercept.get(
        url=f"{CUSTOMER_APP_URL}/things/{serial}/stats",
        status=200,
        payload=load_fixture("machine", "statistics.json"),
    )

    result = await client.get_thing_statistics(serial)
    assert result.to_dict() == snapshot


@pytest.mark.parametrize(
    ("status", "expected"), [("Success", True), ("Error", False)]
)
async def test_command_ws_validation(
    mock_aiointercept: aiointercept,
    serial: str,
    client: LaMarzoccoCloudClient,
    status: str,
    expected: bool,
) -> None:
    """A command's result is the status the websocket pushes for its id."""

    url = f"{CUSTOMER_APP_URL}/things/{serial}/command/CoffeeMachineChangeMode"
    mock_aiointercept.post(url=url, status=200, payload=MOCK_COMMAND_RESPONSE)
    commands = [{"id": "mock-id", "status": status, "errorCode": None}]

    async with websocket_pushing(mock_aiointercept, client, serial, commands):
        assert client.websocket.connected is True
        result = await client.set_power(serial, False)

    call = mock_aiointercept.requests[(HTTPMethod.POST, URL(url))][0]
    assert await call.json() == {"mode": "StandBy"}
    assert result is expected


async def test_failed_command_returns_without_waiting_for_timeout(
    mock_aiointercept: aiointercept,
    serial: str,
    client: LaMarzoccoCloudClient,
) -> None:
    """A refused command reports False from its Failed status, not from the timeout."""

    url = f"{CUSTOMER_APP_URL}/things/{serial}/command/CoffeeMachineChangeMode"
    mock_aiointercept.post(url=url, status=200, payload=MOCK_COMMAND_RESPONSE)
    commands = [{"id": "mock-id", "status": "Failed", "errorCode": None}]

    async with websocket_pushing(mock_aiointercept, client, serial, commands):
        async with asyncio.timeout(1):
            result = await client.set_power(serial, False)

    assert result is False


async def test_pending_command_ws_validation_timeout(
    mock_aiointercept: aiointercept,
    serial: str,
    client: LaMarzoccoCloudClient,
) -> None:
    """A command whose result never arrives times out and is not kept pending."""

    url = f"{CUSTOMER_APP_URL}/things/{serial}/command/CoffeeMachineChangeMode"
    mock_aiointercept.post(url=url, status=200, payload=MOCK_COMMAND_RESPONSE)
    commands = [{"id": "other-id", "status": "Success", "errorCode": None}]

    with patch("pylamarzocco.clients._cloud.PENDING_COMMAND_TIMEOUT", new=0.1):
        async with websocket_pushing(mock_aiointercept, client, serial, commands):
            result = await client.set_power(serial, False)

    assert result is False
    assert client._pending_commands == {}  # pylint: disable=protected-access


async def test_set_wake_up_schedule(
    mock_aiointercept: aiointercept,
    serial: str,
    client: LaMarzoccoCloudClient,
) -> None:
    """Test setting the wake up schedule for a thing."""

    url = (
        f"{CUSTOMER_APP_URL}/things/{serial}/command/"
        "CoffeeMachineSettingWakeUpSchedule"
    )
    mock_aiointercept.post(
        url=url,
        status=200,
        payload=MOCK_COMMAND_RESPONSE,
        repeat=2,
    )

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
    call = mock_aiointercept.requests[(HTTPMethod.POST, URL(url))][0]
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
    assert await call.json() == expected_output
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
    call = mock_aiointercept.requests[(HTTPMethod.POST, URL(url))][1]
    assert await call.json() == {
        "id": "aBc23d",
        **expected_output,
    }
    assert result is True


async def test_get_update_details(
    mock_aiointercept: aiointercept, serial: str, snapshot: SnapshotAssertion,
    client: LaMarzoccoCloudClient,
) -> None:
    """Test getting the update details for a thing."""

    url = f"{CUSTOMER_APP_URL}/things/{serial}/update-fw"
    mock_aiointercept.get(
        url=url,
        status=200,
        payload={
            "status": "ToUpdate",
            "commandStatus": "InProgress",
            "progressInfo": "download",
            "progressPercentage": 10,
        },
    )

    result = await client.get_thing_firmware(serial)
    assert result.to_dict() == snapshot


async def test_start_update(
    mock_aiointercept: aiointercept, serial: str, snapshot: SnapshotAssertion,
    client: LaMarzoccoCloudClient,
) -> None:
    """Test getting the update details for a thing."""

    url = f"{CUSTOMER_APP_URL}/things/{serial}/update-fw"
    mock_aiointercept.post(
        url=url,
        status=200,
        payload={
            "status": "ToUpdate",
            "commandStatus": "InProgress",
            "progressInfo": "starting process",
            "progressPercentage": None,
        },
    )

    result = await client.update_firmware(serial)
    assert result.to_dict() == snapshot


async def test_register_client(
    mock_aiointercept: aiointercept,
    client: LaMarzoccoCloudClient,
) -> None:
    """Test registering a new client."""

    url = f"{CUSTOMER_APP_URL}/auth/init"
    mock_aiointercept.post(url=url, status=200)

    await client.async_register_client()

    call = mock_aiointercept.requests[(HTTPMethod.POST, URL(url))][0]
    assert await call.json() == {"pk": MOCK_SECRET_DATA.public_key_b64}
    assert call.kwargs["headers"]["X-App-Installation-Id"] == "mock-installation-id"


@pytest.mark.parametrize(
    ("status", "exception"), [(401, AuthFail), (500, RequestNotSuccessful)]
)
async def test_register_client_failure(
    mock_aiointercept: aiointercept,
    status: int,
    exception: type[Exception],
    client: LaMarzoccoCloudClient,
) -> None:
    """Test a failing client registration."""

    mock_aiointercept.post(url=f"{CUSTOMER_APP_URL}/auth/init", status=status)

    with pytest.raises(exception):
        await client.async_register_client()


async def test_register_client_connection_error(
    mock_aiointercept: aiointercept,
    client: LaMarzoccoCloudClient,
) -> None:
    """Test a connection error during client registration."""

    mock_aiointercept.post(
        url=f"{CUSTOMER_APP_URL}/auth/init", exception=ClientError("boom")
    )

    with pytest.raises(RequestNotSuccessful):
        await client.async_register_client()


@pytest.mark.parametrize(
    ("status", "exception"), [(401, AuthFail), (500, RequestNotSuccessful)]
)
async def test_access_token_failure(
    mock_aiointercept: aiointercept,
    status: int,
    exception: type[Exception],
    client: LaMarzoccoCloudClient,
) -> None:
    """Test a failing sign in."""

    mock_aiointercept.clear()
    mock_aiointercept.post(url=f"{CUSTOMER_APP_URL}/auth/signin", status=status)

    with pytest.raises(exception):
        await client.async_get_access_token()


async def test_access_token_connection_error(
    mock_aiointercept: aiointercept,
    client: LaMarzoccoCloudClient,
) -> None:
    """Test a connection error during sign in."""

    mock_aiointercept.clear()
    mock_aiointercept.post(
        url=f"{CUSTOMER_APP_URL}/auth/signin", exception=ClientError("boom")
    )

    with pytest.raises(RequestNotSuccessful):
        await client.async_get_access_token()


async def test_refresh_token_without_access_token(
    client: LaMarzoccoCloudClient,
) -> None:
    """Test refreshing without an access token raises."""

    with pytest.raises(ValueError, match="No access token available"):
        await client._async_refresh_token()  # pylint: disable=protected-access


@pytest.mark.parametrize(
    ("status", "body", "exception"),
    [
        (401, "", AuthFail),
        (403, "not json", AuthFail),
        (500, "error", RequestNotSuccessful),
    ],
)
async def test_rest_api_call_failure(
    mock_aiointercept: aiointercept,
    serial: str,
    status: int,
    body: str,
    exception: type[Exception],
    client: LaMarzoccoCloudClient,
) -> None:
    """Test failing REST API calls."""

    mock_aiointercept.get(
        url=f"{CUSTOMER_APP_URL}/things/{serial}/dashboard", status=status, body=body
    )

    with pytest.raises(exception):
        await client.get_thing_dashboard(serial)


async def test_rest_api_call_connection_error(
    mock_aiointercept: aiointercept,
    serial: str,
    client: LaMarzoccoCloudClient,
) -> None:
    """Test a connection error during a REST API call."""

    mock_aiointercept.get(
        url=f"{CUSTOMER_APP_URL}/things/{serial}/dashboard",
        exception=ClientError("boom"),
    )

    with pytest.raises(RequestNotSuccessful):
        await client.get_thing_dashboard(serial)


async def test_get_thing_coffee_and_flush_trend(
    mock_aiointercept: aiointercept,
    serial: str,
    client: LaMarzoccoCloudClient,
) -> None:
    """Test getting the coffee and flush trend."""

    url = (
        f"{CUSTOMER_APP_URL}/things/{serial}/stats/COFFEE_AND_FLUSH_TREND/1"
        "?days=7&timezone=Europe/Berlin"
    )
    mock_aiointercept.get(
        url=url,
        status=200,
        payload={
            "output": {
                "days": 7,
                "timezone": "Europe/Berlin",
                "coffees": [{"timestamp": 1700000000000, "value": 3}],
            }
        },
    )

    result = await client.get_thing_coffee_and_flush_trend(
        serial, days=7, timezone="Europe/Berlin"
    )
    assert result.days == 7
    assert result.timezone == "Europe/Berlin"
    assert result.coffees[0].value == 3


async def test_get_thing_last_coffee(
    mock_aiointercept: aiointercept,
    serial: str,
    client: LaMarzoccoCloudClient,
) -> None:
    """Test getting the last coffees."""

    mock_aiointercept.get(
        url=f"{CUSTOMER_APP_URL}/things/{serial}/stats/LAST_COFFEE/1?days=7",
        status=200,
        payload={
            "output": {
                "lastCoffees": [
                    {
                        "time": 1700000000000,
                        "extractionSeconds": 27.5,
                        "doseMode": "Dose1",
                        "doseIndex": "DoseA",
                    }
                ]
            }
        },
    )

    result = await client.get_thing_last_coffee(serial, days=7)
    assert result.last_coffees[0].extraction_seconds == 27.5
    assert result.last_coffees[0].dose_mode is DoseMode.DOSE_1
    assert result.last_coffees[0].dose_index is DoseIndex.DOSE_A


async def test_get_thing_coffee_and_flush_counter(
    mock_aiointercept: aiointercept,
    serial: str,
    client: LaMarzoccoCloudClient,
) -> None:
    """Test getting the coffee and flush counter."""

    mock_aiointercept.get(
        url=f"{CUSTOMER_APP_URL}/things/{serial}/stats/COFFEE_AND_FLUSH_COUNTER/1",
        status=200,
        payload={"output": {"totalCoffee": 1234, "totalFlush": 567}},
    )

    result = await client.get_thing_coffee_and_flush_counter(serial)
    assert result.total_coffee == 1234
    assert result.total_flush == 567


@pytest.mark.parametrize(
    ("method", "args", "command", "expected_body"),
    [
        ("set_power", (False,), "CoffeeMachineChangeMode", {"mode": "StandBy"}),
        (
            "set_mode",
            (MachineMode.ECO_MODE,),
            "CoffeeMachineChangeMode",
            {"mode": "EcoMode"},
        ),
        (
            "set_auto_flush",
            (True,),
            "CoffeeMachineSettingAutoFlushEnabled",
            {"enabled": True},
        ),
        (
            "set_steam_flush",
            (False,),
            "CoffeeMachineSettingSteamFlushEnabled",
            {"enabled": False},
        ),
        (
            "set_rinse_flush",
            (True,),
            "CoffeeMachineSettingRinseFlushEnabled",
            {"enabled": True},
        ),
        (
            "set_hot_water_dose_enabled",
            (False,),
            "CoffeeMachineSettingHotWaterDoseEnabled",
            {"enabled": False},
        ),
        (
            "set_cup_warmer",
            (True,),
            "CoffeeMachineSettingCupWarmerEnabled",
            {"enabled": True},
        ),
        (
            "set_group_mode",
            (MachineMode.BREWING_MODE,),
            "CoffeeMachineGroupChangeMode",
            {"groupIndex": 1, "mode": "BrewingMode"},
        ),
        (
            "set_coffee_boiler",
            (True,),
            "CoffeeMachineSettingCoffeeBoilerEnabled",
            {"boilerIndex": 1, "enabled": True},
        ),
        (
            "set_rinse_flush_time",
            (4.0,),
            "CoffeeMachineSettingRinseFlushTime",
            {"timeSeconds": 4.0},
        ),
        (
            "set_hot_water_dose",
            (8.0, DoseIndex.DOSE_A),
            "CoffeeMachineSettingHotWaterDose",
            {"doseIndex": "DoseA", "dose": 8.0},
        ),
        (
            "set_group_dose_mode",
            (DoseMode.PULSES_TYPE,),
            "CoffeeMachineGroupDoseChangeMode",
            {"groupIndex": 1, "mode": "PulsesType"},
        ),
        (
            "set_group_dose",
            (DoseMode.PULSES_TYPE, DoseIndex.DOSE_A, 36.0),
            "CoffeeMachineGroupDoseSettingDose",
            {"groupIndex": 1, "mode": "PulsesType", "doseIndex": "DoseA", "dose": 36.0},
        ),
        (
            "set_brewing_pressure",
            (9.0,),
            "CoffeeMachineGroupDoseSettingGroupBrewingPressure",
            {"groupIndex": 1, "pressure": 9.0},
        ),
        (
            "set_continuous_dose_enabled",
            (True,),
            "CoffeeMachineGroupDoseSettingContinuousDoseEnabled",
            {"groupIndex": 1, "rinseEnabled": True},
        ),
        (
            "set_continuous_dose",
            (3.0,),
            "CoffeeMachineGroupDoseSettingContinuousDose",
            {"groupIndex": 1, "rinseSeconds": 3.0},
        ),
        (
            "set_mirror_group1",
            (True,),
            "CoffeeMachineGroupDoseSettingMirrorGroup1",
            {"groupIndex": 2, "enabled": True},
        ),
        ("set_plumb_in", (True,), "CoffeeMachineSettingPlumbIn", {"enabled": True}),
        (
            "set_grinder_mode",
            (GrinderMode.GRINDING,),
            "GrinderChangeMode",
            {"mode": "GrindingMode"},
        ),
        (
            "set_grinder_barista_light",
            (True,),
            "GrinderSettingBaristaLightEnabled",
            {"enabled": True},
        ),
        (
            "set_grinder_grind_with",
            (GrinderGrindWithMode.BY_BUTTON,),
            "GrinderSettingGrindWithMode",
            {"mode": "ByButton"},
        ),
        (
            "set_grinder_dose",
            (DoseIndex.DOSE_A, 12.0, GrinderDoseMode.TIME),
            "GrinderSettingDose",
            {"mode": "TimeType", "doseIndex": "DoseA", "dose": 12.0},
        ),
        (
            "set_grinder_dose",
            (DoseIndex.DOSE_B, 9.7, GrinderDoseMode.REV),
            "GrinderSettingDose",
            {"mode": "RevType", "doseIndex": "DoseB", "dose": 9.7},
        ),
        (
            "set_grinder_more_dose",
            (2.5,),
            "GrinderSettingMoreDose",
            {"revolutions": 2.5},
        ),
        (
            "set_grinder_single_dose_mode",
            (True,),
            "GrinderSettingSingleDoseModeEnabled",
            {"enabled": True},
        ),
        (
            "set_grinder_mirror_doses",
            (False,),
            "GrinderSettingMirrorDosesEnabled",
            {"enabled": False},
        ),
        (
            "set_grinder_speed",
            (DoseIndex.DOSE_B, GrinderSpeedLevelType.LOW),
            "GrinderSettingSpeedForDose",
            {"doseIndex": "DoseB", "speedLevel": "Low"},
        ),
        (
            "set_grinder_auto_speed_enabled",
            (DoseIndex.DOSE_A, True, 2),
            "GrinderSettingAutoSpeedDoseEnabled",
            {"doseIndex": "DoseA", "groupIndex": 2, "enabled": True},
        ),
        (
            "set_grinder_auto_speed_reference",
            (DoseMode.MASS_TYPE, 28.0, 36.5),
            "GrinderSettingAutoSpeedDose",
            {
                "doseMode": "MassType",
                "extractionSeconds": 28.0,
                "doseMass": 36.5,
                "dosePulses": None,
                "rateLock": False,
            },
        ),
        (
            "set_grinder_auto_standby",
            (15,),
            "GrinderSettingAutoStandBy",
            {"standByMinutes": 15},
        ),
        (
            "set_steam",
            (True,),
            "CoffeeMachineSettingSteamBoilerEnabled",
            {"boilerIndex": 1, "enabled": True},
        ),
        (
            "set_coffee_target_temperature",
            (94.584,),
            "CoffeeMachineSettingCoffeeBoilerTargetTemperature",
            {"boilerIndex": 1, "targetTemperature": 94.6},
        ),
        (
            "set_steam_target_level",
            (SteamTargetLevel.LEVEL_1,),
            "CoffeeMachineSettingSteamBoilerTargetLevel",
            {"boilerIndex": 1, "targetLevel": "Level1"},
        ),
        (
            "set_steam_target_temperature",
            (122.1,),
            "CoffeeMachineSettingSteamBoilerTargetTemperature",
            {"boilerIndex": 1, "targetTemperature": 122.1},
        ),
        (
            "start_backflush_cleaning",
            (),
            "CoffeeMachineBackFlushStartCleaning",
            {"enabled": True},
        ),
        (
            "change_pre_extraction_mode",
            (PreExtractionMode.PREBREWING,),
            "CoffeeMachinePreBrewingChangeMode",
            {"mode": "PreBrewing"},
        ),
        (
            "change_pre_extraction_times",
            (
                PrebrewSettingTimes(
                    times=SecondsInOut(seconds_in=5.12, seconds_out=5.03)
                ),
            ),
            "CoffeeMachinePreBrewingSettingTimes",
            {"times": {"In": 5.1, "Out": 5.0}, "groupIndex": 1, "doseIndex": "ByGroup"},
        ),
        (
            "set_smart_standby",
            (False, 20, SmartStandByType.LAST_BREW),
            "CoffeeMachineSettingSmartStandBy",
            {"enabled": False, "minutes": 20, "after": "LastBrewing"},
        ),
        (
            "change_brew_by_weight_dose_mode",
            (DoseMode.DOSE_1,),
            "CoffeeMachineBrewByWeightChangeMode",
            {"mode": "Dose1"},
        ),
        (
            "set_brew_by_weight_dose",
            (32.56, 45.67),
            "CoffeeMachineBrewByWeightSettingDoses",
            {"doses": {"Dose1": 32.6, "Dose2": 45.7}},
        ),
        (
            "set_auto_standby",
            ("00:30",),
            "CoffeeMachineSettingAutoStandBy",
            {"mode": "00:30"},
        ),
        (
            "set_auto_on_off",
            ("schedule",),
            "CoffeeMachineSettingAutoOnOff",
            {"schedule": "schedule"},
        ),
        (
            "delete_wakeup_schedule",
            ("schedule-id",),
            "CoffeeMachineDeleteWakeUpSchedule",
            {"id": "schedule-id"},
        ),
    ],
)
async def test_commands(
    mock_aiointercept: aiointercept,
    client: LaMarzoccoCloudClient,
    serial: str,
    method: str,
    args: tuple,
    command: str,
    expected_body: dict,
) -> None:
    """Test commands are posted with the expected body."""

    url = f"{CUSTOMER_APP_URL}/things/{serial}/command/{command}"
    mock_aiointercept.post(url=url, status=200, payload=MOCK_COMMAND_RESPONSE)

    assert await getattr(client, method)(serial, *args) is True

    call = mock_aiointercept.requests[(HTTPMethod.POST, URL(url))][0]
    assert await call.json() == expected_body
