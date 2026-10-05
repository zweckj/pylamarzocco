"""Testing the cloud client."""

from __future__ import annotations

import logging
from collections.abc import Generator
from http import HTTPMethod
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiointercept import aiointercept
from cryptography.hazmat.primitives.asymmetric.ec import SECP256R1, generate_private_key
from syrupy import SnapshotAssertion
from yarl import URL

from pylamarzocco.clients import LaMarzoccoCloudClient
from pylamarzocco.const import (
    CUSTOMER_APP_URL,
    CommandStatus,
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
from pylamarzocco.models import (
    CommandResponse,
    PrebrewSettingTimes,
    SecondsInOut,
    WakeUpScheduleSettings,
)
from pylamarzocco.util import InstallationKey

from .conftest import load_fixture

MOCK_COMMAND_RESPONSE = [
    {
        "id": "mock-id",
        "status": "Pending",
        "error_code": None,
    }
]

MOCK_SECRET_DATA = InstallationKey(
    secret=bytes(32),
    private_key=generate_private_key(SECP256R1()),
    installation_id="mock-installation-id",
)


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


async def test_access_token(mock_aiointercept: aiointercept) -> None:
    """Test getting the dashboard for a thing."""

    # Drop the autouse repeating sign-in handler; aiointercept rejects adding
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

    client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA)
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
) -> None:
    """Test getting the dashboard for a thing."""

    mock_aiointercept.get(
        url=f"{CUSTOMER_APP_URL}/things/{serial}/dashboard",
        status=200,
        payload=load_fixture("machine", f"dashboard_{model}.json"),
    )

    client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA)
    result = await client.get_thing_dashboard(serial)
    assert result.to_dict() == snapshot


async def test_get_grinder_dashboard(
    mock_aiointercept: aiointercept,
    snapshot: SnapshotAssertion,
) -> None:
    """Test getting the dashboard for a grinder."""

    serial = "GR123456"  # matches the fixture's serialNumber
    mock_aiointercept.get(
        url=f"{CUSTOMER_APP_URL}/things/{serial}/dashboard",
        status=200,
        payload=load_fixture("grinder", "dashboard_pico.json"),
    )

    client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA)
    result = await client.get_thing_dashboard(serial)
    assert result.to_dict() == snapshot


async def test_get_thing_settings(
    mock_aiointercept: aiointercept, serial: str, snapshot: SnapshotAssertion
) -> None:
    """Test getting the settings for a thing."""

    mock_aiointercept.get(
        url=f"{CUSTOMER_APP_URL}/things/{serial}/settings",
        status=200,
        payload=load_fixture("machine", "settings_micra.json"),
    )

    client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA)
    result = await client.get_thing_settings(serial)
    assert result.to_dict() == snapshot


async def test_get_thing_schedule(
    mock_aiointercept: aiointercept, serial: str, snapshot: SnapshotAssertion
) -> None:
    """Test getting the schedule for a thing."""

    mock_aiointercept.get(
        url=f"{CUSTOMER_APP_URL}/things/{serial}/scheduling",
        status=200,
        payload=load_fixture("machine", "schedule.json"),
    )

    client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA)
    result = await client.get_thing_schedule(serial)
    assert result.to_dict() == snapshot


async def test_list_things(
    mock_aiointercept: aiointercept, snapshot: SnapshotAssertion
) -> None:
    """Test getting the list of things."""

    mock_aiointercept.get(
        url=f"{CUSTOMER_APP_URL}/things",
        status=200,
        payload=[load_fixture("machine", "settings_micra.json")],
    )

    client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA)
    result = await client.list_things()
    assert result[0].to_dict() == snapshot


async def test_debug_log_masks_bluetooth_token(
    mock_aiointercept: aiointercept, serial: str, caplog: pytest.LogCaptureFixture
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

    client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA)
    settings = await client.get_thing_settings(serial)
    things = await client.list_things()

    assert settings.ble_auth_token == things[0].ble_auth_token == "secret-token"
    assert caplog.text.count("Response:") == 2
    assert "secret-token" not in caplog.text


