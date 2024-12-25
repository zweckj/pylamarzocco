"""Test the LaMarzoccoMachine class."""

# pylint: disable=W0212
from dataclasses import asdict
from http import HTTPMethod
from unittest.mock import AsyncMock, patch
from aiohttp import ClientTimeout
import pytest

from aioresponses import aioresponses
from bleak import BleakError
from syrupy import SnapshotAssertion

from pylamarzocco.clients.bluetooth import LaMarzoccoBluetoothClient
from pylamarzocco.clients.cloud import LaMarzoccoCloudClient
from pylamarzocco.clients.local import LaMarzoccoLocalClient
from pylamarzocco.const import (
    BoilerType,
    PhysicalKey,
    MachineModel,
    GW_MACHINE_BASE_URL,
)
from pylamarzocco.devices.machine import LaMarzoccoMachine
from pylamarzocco.models import LaMarzoccoBrewByWeightSettings

from . import init_machine
from .conftest import load_fixture

CLIENT_TIMEOUT = ClientTimeout(
    total=5, connect=None, sock_read=None, sock_connect=None, ceil_threshold=5
)


async def test_create(
    cloud_client: LaMarzoccoCloudClient,
    snapshot: SnapshotAssertion,
) -> None:
    """Test creation of a cloud client."""

    machine = await init_machine(cloud_client)
    assert asdict(machine.config) == snapshot(name="config")
    assert machine.firmware == snapshot(name="firmware")
    assert machine.statistics == snapshot(name="statistics")


async def test_mini(
    cloud_client: LaMarzoccoCloudClient,
    mock_aioresponse: aioresponses,
    snapshot: SnapshotAssertion,
) -> None:
    """Test creation of a cloud client."""
    serial = "LM01234"
    mock_aioresponse.get(
        url=f"{GW_MACHINE_BASE_URL}/{serial}/configuration",
        status=200,
        payload=load_fixture("machine", "config-mini.json"),
    )
    mock_aioresponse.get(
        url=f"{GW_MACHINE_BASE_URL}/{serial}/statistics/counters",
        status=200,
        payload=load_fixture("machine", "counters.json"),
    )
    mock_aioresponse.get(
        url=f"{GW_MACHINE_BASE_URL}/{serial}/firmware/",
        status=200,
        payload=load_fixture("machine", "firmware.json"),
    )
    machine = await LaMarzoccoMachine.create(
        model=MachineModel.LINEA_MINI,
        serial_number=serial,
        name="MyMachine",
        cloud_client=cloud_client,
    )

    assert asdict(machine.config) == snapshot


async def test_local_client(
    machine: LaMarzoccoMachine,
    local_machine_client: LaMarzoccoLocalClient,
    mock_aioresponse: aioresponses,
) -> None:
    """Ensure that the local client delivers same result"""
    # load config
    mock_aioresponse.get(
        url="http://192.168.1.42:8081/api/v1/config",
        status=200,
        payload=load_fixture("machine", "config.json")["data"],
    )

    machine_local = await init_machine(local_client=local_machine_client)

    assert machine_local
    assert str(machine.config) == str(machine_local.config)


async def test_set_temp(machine: LaMarzoccoMachine) -> None:
    """Test setting boiler temperature."""

    result = await machine.set_temp(
        BoilerType.STEAM,
        120,
    )
    assert result is True
    assert machine.config.boilers[BoilerType.STEAM].target_temperature == 120


# async def test_set_schedule(
#     cloud_client: LaMarzoccoCloudClient,
# ) -> None:
#     """Test setting prebrew infusion."""
#     machine = await init_machine(cloud_client)

#     with patch("asyncio.sleep", new_callable=AsyncMock):
#         result = await machine.set_schedule_day(
#             day=WeekDay.MONDAY,
#             enabled=True,
#             h_on=3,
#             m_on=0,
#             h_off=24,
#             m_off=0,
#         )
#     assert result is True


