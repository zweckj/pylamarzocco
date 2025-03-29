"""Test the bluetooth client."""

from unittest.mock import MagicMock

import pytest
from bleak import BleakClient

from pylamarzocco import LaMarzoccoBluetoothClient
from pylamarzocco.const import BoilerType, MachineMode, ModelName, SmartStandByType
from pylamarzocco.models import (
    BluetoothBoilerDetails,
    BluetoothMachineCapabilities,
    BluetoothSmartStandbyDetails,
)


@pytest.fixture(name="mock_bleak_client")
def bleak_client() -> MagicMock:
    """Fixture to create a mock BleakClient."""
    mock_client = MagicMock(spec=BleakClient)
    mock_client.is_connected = True
    mock_client.services.get_characteristic.return_value = "mock_characteristic"
    return mock_client


@pytest.fixture(name="lm_bluetooth_client")
def bluetooth_client() -> LaMarzoccoBluetoothClient:
    """Fixture to create an instance of LaMarzoccoBluetoothClient."""
    client = LaMarzoccoBluetoothClient(
        address_or_ble_device="00:00:00:00:00:00",
        ble_token="test_token",
    )
    return client


SETTINGS_CHAR = "0b0b7847-e12b-09a8-b04b-8e0922a9abab"
AUTH_CHAR = "0d0b7847-e12b-09a8-b04b-8e0922a9abab"
READ_CHAR = "0a0b7847-e12b-09a8-b04b-8e0922a9abab"


async def test_ble_set_power(
    mock_bleak_client: MagicMock,
    lm_bluetooth_client: LaMarzoccoBluetoothClient,
) -> None:
    """Test setting power on the machine."""
    await lm_bluetooth_client.set_power(mock_bleak_client, True)
    mock_bleak_client.services.get_characteristic.assert_called_once_with(SETTINGS_CHAR)
    mock_bleak_client.write_gatt_char.assert_called_once_with(
        char_specifier="mock_characteristic",
        data=b'{"name":"MachineChangeMode","parameter":{"mode":"BrewingMode"}}\x00',
        response=True,
    )


async def test_ble_set_temperature(
    mock_bleak_client: MagicMock,
    lm_bluetooth_client: LaMarzoccoBluetoothClient,
) -> None:
    """Test setting temperature on the machine."""
    await lm_bluetooth_client.set_temp(mock_bleak_client, BoilerType.STEAM, 90)
    mock_bleak_client.services.get_characteristic.assert_called_once_with(SETTINGS_CHAR)
    mock_bleak_client.write_gatt_char.assert_called_once_with(
        char_specifier="mock_characteristic",
        data=b'{"name":"SettingBoilerTarget","parameter":{"identifier":"SteamBoiler","value":90}}\x00',
        response=True,
    )


async def test_ble_set_smart_standby(
    mock_bleak_client: MagicMock,
    lm_bluetooth_client: LaMarzoccoBluetoothClient,
) -> None:
    """Test setting smart standby on the machine."""
    await lm_bluetooth_client.set_smart_standby(
        mock_bleak_client, True, SmartStandByType.POWER_ON, 42
    )
    mock_bleak_client.services.get_characteristic.assert_called_once_with(SETTINGS_CHAR)
    mock_bleak_client.write_gatt_char.assert_called_once_with(
        char_specifier="mock_characteristic",
        data=b'{"name":"SettingSmartStandby","parameter":{"minutes":42,"mode":"PowerOn","enabled":true}}\x00',
        response=True,
    )


async def test_ble_authenticate(
    mock_bleak_client: MagicMock,
    lm_bluetooth_client: LaMarzoccoBluetoothClient,
) -> None:
    """Test authenticating the machine."""
    await lm_bluetooth_client.authenticate(mock_bleak_client)
    mock_bleak_client.services.get_characteristic.assert_called_once_with(AUTH_CHAR)
    mock_bleak_client.write_gatt_char.assert_called_once_with(
        char_specifier="mock_characteristic", data=b"test_token", response=True
    )


async def test_ble_get_machine_capability(
    mock_bleak_client: MagicMock,
    lm_bluetooth_client: LaMarzoccoBluetoothClient,
) -> None:
    """Test getting machine capability."""
    mock_bleak_client.read_gatt_char.return_value = b'[{"family":"MICRA","groupsNumber":1,"coffeeBoilersNumber":1,"hasCupWarmer":false,"steamBoilersNumber":1,"teaDosesNumber":0,"machineModes":["BrewingMode","StandBy"],"schedulingType":"smartWakeUpSleep"}]'
    response = await lm_bluetooth_client.get_machine_capabilities(mock_bleak_client)
    mock_bleak_client.services.get_characteristic.assert_called_with(READ_CHAR)
    mock_bleak_client.write_gatt_char.assert_called_once_with(
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


async def test_ble_get_boiler_details(
    mock_bleak_client: MagicMock,
    lm_bluetooth_client: LaMarzoccoBluetoothClient,
) -> None:
    """Test getting boiler details."""
    mock_bleak_client.read_gatt_char.return_value = b'[{"id":"SteamBoiler","isEnabled":true,"target":131,"current":45},{"id":"CoffeeBoiler1","isEnabled":true,"target":94,"current":65}]'
    response = await lm_bluetooth_client.get_boilers(mock_bleak_client)
    mock_bleak_client.services.get_characteristic.assert_called_with(READ_CHAR)
    mock_bleak_client.write_gatt_char.assert_called_once_with(
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


async def test_ble_get_smart_standby_details(
    mock_bleak_client: MagicMock,
    lm_bluetooth_client: LaMarzoccoBluetoothClient,
) -> None:
    """Test getting smart standby details."""
    mock_bleak_client.read_gatt_char.return_value = (
        b'{"mode":"PowerOn","minutes":42,"enabled":"true"}'
    )
    response = await lm_bluetooth_client.get_smart_standby_settings(mock_bleak_client)
    mock_bleak_client.services.get_characteristic.assert_called_with(READ_CHAR)
    mock_bleak_client.write_gatt_char.assert_called_once_with(
        char_specifier="mock_characteristic",
        data=b"smartStandBy\x00",
        response=True,
    )
    assert response == BluetoothSmartStandbyDetails(
        mode=SmartStandByType.POWER_ON, minutes=42, enabled=True
    )


async def test_ble_get_tank_status(
    mock_bleak_client: MagicMock,
    lm_bluetooth_client: LaMarzoccoBluetoothClient,
) -> None:
    """Test getting tank status."""
    mock_bleak_client.read_gatt_char.return_value = b'"true"'
    response = await lm_bluetooth_client.get_tank_status(mock_bleak_client)
    mock_bleak_client.services.get_characteristic.assert_called_with(READ_CHAR)
    mock_bleak_client.write_gatt_char.assert_called_once_with(
        char_specifier="mock_characteristic",
        data=b"tankStatus\x00",
        response=True,
    )
    assert response is True


async def test_get_machine_mode(
    mock_bleak_client: MagicMock,
    lm_bluetooth_client: LaMarzoccoBluetoothClient,
) -> None:
    """Test getting machine mode."""
    mock_bleak_client.read_gatt_char.return_value = b'"BrewingMode"'
    response = await lm_bluetooth_client.get_machine_mode(mock_bleak_client)
    mock_bleak_client.services.get_characteristic.assert_called_with(READ_CHAR)
    mock_bleak_client.write_gatt_char.assert_called_once_with(
        char_specifier="mock_characteristic",
        data=b"machineMode\x00",
        response=True,
    )
    assert response == MachineMode.BREWING_MODE