async def test_get_statistics(
    mock_aiointercept: aiointercept, serial: str, snapshot: SnapshotAssertion
) -> None:
    """Test getting the list of things."""

    mock_aiointercept.get(
        url=f"{CUSTOMER_APP_URL}/things/{serial}/stats",
        status=200,
        payload=load_fixture("machine", "statistics.json"),
    )

    client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA)
    result = await client.get_thing_statistics(serial)
    assert result.to_dict() == snapshot


async def test_set_power(
    mock_aiointercept: aiointercept,
    serial: str,
) -> None:
    """Test setting the power for a thing."""

    url = f"{CUSTOMER_APP_URL}/things/{serial}/command/CoffeeMachineChangeMode"

    mock_aiointercept.post(
        url=url,
        status=200,
        payload=MOCK_COMMAND_RESPONSE,
    )

    client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA)

    result = await client.set_power(serial, False)

    call = mock_aiointercept.requests[(HTTPMethod.POST, URL(url))][0]
    assert await call.json() == {"mode": "StandBy"}
    assert result is True


async def test_disconnected_commands_do_not_leak_pending(
    mock_aiointercept: aiointercept,
    serial: str,
) -> None:
    """Fire-and-forget commands (websocket disconnected) must not accumulate
    in _pending_commands. """

    url = f"{CUSTOMER_APP_URL}/things/{serial}/command/CoffeeMachineChangeMode"

    for i in range(5):
        mock_aiointercept.post(
            url=url,
            status=200,
            payload=[{"id": f"cmd-{i}", "status": "Pending", "error_code": None}],
        )

    client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA)
    assert client.websocket.connected is False

    for _ in range(5):
        assert await client.set_power(serial, False) is True

    requests = mock_aiointercept.requests[(HTTPMethod.POST, URL(url))]
    assert len(requests) == 5
    for call in requests:
        assert await call.json() == {"mode": "StandBy"}

    assert client._pending_commands == {}


@pytest.mark.usefixtures("mock_websocket", "mock_wait_for_ws_command_response")
async def test_set_power_with_ws_validation(
    mock_aiointercept: aiointercept,
    serial: str,
) -> None:
    """Test setting the power for a thing, validate the command from ws."""

    url = f"{CUSTOMER_APP_URL}/things/{serial}/command/CoffeeMachineChangeMode"

    mock_aiointercept.post(
        url=url,
        status=200,
        payload=MOCK_COMMAND_RESPONSE,
    )

    client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA)

    result = await client.set_power(serial, False)

    call = mock_aiointercept.requests[(HTTPMethod.POST, URL(url))][0]
    assert await call.json() == {"mode": "StandBy"}
    assert result is True


async def test_set_mode(
    mock_aiointercept: aiointercept,
    serial: str,
) -> None:
    """Test setting the operating mode for a thing."""

    url = f"{CUSTOMER_APP_URL}/things/{serial}/command/CoffeeMachineChangeMode"

    mock_aiointercept.post(
        url=url,
        status=200,
        payload=MOCK_COMMAND_RESPONSE,
    )

    client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA)

    result = await client.set_mode(serial, MachineMode.ECO_MODE)

    call = mock_aiointercept.requests[(HTTPMethod.POST, URL(url))][0]
    assert await call.json() == {"mode": "EcoMode"}
    assert result is True


async def test_set_auto_flush(
    mock_aiointercept: aiointercept,
    serial: str,
) -> None:
    """Test enabling auto flush for a thing."""

    url = f"{CUSTOMER_APP_URL}/things/{serial}/command/CoffeeMachineSettingAutoFlushEnabled"

    mock_aiointercept.post(
        url=url,
        status=200,
        payload=MOCK_COMMAND_RESPONSE,
    )

    client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA)

    result = await client.set_auto_flush(serial, True)

    call = mock_aiointercept.requests[(HTTPMethod.POST, URL(url))][0]
    assert await call.json() == {"enabled": True}
    assert result is True