async def test_set_power(
    cloud_client: LaMarzoccoCloudClient,
    bluetooth_client: LaMarzoccoBluetoothClient,
    mock_aioresponse: aioresponses,
):
    """Test setting the power."""
    machine = await init_machine(cloud_client, bluetooth_client=bluetooth_client)

    with patch(
        "pylamarzocco.clients.bluetooth.LaMarzoccoBluetoothClient.set_power",
        new=AsyncMock(),
    ) as mock_set_power:
        mock_set_power.side_effect = BleakError("Failed to write")
        assert await machine.set_power(True)

        mock_aioresponse.assert_called_with(  # type: ignore[attr-defined]
            method=HTTPMethod.POST,
            url="https://gw-lmz.lamarzocco.io/v1/home/machines/GS01234/status",
            json={"status": "BrewingMode"},
            headers={"Authorization": "Bearer 123"},
            timeout=CLIENT_TIMEOUT,
            allow_redirects=True,
            data=None,
        )


async def test_set_steam(
    cloud_client: LaMarzoccoCloudClient,
    bluetooth_client: LaMarzoccoBluetoothClient,
    mock_aioresponse: aioresponses,
):
    """Test setting the steam."""
    machine = await init_machine(cloud_client, bluetooth_client=bluetooth_client)

    with patch(
        "pylamarzocco.clients.bluetooth.LaMarzoccoBluetoothClient.set_steam",
        new=AsyncMock(),
    ) as mock_set_steam:
        mock_set_steam.side_effect = BleakError("Failed to write")

        assert await machine.set_steam(True)

        mock_aioresponse.assert_called_with(  # type: ignore[attr-defined]
            method=HTTPMethod.POST,
            url="https://gw-lmz.lamarzocco.io/v1/home/machines/GS01234/enable-boiler",
            json={"identifier": "SteamBoiler", "state": True},
            headers={"Authorization": "Bearer 123"},
            timeout=CLIENT_TIMEOUT,
            allow_redirects=True,
            data=None,
        )


async def test_set_temperature(
    cloud_client: LaMarzoccoCloudClient,
    bluetooth_client: LaMarzoccoBluetoothClient,
    mock_aioresponse: aioresponses,
):
    """Test setting temperature."""
    machine = await init_machine(cloud_client, bluetooth_client=bluetooth_client)

    with patch(
        "pylamarzocco.clients.bluetooth.LaMarzoccoBluetoothClient.set_temp",
        new=AsyncMock(),
    ) as mock_set_temp:
        mock_set_temp.side_effect = BleakError("Failed to write")

        assert await machine.set_temp(BoilerType.STEAM, 131)

        mock_aioresponse.assert_called_with(  # type: ignore[attr-defined]
            method=HTTPMethod.POST,
            url="https://gw-lmz.lamarzocco.io/v1/home/machines/GS01234/target-boiler",
            json={"identifier": "SteamBoiler", "value": 131},
            headers={"Authorization": "Bearer 123"},
            timeout=CLIENT_TIMEOUT,
            allow_redirects=True,
            data=None,
        )


async def test_set_prebrew_time(
    machine: LaMarzoccoMachine,
    mock_aioresponse: aioresponses,
):
    """Test setting prebrew time."""

    assert await machine.set_prebrew_time(1.0, 3.5)

    mock_aioresponse.assert_called_with(  # type: ignore[attr-defined]
        method=HTTPMethod.POST,
        url="https://gw-lmz.lamarzocco.io/v1/home/machines/GS01234/setting-preinfusion",
        json={
            "button": "DoseA",
            "group": "Group1",
            "holdTimeMs": 3500,
            "wetTimeMs": 1000,
        },
        headers={"Authorization": "Bearer 123"},
        timeout=CLIENT_TIMEOUT,
        allow_redirects=True,
        data=None,
    )

    assert machine.config.prebrew_configuration[PhysicalKey.A].on_time == 1.0
    assert machine.config.prebrew_configuration[PhysicalKey.A].off_time == 3.5


async def test_set_preinfusion_time(
    machine: LaMarzoccoMachine,
    mock_aioresponse: aioresponses,
):
    """Test setting prebrew time."""
    assert await machine.set_preinfusion_time(4.5)
    mock_aioresponse.assert_called_with(  # type: ignore[attr-defined]
        method=HTTPMethod.POST,
        url="https://gw-lmz.lamarzocco.io/v1/home/machines/GS01234/setting-preinfusion",
        json={"button": "DoseA", "group": "Group1", "holdTimeMs": 4500, "wetTimeMs": 0},
        headers={"Authorization": "Bearer 123"},
        timeout=CLIENT_TIMEOUT,
        allow_redirects=True,
        data=None,
    )

    assert machine.config.prebrew_configuration[PhysicalKey.A].off_time == 4.5


