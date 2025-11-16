"""Test the bluetooth client."""

import asyncio
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError

from pylamarzocco import LaMarzoccoBluetoothClient
from pylamarzocco.clients._bluetooth import BleakClientWithServiceCache
from pylamarzocco.const import BoilerType, MachineMode, ModelName, SmartStandByType
from pylamarzocco.exceptions import BluetoothConnectionFailed
from pylamarzocco.models import (
    BluetoothBoilerDetails,
    BluetoothMachineCapabilities,
    BluetoothSmartStandbyDetails,
)


@pytest.fixture(name="ble_device")
def ble_device_fixture() -> BLEDevice:
    """Fixture providing a fake BLE device instance."""
    return BLEDevice(
        address="test-address",
        name="Test Device",
        details=None,
    )


@pytest.fixture(name="mock_bleak_client", autouse=True)
def bleak_client() -> Generator[MagicMock, None, None]:
    """Fixture to create a mock BleakClient."""
    with patch(
        "pylamarzocco.clients._bluetooth.establish_connection",
        new_callable=AsyncMock,
    ) as mock_establish_connection:
        mock_client = MagicMock()
        mock_client.write_gatt_char = AsyncMock()
        mock_client.read_gatt_char = AsyncMock(
            return_value=b'{"id":"test-id","message":"Success","status":"success"}'
        )
        mock_client.disconnect = AsyncMock()
        mock_client.services = MagicMock()
        mock_establish_connection.return_value = mock_client
        mock_client.is_connected = True
        mock_client.services.get_characteristic.return_value = "mock_characteristic"
        mock_client.establish_mock = mock_establish_connection
        yield mock_client


SETTINGS_CHAR = "0b0b7847-e12b-09a8-b04b-8e0922a9abab"
AUTH_CHAR = "0d0b7847-e12b-09a8-b04b-8e0922a9abab"
READ_CHAR = "0a0b7847-e12b-09a8-b04b-8e0922a9abab"


async def test_ble_set_power(
    mock_bleak_client: MagicMock, ble_device: BLEDevice
) -> None:
    """Test setting power on the machine."""
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    await client.set_power(True)

    mock_bleak_client.services.get_characteristic.assert_called_with(SETTINGS_CHAR)
    mock_bleak_client.write_gatt_char.assert_called_with(
        char_specifier="mock_characteristic",
        data=b'{"name":"MachineChangeMode","parameter":{"mode":"BrewingMode"}}\x00',
        response=True,
    )
    await client.disconnect()


async def test_ble_set_temperature(
    mock_bleak_client: MagicMock, ble_device: BLEDevice
) -> None:
    """Test setting temperature on the machine."""
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    await client.set_temp(BoilerType.STEAM, 90)
    
    mock_bleak_client.services.get_characteristic.assert_called_with(SETTINGS_CHAR)
    mock_bleak_client.write_gatt_char.assert_called_with(
        char_specifier="mock_characteristic",
        data=b'{"name":"SettingBoilerTarget","parameter":{"identifier":"SteamBoiler","value":90}}\x00',
        response=True,
    )
    await client.disconnect()


async def test_ble_set_smart_standby(
    mock_bleak_client: MagicMock, ble_device: BLEDevice
) -> None:
    """Test setting smart standby on the machine."""
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    await client.set_smart_standby(True, SmartStandByType.POWER_ON, 42)
    
    mock_bleak_client.services.get_characteristic.assert_called_with(SETTINGS_CHAR)
    mock_bleak_client.write_gatt_char.assert_called_with(
        char_specifier="mock_characteristic",
        data=b'{"name":"SettingSmartStandby","parameter":{"minutes":42,"mode":"PowerOn","enabled":true}}\x00',
        response=True,
    )
    await client.disconnect()