async def test_set_steam_flush(
    mock_aiointercept: aiointercept,
    serial: str,
) -> None:
    """Test enabling steam flush for a thing."""

    url = f"{CUSTOMER_APP_URL}/things/{serial}/command/CoffeeMachineSettingSteamFlushEnabled"

    mock_aiointercept.post(
        url=url,
        status=200,
        payload=MOCK_COMMAND_RESPONSE,
    )

    client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA)

    result = await client.set_steam_flush(serial, False)

    call = mock_aiointercept.requests[(HTTPMethod.POST, URL(url))][0]
    assert await call.json() == {"enabled": False}
    assert result is True


async def test_set_rinse_flush(
    mock_aiointercept: aiointercept,
    serial: str,
) -> None:
    """Test enabling rinse flush for a thing."""

    url = f"{CUSTOMER_APP_URL}/things/{serial}/command/CoffeeMachineSettingRinseFlushEnabled"

    mock_aiointercept.post(
        url=url,
        status=200,
        payload=MOCK_COMMAND_RESPONSE,
    )

    client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA)

    result = await client.set_rinse_flush(serial, True)

    call = mock_aiointercept.requests[(HTTPMethod.POST, URL(url))][0]
    assert await call.json() == {"enabled": True}
    assert result is True


async def test_set_hot_water_dose_enabled(
    mock_aiointercept: aiointercept,
    serial: str,
) -> None:
    """Test enabling the hot water dose for a thing."""

    url = f"{CUSTOMER_APP_URL}/things/{serial}/command/CoffeeMachineSettingHotWaterDoseEnabled"

    mock_aiointercept.post(
        url=url,
        status=200,
        payload=MOCK_COMMAND_RESPONSE,
    )

    client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA)

    result = await client.set_hot_water_dose_enabled(serial, False)

    call = mock_aiointercept.requests[(HTTPMethod.POST, URL(url))][0]
    assert await call.json() == {"enabled": False}
    assert result is True


async def test_set_cup_warmer(
    mock_aiointercept: aiointercept,
    serial: str,
) -> None:
    """Test enabling the cup warmer for a thing."""

    url = f"{CUSTOMER_APP_URL}/things/{serial}/command/CoffeeMachineSettingCupWarmerEnabled"

    mock_aiointercept.post(
        url=url,
        status=200,
        payload=MOCK_COMMAND_RESPONSE,
    )

    client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA)

    result = await client.set_cup_warmer(serial, True)

    call = mock_aiointercept.requests[(HTTPMethod.POST, URL(url))][0]
    assert await call.json() == {"enabled": True}
    assert result is True


async def test_set_group_mode(
    mock_aiointercept: aiointercept,
    serial: str,
) -> None:
    """Test setting the mode of a single group."""

    url = f"{CUSTOMER_APP_URL}/things/{serial}/command/CoffeeMachineGroupChangeMode"

    mock_aiointercept.post(url=url, status=200, payload=MOCK_COMMAND_RESPONSE)

    client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA)

    result = await client.set_group_mode(serial, MachineMode.BREWING_MODE)

    call = mock_aiointercept.requests[(HTTPMethod.POST, URL(url))][0]
    assert await call.json() == {"groupIndex": 1, "mode": "BrewingMode"}
    assert result is True


async def test_set_coffee_boiler(
    mock_aiointercept: aiointercept,
    serial: str,
) -> None:
    """Test enabling the coffee boiler."""

    url = (
        f"{CUSTOMER_APP_URL}/things/{serial}/command/"
        "CoffeeMachineSettingCoffeeBoilerEnabled"
    )

    mock_aiointercept.post(url=url, status=200, payload=MOCK_COMMAND_RESPONSE)

    client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA)

    result = await client.set_coffee_boiler(serial, True)

    call = mock_aiointercept.requests[(HTTPMethod.POST, URL(url))][0]
    assert await call.json() == {"boilerIndex": 1, "enabled": True}
    assert result is True


async def test_set_rinse_flush_time(
    mock_aiointercept: aiointercept,
    serial: str,
) -> None:
    """Test setting the rinse flush time."""

    url = f"{CUSTOMER_APP_URL}/things/{serial}/command/CoffeeMachineSettingRinseFlushTime"

    mock_aiointercept.post(url=url, status=200, payload=MOCK_COMMAND_RESPONSE)

    client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA)

    result = await client.set_rinse_flush_time(serial, 4.0)

    call = mock_aiointercept.requests[(HTTPMethod.POST, URL(url))][0]
    assert await call.json() == {"timeSeconds": 4.0}
    assert result is True