async def test_set_scale_target(
    machine: LaMarzoccoMachine,
    mock_aioresponse: aioresponses,
):
    """Test setting scale target."""
    # fails with not Linea Mini
    with pytest.raises(ValueError):
        await machine.set_scale_target(PhysicalKey.B, 42)

    # set to Linea Mini
    machine.model = MachineModel.LINEA_MINI
    machine.config.bbw_settings = LaMarzoccoBrewByWeightSettings(
        doses={}, active_dose=PhysicalKey.A
    )

    assert await machine.set_scale_target(PhysicalKey.B, 42)
    mock_aioresponse.assert_called_with(  # type: ignore[attr-defined]
        method=HTTPMethod.POST,
        url="https://gw-lmz.lamarzocco.io/v1/home/machines/GS01234/scale/target-dose",
        json={
            "group": "Group1",
            "dose_index": "DoseB",
            "dose_type": "MassType",
            "value": 42,
        },
        headers={"Authorization": "Bearer 123"},
        timeout=CLIENT_TIMEOUT,
        allow_redirects=True,
        data=None,
    )

    assert machine.config.bbw_settings.doses[PhysicalKey.B] == 42


async def test_set_bbw_recipe(
    machine: LaMarzoccoMachine,
    mock_aioresponse: aioresponses,
):
    """Test setting scale target."""
    # fails with not Linea Mini
    with pytest.raises(ValueError):
        await machine.set_bbw_recipe_target(PhysicalKey.B, 42)

    # set to Linea Mini
    machine.model = MachineModel.LINEA_MINI
    machine.config.bbw_settings = LaMarzoccoBrewByWeightSettings(
        doses={PhysicalKey.A: 12, PhysicalKey.B: 34}, active_dose=PhysicalKey.A
    )

    assert await machine.set_bbw_recipe_target(PhysicalKey.B, 42)
    mock_aioresponse.assert_called_with(  # type: ignore[attr-defined]
        method=HTTPMethod.PUT,
        url="https://gw-lmz.lamarzocco.io/v1/home/machines/GS01234/recipes/",
        json={
            "recipeId": "Recipe1",
            "doseMode": "Mass",
            "recipeDoses": [
                {"id": "A", "target": 12},
                {"id": "B", "target": 42},
            ],
        },
        headers={"Authorization": "Bearer 123"},
        timeout=CLIENT_TIMEOUT,
        allow_redirects=True,
    )

    assert machine.config.bbw_settings.doses[PhysicalKey.B] == 42


async def test_set_active_bbw_recipe(
    machine: LaMarzoccoMachine,
    mock_aioresponse: aioresponses,
):
    """Test active bbw recipe."""
    # fails with not Linea Mini
    with pytest.raises(ValueError):
        await machine.set_active_bbw_recipe(PhysicalKey.B)

    # set to Linea Mini
    machine.model = MachineModel.LINEA_MINI
    machine.config.bbw_settings = LaMarzoccoBrewByWeightSettings(
        doses={PhysicalKey.A: 12, PhysicalKey.B: 34}, active_dose=PhysicalKey.A
    )

    assert await machine.set_active_bbw_recipe(PhysicalKey.B)
    mock_aioresponse.assert_called_with(  # type: ignore[attr-defined]
        method=HTTPMethod.POST,
        url="https://gw-lmz.lamarzocco.io/v1/home/machines/GS01234/recipes/active-recipe",
        json={
            "group": "Group1",
            "doseIndex": "DoseA",
            "recipeId": "Recipe1",
            "recipeDose": "B",
        },
        headers={"Authorization": "Bearer 123"},
        timeout=CLIENT_TIMEOUT,
        allow_redirects=True,
        data=None,
    )

    assert machine.config.bbw_settings.active_dose == PhysicalKey.B