async def test_ble_get_machine_capability(
    mock_bleak_client: MagicMock, ble_device: BLEDevice
) -> None:
    """Test getting machine capability."""
    mock_bleak_client.read_gatt_char.return_value = b'[{"family":"MICRA","groupsNumber":1,"coffeeBoilersNumber":1,"hasCupWarmer":false,"steamBoilersNumber":1,"teaDosesNumber":0,"machineModes":["BrewingMode","StandBy"],"schedulingType":"smartWakeUpSleep"}]'
    
    client = LaMarzoccoBluetoothClient(ble_device, "token")
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
    await client.disconnect()


async def test_ble_get_boiler_details(
    mock_bleak_client: MagicMock, ble_device: BLEDevice
) -> None:
    """Test getting boiler details."""
    mock_bleak_client.read_gatt_char.return_value = b'[{"id":"SteamBoiler","isEnabled":true,"target":131,"current":45},{"id":"CoffeeBoiler1","isEnabled":true,"target":94,"current":65}]'
    
    client = LaMarzoccoBluetoothClient(ble_device, "token")
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
    await client.disconnect()


async def test_ble_get_smart_standby_details(
    mock_bleak_client: MagicMock, ble_device: BLEDevice
) -> None:
    """Test getting smart standby details."""
    mock_bleak_client.read_gatt_char.return_value = (
        b'{"mode":"PowerOn","minutes":42,"enabled":"true"}'
    )
    
    client = LaMarzoccoBluetoothClient(ble_device, "token")
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
    await client.disconnect()


async def test_ble_get_tank_status(
    mock_bleak_client: MagicMock, ble_device: BLEDevice
) -> None:
    """Test getting tank status."""
    mock_bleak_client.read_gatt_char.return_value = b'"true"'
    
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    response = await client.get_tank_status()
    
    mock_bleak_client.services.get_characteristic.assert_called_with(READ_CHAR)
    mock_bleak_client.write_gatt_char.assert_called_with(
        char_specifier="mock_characteristic",
        data=b"tankStatus\x00",
        response=True,
    )
    assert response is True
    await client.disconnect()


async def test_get_machine_mode(
    mock_bleak_client: MagicMock, ble_device: BLEDevice
) -> None:
    """Test getting machine mode."""
    mock_bleak_client.read_gatt_char.return_value = b'"BrewingMode"'
    
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    response = await client.get_machine_mode()
    
    mock_bleak_client.services.get_characteristic.assert_called_with(READ_CHAR)
    mock_bleak_client.write_gatt_char.assert_called_with(
        char_specifier="mock_characteristic",
        data=b"machineMode\x00",
        response=True,
    )
    assert response == MachineMode.BREWING_MODE
    await client.disconnect()


async def test_persistent_connection_auto_connect(
    mock_bleak_client: MagicMock, ble_device: BLEDevice
) -> None:
    """Test that connection is established automatically on first command."""
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    
    # Connection should not be established yet
    assert not client.is_connected
    
    # First command should trigger connection
    await client.set_power(True)
    
    # Connection should now be established
    mock_bleak_client.establish_mock.assert_awaited_once()
    
    # Cleanup
    await client.disconnect()


async def test_persistent_connection_reuse(
    mock_bleak_client: MagicMock, ble_device: BLEDevice
) -> None:
    """Test that connection is reused for multiple commands."""
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    
    # Execute multiple commands
    await client.set_power(True)
    await client.set_power(False)
    await client.set_steam(True)
    
    # Connection should only be established once
    mock_bleak_client.establish_mock.assert_awaited_once()
    
    # Connection should still be active
    assert client.is_connected
    
    # Cleanup
    await client.disconnect()


async def test_auto_disconnect_after_idle(
    mock_bleak_client: MagicMock, ble_device: BLEDevice
) -> None:
    """Test that connection is automatically disconnected after idle timeout."""
    # Override the timeout for testing
    with patch("pylamarzocco.clients._bluetooth.IDLE_TIMEOUT", 0.1):
        client = LaMarzoccoBluetoothClient(ble_device, "token")
        
        # Execute a command to establish connection
        await client.set_power(True)
        assert client.is_connected
        
        # Wait for auto-disconnect
        await asyncio.sleep(0.2)
        
        # Connection should be closed
        assert not client.is_connected
        mock_bleak_client.disconnect.assert_awaited()