async def test_set_hot_water_dose(
    mock_aiointercept: aiointercept,
    serial: str,
) -> None:
    """Test setting a hot water dose value."""

    url = f"{CUSTOMER_APP_URL}/things/{serial}/command/CoffeeMachineSettingHotWaterDose"

    mock_aiointercept.post(url=url, status=200, payload=MOCK_COMMAND_RESPONSE)

    client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA)

    result = await client.set_hot_water_dose(serial, 8.0, DoseIndex.DOSE_A)

    call = mock_aiointercept.requests[(HTTPMethod.POST, URL(url))][0]
    assert await call.json() == {"doseIndex": "DoseA", "dose": 8.0}
    assert result is True


async def test_set_group_dose_mode(
    mock_aiointercept: aiointercept,
    serial: str,
) -> None:
    """Test setting the dose mode of a group."""

    url = (
        f"{CUSTOMER_APP_URL}/things/{serial}/command/CoffeeMachineGroupDoseChangeMode"
    )

    mock_aiointercept.post(url=url, status=200, payload=MOCK_COMMAND_RESPONSE)

    client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA)

    result = await client.set_group_dose_mode(serial, DoseMode.PULSES_TYPE)

    call = mock_aiointercept.requests[(HTTPMethod.POST, URL(url))][0]
    assert await call.json() == {"groupIndex": 1, "mode": "PulsesType"}
    assert result is True


async def test_set_group_dose(
    mock_aiointercept: aiointercept,
    serial: str,
) -> None:
    """Test setting a group dose value."""

    url = (
        f"{CUSTOMER_APP_URL}/things/{serial}/command/CoffeeMachineGroupDoseSettingDose"
    )

    mock_aiointercept.post(url=url, status=200, payload=MOCK_COMMAND_RESPONSE)

    client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA)

    result = await client.set_group_dose(
        serial, DoseMode.PULSES_TYPE, DoseIndex.DOSE_A, 36.0
    )

    call = mock_aiointercept.requests[(HTTPMethod.POST, URL(url))][0]
    assert await call.json() == {
        "groupIndex": 1,
        "mode": "PulsesType",
        "doseIndex": "DoseA",
        "dose": 36.0,
    }
    assert result is True


async def test_set_brewing_pressure(
    mock_aiointercept: aiointercept,
    serial: str,
) -> None:
    """Test setting the brewing pressure of a group."""

    url = (
        f"{CUSTOMER_APP_URL}/things/{serial}/command/"
        "CoffeeMachineGroupDoseSettingGroupBrewingPressure"
    )

    mock_aiointercept.post(url=url, status=200, payload=MOCK_COMMAND_RESPONSE)

    client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA)

    result = await client.set_brewing_pressure(serial, 9.0)

    call = mock_aiointercept.requests[(HTTPMethod.POST, URL(url))][0]
    assert await call.json() == {"groupIndex": 1, "pressure": 9.0}
    assert result is True


async def test_set_continuous_dose_enabled(
    mock_aiointercept: aiointercept,
    serial: str,
) -> None:
    """Test enabling the continuous dose of a group."""

    url = (
        f"{CUSTOMER_APP_URL}/things/{serial}/command/"
        "CoffeeMachineGroupDoseSettingContinuousDoseEnabled"
    )

    mock_aiointercept.post(url=url, status=200, payload=MOCK_COMMAND_RESPONSE)

    client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA)

    result = await client.set_continuous_dose_enabled(serial, True)

    call = mock_aiointercept.requests[(HTTPMethod.POST, URL(url))][0]
    assert await call.json() == {"groupIndex": 1, "rinseEnabled": True}
    assert result is True


async def test_set_continuous_dose(
    mock_aiointercept: aiointercept,
    serial: str,
) -> None:
    """Test setting the continuous dose duration of a group."""

    url = (
        f"{CUSTOMER_APP_URL}/things/{serial}/command/"
        "CoffeeMachineGroupDoseSettingContinuousDose"
    )

    mock_aiointercept.post(url=url, status=200, payload=MOCK_COMMAND_RESPONSE)

    client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA)

    result = await client.set_continuous_dose(serial, 3.0)

    call = mock_aiointercept.requests[(HTTPMethod.POST, URL(url))][0]
    assert await call.json() == {"groupIndex": 1, "rinseSeconds": 3.0}
    assert result is True


