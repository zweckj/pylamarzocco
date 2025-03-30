"""Test the bluetooth client."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from pylamarzocco import LaMarzoccoBluetoothClient
from pylamarzocco.const import BoilerType, MachineMode, ModelName, SmartStandByType
from pylamarzocco.models import (
    BluetoothBoilerDetails,
    BluetoothMachineCapabilities,
    BluetoothSmartStandbyDetails,
)


@pytest.fixture(name="mock_bleak_client", autouse=True)
def bleak_client() -> Generator[MagicMock]:
    """Fixture to create a mock BleakClient."""
    with patch(
        "pylamarzocco.clients._bluetooth.BleakClient", autospec=True
    ) as mock_bleak:
        mock_client = mock_bleak.return_value
        mock_client.is_connected = True
        mock_client.services.get_characteristic.return_value = "mock_characteristic"
        yield mock_client


SETTINGS_CHAR = "0b0b7847-e12b-09a8-b04b-8e0922a9abab"
AUTH_CHAR = "0d0b7847-e12b-09a8-b04b-8e0922a9abab"
READ_CHAR = "0a0b7847-e12b-09a8-b04b-8e0922a9abab"


async def test_context_manager(mock_bleak_client: MagicMock) -> None:
    """Test context manager for LaMarzoccoBluetoothClient."""
    async with LaMarzoccoBluetoothClient("test", "token"):
        pass
    mock_bleak_client.connect.assert_called_once()
    mock_bleak_client.services.get_characteristic.assert_called_with(AUTH_CHAR)
    mock_bleak_client.write_gatt_char.assert_called_once_with(
        char_specifier="mock_characteristic", data=b"token", response=True
    )
    mock_bleak_client.disconnect.assert_called_once()


async def test_ble_set_power(mock_bleak_client: MagicMock) -> None:
    """Test setting power on the machine."""
    async with LaMarzoccoBluetoothClient("test", "token") as client:
        await client.set_power(True)

    mock_bleak_client.services.get_characteristic.assert_called_with(SETTINGS_CHAR)
    mock_bleak_client.write_gatt_char.assert_called_with(
        char_specifier="mock_characteristic",
        data=b'{"name":"MachineChangeMode","parameter":{"mode":"BrewingMode"}}\x00',
        response=True,
    )


async def test_ble_set_temperature(mock_bleak_client: MagicMock) -> None:
    """Test setting temperature on the machine."""
    async with LaMarzoccoBluetoothClient("test", "token") as client:
        await client.set_temp(BoilerType.STEAM, 90)
    mock_bleak_client.services.get_characteristic.assert_called_with(SETTINGS_CHAR)
    mock_bleak_client.write_gatt_char.assert_called_with(
        char_specifier="mock_characteristic",
        data=b'{"name":"SettingBoilerTarget","parameter":{"identifier":"SteamBoiler","value":90}}\x00',
        response=True,
    )


async def test_ble_set_smart_standby(mock_bleak_client: MagicMock) -> None:
    """Test setting smart standby on the machine."""
    async with LaMarzoccoBluetoothClient("test", "token") as client:
        await client.set_smart_standby(True, SmartStandByType.POWER_ON, 42)
    mock_bleak_client.services.get_characteristic.assert_called_with(SETTINGS_CHAR)
    mock_bleak_client.write_gatt_char.assert_called_with(
        char_specifier="mock_characteristic",
        data=b'{"name":"SettingSmartStandby","parameter":{"minutes":42,"mode":"PowerOn","enabled":true}}\x00',
        response=True,
    )


async def test_ble_get_machine_capability(mock_bleak_client: MagicMock) -> None:
    """Test getting machine capability."""
    mock_bleak_client.read_gatt_char.return_value = b'[{"family":"MICRA","groupsNumber":1,"coffeeBoilersNumber":1,"hasCupWarmer":false,"steamBoilersNumber":1,"teaDosesNumber":0,"machineModes":["BrewingMode","StandBy"],"schedulingType":"smartWakeUpSleep"}]'
    async with LaMarzoccoBluetoothClient("test", "token") as client:
        response = await client.get_machine_capabilities()
    mock_bleak_client.services.get_characteristic.assert_called_with(READ_CHAR)
    mock_bleak_client.write_gatt_char.assert_called_with(
        char_specifier="mock_characteristic",
        data=b"machineCapabilities\x00",
        response=True,
    )
    assert response == BluetoothMachineCapabilities(
        family=ModelName.LINEA_MICRA,
        groups_number=1,
        coffee_boilers_number=1,
        has_cup_warmer=False,
        steam_boilers_number=1,
        tea_doses_number=0,
        machine_modes=[MachineMode.BREWING_MODE, MachineMode.STANDBY],
        scheduling_type="smartWakeUpSleep",
    )


async def test_ble_get_boiler_details(mock_bleak_client: MagicMock) -> None:
    """Test getting boiler details."""
    mock_bleak_client.read_gatt_char.return_value = b'[{"id":"SteamBoiler","isEnabled":true,"target":131,"current":45},{"id":"CoffeeBoiler1","isEnabled":true,"target":94,"current":65}]'
    async with LaMarzoccoBluetoothClient("test", "token") as client:
        response = await client.get_boilers()
    mock_bleak_client.services.get_characteristic.assert_called_with(READ_CHAR)
    mock_bleak_client.write_gatt_char.assert_called_with(
        char_specifier="mock_characteristic",
        data=b"boilers\x00",
        response=True,
    )
    assert response == [
        BluetoothBoilerDetails(
            id=BoilerType.STEAM,
            is_enabled=True,
            target=131,
            current=45,
        ),
        BluetoothBoilerDetails(
            id=BoilerType.COFFEE,
            is_enabled=True,
            target=94,
            current=65,
        ),
    ]


async def test_ble_get_smart_standby_details(mock_bleak_client: MagicMock) -> None:
    """Test getting smart standby details."""
    mock_bleak_client.read_gatt_char.return_value = (
        b'{"mode":"PowerOn","minutes":42,"enabled":"true"}'
    )
    async with LaMarzoccoBluetoothClient("test", "token") as client:
        response = await client.get_smart_standby_settings()
    mock_bleak_client.services.get_characteristic.assert_called_with(READ_CHAR)
    mock_bleak_client.write_gatt_char.assert_called_with(
        char_specifier="mock_characteristic",
        data=b"smartStandBy\x00",
        response=True,
    )
    assert response == BluetoothSmartStandbyDetails(
        mode=SmartStandByType.POWER_ON, minutes=42, enabled=True
    )


async def test_ble_get_tank_status(mock_bleak_client: MagicMock) -> None:
    """Test getting tank status."""
    mock_bleak_client.read_gatt_char.return_value = b'"true"'
    async with LaMarzoccoBluetoothClient("test", "token") as client:
        response = await client.get_tank_status()
    mock_bleak_client.services.get_characteristic.assert_called_with(READ_CHAR)
    mock_bleak_client.write_gatt_char.assert_called_with(
        char_specifier="mock_characteristic",
        data=b"tankStatus\x00",
        response=True,
    )
    assert response is True


async def test_get_machine_mode(mock_bleak_client: MagicMock) -> None:
    """Test getting machine mode."""
    mock_bleak_client.read_gatt_char.return_value = b'"BrewingMode"'
    async with LaMarzoccoBluetoothClient("test", "token") as client:
        response = await client.get_machine_mode()
    mock_bleak_client.services.get_characteristic.assert_called_with(READ_CHAR)
    mock_bleak_client.write_gatt_char.assert_called_with(
        char_specifier="mock_characteristic",
        data=b"machineMode\x00",
        response=True,
    )
    assert response == MachineMode.BREWING_MODE