async def test_timer_reset_on_new_command(
    mock_bleak_client: MagicMock, ble_device: BLEDevice
) -> None:
    """Test that disconnect timer is reset when a new command is issued."""
    # Override the timeout for testing
    with patch("pylamarzocco.clients._bluetooth.IDLE_TIMEOUT", 0.2):
        client = LaMarzoccoBluetoothClient(ble_device, "token")
        
        # Execute a command
        await client.set_power(True)
        assert client.is_connected
        
        # Wait a bit but not long enough to disconnect
        await asyncio.sleep(0.1)
        
        # Execute another command (should reset timer)
        await client.set_steam(True)
        
        # Wait again
        await asyncio.sleep(0.1)
        
        # Connection should still be active (timer was reset)
        assert client.is_connected
        
        # Wait for disconnect
        await asyncio.sleep(0.2)
        assert not client.is_connected
        
        # Cleanup
        await client.disconnect()


async def test_concurrent_commands_thread_safe(
    mock_bleak_client: MagicMock, ble_device: BLEDevice
) -> None:
    """Test that concurrent commands are handled safely with locks."""
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    
    # Execute commands concurrently
    await asyncio.gather(
        client.set_power(True),
        client.set_steam(True),
        client.set_power(False),
    )
    
    # Connection should only be established once despite concurrent calls
    mock_bleak_client.establish_mock.assert_awaited_once()
    
    # All commands should have executed
    assert mock_bleak_client.write_gatt_char.await_count >= 3
    
    # Cleanup
    await client.disconnect()


async def test_exception_triggers_disconnect(
    mock_bleak_client: MagicMock, ble_device: BLEDevice
) -> None:
    """Test that an exception during command execution triggers disconnect."""
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    
    # First command succeeds to establish connection
    await client.set_power(True)
    assert client.is_connected
    
    # Make subsequent write fail
    mock_bleak_client.write_gatt_char.side_effect = BleakError("Connection failed")
    
    # Command should fail and trigger disconnect
    with pytest.raises(BleakError):
        await client.set_power(False)
    
    # Give time for disconnect task to complete
    await asyncio.sleep(0.05)
    
    # Disconnect should have been called
    assert not client.is_connected


async def test_characteristic_resolution_failure_clears_cache(
    mock_bleak_client: MagicMock, ble_device: BLEDevice
) -> None:
    """Test that failing to resolve characteristic clears cache and disconnects."""
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    
    # Make characteristic resolution fail
    mock_bleak_client.services.get_characteristic.return_value = None
    mock_bleak_client.clear_cache = AsyncMock()
    
    # Command should fail
    with pytest.raises(BluetoothConnectionFailed):
        await client.set_power(True)
    
    # Cache should be cleared and disconnected
    mock_bleak_client.clear_cache.assert_awaited()
    await asyncio.sleep(0.01)  # Give time for disconnect to complete
    assert not client.is_connected


async def test_is_connected_property(
    mock_bleak_client: MagicMock, ble_device: BLEDevice
) -> None:
    """Test the is_connected property."""
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    
    # Should not be connected initially
    assert not client.is_connected
    
    # Connect and check
    await client.set_power(True)
    assert client.is_connected
    
    # Disconnect and check
    await client.disconnect()
    assert not client.is_connected


async def test_reconnect_after_disconnect(
    mock_bleak_client: MagicMock, ble_device: BLEDevice
) -> None:
    """Test that client can reconnect after manual disconnect."""
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    
    # Connect and disconnect
    await client.set_power(True)
    await client.disconnect()
    assert not client.is_connected
    
    # Should be able to reconnect
    await client.set_steam(True)
    assert client.is_connected
    
    # Cleanup
    await client.disconnect()