async def test_set_mirror_group1(
    mock_aiointercept: aiointercept,
    serial: str,
) -> None:
    """Test mirroring a group with group 1."""

    url = (
        f"{CUSTOMER_APP_URL}/things/{serial}/command/"
        "CoffeeMachineGroupDoseSettingMirrorGroup1"
    )

    mock_aiointercept.post(url=url, status=200, payload=MOCK_COMMAND_RESPONSE)

    client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA)

    result = await client.set_mirror_group1(serial, True)

    call = mock_aiointercept.requests[(HTTPMethod.POST, URL(url))][0]
    assert await call.json() == {"groupIndex": 2, "enabled": True}
    assert result is True


async def test_set_plumb_in(
    mock_aiointercept: aiointercept,
    serial: str,
) -> None:
    """Test enabling plumb-in mode."""

    url = f"{CUSTOMER_APP_URL}/things/{serial}/command/CoffeeMachineSettingPlumbIn"

    mock_aiointercept.post(url=url, status=200, payload=MOCK_COMMAND_RESPONSE)

    client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA)

    result = await client.set_plumb_in(serial, True)

    call = mock_aiointercept.requests[(HTTPMethod.POST, URL(url))][0]
    assert await call.json() == {"enabled": True}
    assert result is True


@pytest.mark.usefixtures("mock_websocket", "mock_wait_for_ws_command_response")
async def test_set_grinder_mode(
    mock_aiointercept: aiointercept,
    serial: str,
) -> None:
    """Test setting the mode (wake/standby) for a grinder."""

    url = f"{CUSTOMER_APP_URL}/things/{serial}/command/GrinderChangeMode"

    mock_aiointercept.post(
        url=url,
        status=200,
        payload=MOCK_COMMAND_RESPONSE,
    )

    client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA)

    result = await client.set_grinder_mode(serial, GrinderMode.GRINDING)

    call = mock_aiointercept.requests[(HTTPMethod.POST, URL(url))][0]
    assert await call.json() == {"mode": "GrindingMode"}
    assert result is True


@pytest.mark.usefixtures("mock_websocket", "mock_wait_for_ws_command_response")
async def test_set_grinder_barista_light(
    mock_aiointercept: aiointercept,
    serial: str,
) -> None:
    """Test setting the barista light for a grinder."""

    url = f"{CUSTOMER_APP_URL}/things/{serial}/command/GrinderSettingBaristaLightEnabled"

    mock_aiointercept.post(
        url=url,
        status=200,
        payload=MOCK_COMMAND_RESPONSE,
    )

    client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA)

    result = await client.set_grinder_barista_light(serial, True)

    call = mock_aiointercept.requests[(HTTPMethod.POST, URL(url))][0]
    assert await call.json() == {"index": 1, "enabled": True}
    assert result is True


async def test_set_grinder_grind_with(
    mock_aiointercept: aiointercept,
    serial: str,
) -> None:
    """Test setting the grind-with mode for a grinder."""

    url = f"{CUSTOMER_APP_URL}/things/{serial}/command/GrinderSettingGrindWithMode"

    mock_aiointercept.post(
        url=url,
        status=200,
        payload=MOCK_COMMAND_RESPONSE,
    )

    client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA)

    result = await client.set_grinder_grind_with(
        serial, GrinderGrindWithMode.BY_BUTTON
    )

    call = mock_aiointercept.requests[(HTTPMethod.POST, URL(url))][0]
    assert await call.json() == {"index": 1, "mode": "ByButton"}
    assert result is True


async def test_set_grinder_dose(
    mock_aiointercept: aiointercept,
    serial: str,
) -> None:
    """Test setting the dose and speed level for a grinder."""

    url = f"{CUSTOMER_APP_URL}/things/{serial}/command/GrinderSettingDose"

    mock_aiointercept.post(
        url=url,
        status=200,
        payload=MOCK_COMMAND_RESPONSE,
    )

    client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA)

    result = await client.set_grinder_dose(
        serial,
        DoseIndex.DOSE_A,
        12.0,
        GrinderDoseMode.REV,
        GrinderSpeedLevelType.HIGH,
    )

    call = mock_aiointercept.requests[(HTTPMethod.POST, URL(url))][0]
    assert await call.json() == {
        "index": 1,
        "mode": "RevType",
        "doseIndex": "DoseA",
        "dose": 12.0,
        "speedLevel": "High",
    }
    assert result is True


async def test_set_grinder_dose_without_speed(
    mock_aiointercept: aiointercept,
    serial: str,
) -> None:
    """Test setting the dose without a speed level for a grinder."""

    url = f"{CUSTOMER_APP_URL}/things/{serial}/command/GrinderSettingDose"

    mock_aiointercept.post(
        url=url,
        status=200,
        payload=MOCK_COMMAND_RESPONSE,
    )

    client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA)

    result = await client.set_grinder_dose(
        serial, DoseIndex.DOSE_B, 9.7, GrinderDoseMode.REV
    )

    call = mock_aiointercept.requests[(HTTPMethod.POST, URL(url))][0]
    assert await call.json() == {
        "index": 1,
        "mode": "RevType",
        "doseIndex": "DoseB",
        "dose": 9.7,
    }
    assert result is True


async def test_set_grinder_more_dose(
    mock_aiointercept: aiointercept,
    serial: str,
) -> None:
    """Test setting the more-dose revolutions for a grinder."""

    url = f"{CUSTOMER_APP_URL}/things/{serial}/command/GrinderSettingMoreDose"

    mock_aiointercept.post(
        url=url,
        status=200,
        payload=MOCK_COMMAND_RESPONSE,
    )

    client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA)

    result = await client.set_grinder_more_dose(serial, 2.5)

    call = mock_aiointercept.requests[(HTTPMethod.POST, URL(url))][0]
    assert await call.json() == {"index": 1, "revolutions": 2.5}
    assert result is True


@pytest.mark.usefixtures("mock_websocket", "mock_wait_for_ws_command_response")
async def test_failing_response_ws_validation(
    mock_aiointercept: aiointercept,
    mock_ws_command_response: CommandResponse,
    serial: str,
) -> None:
    """Tests failing response from websocket"""

    url = f"{CUSTOMER_APP_URL}/things/{serial}/command/CoffeeMachineChangeMode"

    mock_aiointercept.post(
        url=url,
        status=200,
        payload=MOCK_COMMAND_RESPONSE,
    )

    mock_ws_command_response.status = CommandStatus.ERROR

    client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA)

    result = await client.set_power(serial, False)
    assert result is False


@pytest.mark.usefixtures("mock_websocket", "mock_wait_for_ws_command_response")
async def test_pending_command_ws_validation_timeout(
    mock_aiointercept: aiointercept,
    mock_wait_for_ws_command_response: AsyncMock,
    serial: str,
) -> None:
    """Tests failing response from websocket"""

    url = f"{CUSTOMER_APP_URL}/things/{serial}/command/CoffeeMachineChangeMode"

    mock_aiointercept.post(
        url=url,
        status=200,
        payload=MOCK_COMMAND_RESPONSE,
    )

    mock_wait_for_ws_command_response.side_effect = TimeoutError

    client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA)

    result = await client.set_power(serial, False)
    assert result is False


async def test_disconnected_ws_returns_true(
    mock_aiointercept: aiointercept,
    mock_websocket: MagicMock,
    serial: str,
) -> None:
    """Test setting the power for a thing."""

    url = f"{CUSTOMER_APP_URL}/things/{serial}/command/CoffeeMachineChangeMode"

    mock_aiointercept.post(
        url=url,
        status=200,
        payload=MOCK_COMMAND_RESPONSE,
    )

    client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA)

    mock_websocket.connected = False

    result = await client.set_power(serial, False)

    call = mock_aiointercept.requests[(HTTPMethod.POST, URL(url))][0]
    assert await call.json() == {"mode": "StandBy"}
    assert result is True


async def test_set_steam(
    mock_aiointercept: aiointercept,
    serial: str,
) -> None:
    """Test setting the steam for a thing."""

    url = f"{CUSTOMER_APP_URL}/things/{serial}/command/CoffeeMachineSettingSteamBoilerEnabled"

    mock_aiointercept.post(
        url=url,
        status=200,
        payload=MOCK_COMMAND_RESPONSE,
    )

    client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA)
    result = await client.set_steam(serial, True)

    call = mock_aiointercept.requests[(HTTPMethod.POST, URL(url))][0]
    assert await call.json() == {
        "boilerIndex": 1,
        "enabled": True,
    }
    assert result is True


async def test_set_coffee_temperature(
    mock_aiointercept: aiointercept,
    serial: str,
) -> None:
    """Test setting the steam for a thing."""

    url = f"{CUSTOMER_APP_URL}/things/{serial}/command/CoffeeMachineSettingCoffeeBoilerTargetTemperature"

    mock_aiointercept.post(
        url=url,
        status=200,
        payload=MOCK_COMMAND_RESPONSE,
    )

    client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA)
    result = await client.set_coffee_target_temperature(serial, 94.584)

    call = mock_aiointercept.requests[(HTTPMethod.POST, URL(url))][0]
    assert await call.json() == {
        "boilerIndex": 1,
        "targetTemperature": 94.6,
    }
    assert result is True


async def test_set_steam_target_level(
    mock_aiointercept: aiointercept,
    serial: str,
) -> None:
    """Test setting the steam target level for a thing."""

    url = f"{CUSTOMER_APP_URL}/things/{serial}/command/CoffeeMachineSettingSteamBoilerTargetLevel"

    mock_aiointercept.post(
        url=url,
        status=200,
        payload=MOCK_COMMAND_RESPONSE,
    )

    client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA)
    result = await client.set_steam_target_level(serial, SteamTargetLevel.LEVEL_1)
    call = mock_aiointercept.requests[(HTTPMethod.POST, URL(url))][0]
    assert await call.json() == {
        "boilerIndex": 1,
        "targetLevel": "Level1",
    }
    assert result is True


async def test_set_steam_target_temperature(
    mock_aiointercept: aiointercept,
    serial: str,
) -> None:
    """Test setting the steam target temperature for a thing."""

    url = f"{CUSTOMER_APP_URL}/things/{serial}/command/CoffeeMachineSettingSteamBoilerTargetTemperature"

    mock_aiointercept.post(
        url=url,
        status=200,
        payload=MOCK_COMMAND_RESPONSE,
    )

    client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA)
    result = await client.set_steam_target_temperature(serial, 122.1)
    call = mock_aiointercept.requests[(HTTPMethod.POST, URL(url))][0]
    assert await call.json() == {
        "boilerIndex": 1,
        "targetTemperature": 122.1,
    }
    assert result is True


async def test_start_backflush_cleaning(
    mock_aiointercept: aiointercept,
    serial: str,
) -> None:
    """Test starting backflush cleaning for a thing."""

    url = f"{CUSTOMER_APP_URL}/things/{serial}/command/CoffeeMachineBackFlushStartCleaning"
    mock_aiointercept.post(
        url=url,
        status=200,
        payload=MOCK_COMMAND_RESPONSE,
    )

    client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA)
    result = await client.start_backflush_cleaning(serial)
    call = mock_aiointercept.requests[(HTTPMethod.POST, URL(url))][0]
    assert await call.json() == {
        "enabled": True,
    }
    assert result is True


async def test_change_pre_extraction_mode(
    mock_aiointercept: aiointercept,
    serial: str,
) -> None:
    """Test changing the pre-extraction mode for a thing."""

    url = (
        f"{CUSTOMER_APP_URL}/things/{serial}/command/CoffeeMachinePreBrewingChangeMode"
    )
    mock_aiointercept.post(
        url=url,
        status=200,
        payload=MOCK_COMMAND_RESPONSE,
    )

    client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA)
    result = await client.change_pre_extraction_mode(
        serial, PreExtractionMode.PREBREWING
    )
    call = mock_aiointercept.requests[(HTTPMethod.POST, URL(url))][0]
    assert await call.json() == {
        "mode": "PreBrewing",
    }
    assert result is True


async def test_change_pre_extraction_times(
    mock_aiointercept: aiointercept,
    serial: str,
) -> None:
    """Test changing the pre-extraction times for a thing."""

    url = f"{CUSTOMER_APP_URL}/things/{serial}/command/CoffeeMachinePreBrewingSettingTimes"
    mock_aiointercept.post(
        url=url,
        status=200,
        payload=MOCK_COMMAND_RESPONSE,
    )

    client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA)
    result = await client.change_pre_extraction_times(
        serial,
        PrebrewSettingTimes(times=SecondsInOut(seconds_in=5.12, seconds_out=5.03)),
    )
    call = mock_aiointercept.requests[(HTTPMethod.POST, URL(url))][0]
    assert await call.json() == {
        "times": {"In": 5.1, "Out": 5.0},
        "groupIndex": 1,
        "doseIndex": "ByGroup",
    }
    assert result is True


async def test_setting_smart_standby(
    mock_aiointercept: aiointercept,
    serial: str,
) -> None:
    """Test setting the smart standby for a thing."""

    url = f"{CUSTOMER_APP_URL}/things/{serial}/command/CoffeeMachineSettingSmartStandBy"
    mock_aiointercept.post(
        url=url,
        status=200,
        payload=MOCK_COMMAND_RESPONSE,
    )

    client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA)
    result = await client.set_smart_standby(
        serial, False, 20, SmartStandByType.LAST_BREW
    )
    call = mock_aiointercept.requests[(HTTPMethod.POST, URL(url))][0]
    assert await call.json() == {
        "enabled": False,
        "minutes": 20,
        "after": "LastBrewing",
    }
    assert result is True


async def test_set_wake_up_schedule(
    mock_aiointercept: aiointercept,
    serial: str,
) -> None:
    """Test setting the wake up schedule for a thing."""

    url = f"{CUSTOMER_APP_URL}/things/{serial}/command/CoffeeMachineSettingWakeUpSchedule"
    mock_aiointercept.post(
        url=url,
        status=200,
        payload=MOCK_COMMAND_RESPONSE,
        repeat=2,
    )

    client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA)

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
    mock_aiointercept: aiointercept, serial: str, snapshot: SnapshotAssertion
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

    client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA)
    result = await client.get_thing_firmware(serial)
    assert result.to_dict() == snapshot


async def test_start_update(
    mock_aiointercept: aiointercept, serial: str, snapshot: SnapshotAssertion
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

    client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA)
    result = await client.update_firmware(serial)
    assert result.to_dict() == snapshot


async def test_change_brew_by_weight_dose_mode(
    mock_aiointercept: aiointercept,
    serial: str,
) -> None:
    """Test changing the brew by weight dose mode."""

    url = f"{CUSTOMER_APP_URL}/things/{serial}/command/CoffeeMachineBrewByWeightChangeMode"
    mock_aiointercept.post(
        url=url,
        status=200,
        payload=MOCK_COMMAND_RESPONSE,
    )

    client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA)
    result = await client.change_brew_by_weight_dose_mode(serial, DoseMode.DOSE_1)
    call = mock_aiointercept.requests[(HTTPMethod.POST, URL(url))][0]
    assert await call.json() == {"mode": "Dose1"}
    assert result is True


async def test_set_brew_by_weight_dose(
    mock_aiointercept: aiointercept,
    serial: str,
) -> None:
    """Test setting the brew by weight doses."""

    url = f"{CUSTOMER_APP_URL}/things/{serial}/command/CoffeeMachineBrewByWeightSettingDoses"
    mock_aiointercept.post(
        url=url,
        status=200,
        payload=MOCK_COMMAND_RESPONSE,
    )

    client = LaMarzoccoCloudClient("test", "test", MOCK_SECRET_DATA)
    result = await client.set_brew_by_weight_dose(serial, 32.56, 45.67)
    call = mock_aiointercept.requests[(HTTPMethod.POST, URL(url))][0]
    assert await call.json() == {
        "doses": {
            "Dose1": 32.6,
            "Dose2": 45.7,
        }
    }
    assert result is True
