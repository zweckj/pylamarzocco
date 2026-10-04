"""Test the bluetooth client."""

import asyncio
from collections.abc import Generator
from datetime import timedelta
from typing import Any
from unittest.mock import DEFAULT, AsyncMock, MagicMock, call, patch

import pytest
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError

from pylamarzocco import LaMarzoccoBluetoothClient
from pylamarzocco.const import (
    BluetoothBrewingState,
    BoilerType,
    MachineMode,
    ModelName,
    SmartStandByType,
)
from pylamarzocco.exceptions import (
    BluetoothAuthenticationFailed,
    BluetoothConnectionFailed,
)
from pylamarzocco.models import (
    BluetoothBoilerDetails,
    BluetoothMachineCapabilities,
    BluetoothShotCounterUpdate,
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

        def _read_gatt_char(*_: Any, **__: Any) -> Any:
            # confirm authentication right after the token was written
            last_write = mock_client.write_gatt_char.call_args
            if last_write is not None and last_write.kwargs.get("data") == b"token":
                return b"\x01"
            return DEFAULT

        mock_client.read_gatt_char = AsyncMock(
            return_value=b'{"id":"test-id","message":"Success","status":"success"}',
            side_effect=_read_gatt_char,
        )
        mock_client.disconnect = AsyncMock()
        mock_client.start_notify = AsyncMock()
        mock_client.stop_notify = AsyncMock()
        mock_client.clear_cache = AsyncMock()
        mock_client.services = MagicMock()
        mock_establish_connection.return_value = mock_client
        mock_client.is_connected = True
        mock_client.services.get_characteristic.return_value = "mock_characteristic"
        mock_client.establish_mock = mock_establish_connection

        def _establish(*_: Any, **__: Any) -> MagicMock:
            mock_client.is_connected = True
            return mock_client

        mock_establish_connection.side_effect = _establish
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


SHOT_COUNTER_CHAR = "0e0b7847-e12b-09a8-b04b-8e0922a9abab"


async def test_auth_read_back_failure(
    mock_bleak_client: MagicMock, ble_device: BLEDevice
) -> None:
    """Test authentication fails if the machine never confirms with 0x01."""
    mock_bleak_client.read_gatt_char.side_effect = None
    mock_bleak_client.read_gatt_char.return_value = b"\x00"
    client = LaMarzoccoBluetoothClient(ble_device, "token")

    with (
        patch(
            "pylamarzocco.clients._bluetooth.asyncio.sleep", new_callable=AsyncMock
        ) as mock_sleep,
        pytest.raises(BluetoothConnectionFailed, match="authentication failed"),
    ):
        await client.set_power(True)

    assert mock_bleak_client.read_gatt_char.await_count == 10
    assert mock_sleep.await_count == 9
    mock_sleep.assert_awaited_with(0.05)
    assert not client.is_connected
    mock_bleak_client.disconnect.assert_awaited()


async def test_auth_read_back_retries_until_confirmed(
    mock_bleak_client: MagicMock, ble_device: BLEDevice
) -> None:
    """Test authentication succeeds once the machine returns 0x01."""
    mock_bleak_client.read_gatt_char.side_effect = [
        b"\x00",
        b"\x00",
        b"\x01",
        b'{"id":"test-id","message":"Success","status":"success"}',
    ]
    client = LaMarzoccoBluetoothClient(ble_device, "token")

    with patch(
        "pylamarzocco.clients._bluetooth.asyncio.sleep", new_callable=AsyncMock
    ) as mock_sleep:
        await client.set_power(True)

    assert mock_sleep.await_count == 2
    assert client.is_connected
    await client.disconnect()


async def test_start_shot_counter_characteristic_missing(
    mock_bleak_client: MagicMock, ble_device: BLEDevice
) -> None:
    """Test the shot counter is not started without the characteristic."""
    mock_bleak_client.services.get_characteristic.side_effect = lambda char: (
        None if char == SHOT_COUNTER_CHAR else "mock_characteristic"
    )
    client = LaMarzoccoBluetoothClient(ble_device, "token")

    assert await client.start_shot_counter(MagicMock()) is False

    mock_bleak_client.start_notify.assert_not_awaited()
    mock_bleak_client.disconnect.assert_not_awaited()
    assert client.is_connected
    assert not client.shot_counter_active
    # idle disconnect timer is running again
    assert client._disconnect_task is not None  # pylint: disable=protected-access
    await client.disconnect()


async def test_start_shot_counter(
    mock_bleak_client: MagicMock, ble_device: BLEDevice
) -> None:
    """Test subscribing to the shot counter."""
    mock_bleak_client.services.get_characteristic.side_effect = lambda char: char
    connection_callback = MagicMock()
    client = LaMarzoccoBluetoothClient(ble_device, "token")

    assert await client.start_shot_counter(MagicMock(), connection_callback) is True

    mock_bleak_client.start_notify.assert_awaited_once()
    assert mock_bleak_client.start_notify.call_args.args[0] == SHOT_COUNTER_CHAR
    assert client.shot_counter_active
    connection_callback.assert_called_once_with(True)

    await client.disconnect()
    mock_bleak_client.stop_notify.assert_awaited_once_with(SHOT_COUNTER_CHAR)
    assert not client.shot_counter_active


async def test_shot_counter_suppresses_auto_disconnect(
    mock_bleak_client: MagicMock, ble_device: BLEDevice
) -> None:
    """Test the idle disconnect is suppressed while the shot counter runs."""
    with patch("pylamarzocco.clients._bluetooth.IDLE_TIMEOUT", 0.05):
        client = LaMarzoccoBluetoothClient(ble_device, "token")
        await client.start_shot_counter(MagicMock())
        await client.set_power(True)

        await asyncio.sleep(0.1)
        assert client.is_connected
        mock_bleak_client.disconnect.assert_not_awaited()

        # stopping the shot counter resumes the idle disconnect
        await client.stop_shot_counter()
        mock_bleak_client.stop_notify.assert_awaited_once()
        await asyncio.sleep(0.1)
        assert not client.is_connected


@pytest.mark.parametrize(
    ("payloads", "expected"),
    [
        (
            [
                b'{"BrewingUpdateGroup1Ev":true}',
                b'{"BrewingUpdateGroup1Time":0.5}',
                b'{"BrewingUpdateGroup1Time":12.3}',
                b'{"BrewingUpdateGroup1Ev":false}',
                b'{"BrewingStoppedGroup1Time":27.4,"BrewingStoppedGroup1DoseIndex":"DoseA","BrewingStoppedGroup1StopType":"X"}',
                b'{"FlushStoppedGroup1Time":3.1}',
                b'{"BrewingUpdateGroup1Backflush":true}',
                b'{"BrewingUpdateGroup1Backflush":false,"BrewingUpdateGroup1Ev":false}',
                b'{"BrewingUpdateGroup1Ev":true,"BrewingUpdateGroup1Time":1}',
            ],
            [
                None,
                (BluetoothBrewingState.BREWING, 0.5, None),
                (BluetoothBrewingState.BREWING, 12.3, None),
                (BluetoothBrewingState.BREWING_STOPPED, None, None),
                (BluetoothBrewingState.BREWING_STOPPED, None, 27.4),
                (BluetoothBrewingState.FLUSHED, None, None),
                (BluetoothBrewingState.BACKFLUSHING, None, None),
                (BluetoothBrewingState.BREWING_STOPPED, None, None),
                (BluetoothBrewingState.BREWING, 1, None),
            ],
        ),
        (
            [
                b'{"BrewingUpdateGroup1Ev":true,"BrewingUpdateGroup1Time":2.0}\x00',
                b"not json",
                b'{"BrewingUpdateGroup1Time":"abc"}',
                b"[]",
                b"\xff\xfe",
                b'{"SomethingNew":1,"BrewingUpdateGroup1Time":3.5}',
            ],
            [
                (BluetoothBrewingState.BREWING, 2.0, None),
                (BluetoothBrewingState.BREWING, 2.0, None),
                (BluetoothBrewingState.BREWING, 2.0, None),
                (BluetoothBrewingState.BREWING, 2.0, None),
                (BluetoothBrewingState.BREWING, 2.0, None),
                (BluetoothBrewingState.BREWING, 3.5, None),
            ],
        ),
    ],
    ids=["sequence", "malformed"],
)
async def test_shot_counter_state_machine(
    mock_bleak_client: MagicMock,
    ble_device: BLEDevice,
    payloads: list[bytes],
    expected: list[tuple[BluetoothBrewingState, float | None, float | None] | None],
) -> None:
    """Test the shot counter state machine."""
    callback = MagicMock()
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    await client.start_shot_counter(callback)
    handler = mock_bleak_client.start_notify.call_args.args[1]

    for payload, expected_update in zip(payloads, expected, strict=True):
        callback.reset_mock()
        handler(MagicMock(), bytearray(payload))
        if expected_update is None:
            callback.assert_not_called()
            continue
        callback.assert_called_once()
        update: BluetoothShotCounterUpdate = callback.call_args.args[0]
        assert (
            update.state,
            update.timer_value,
            update.final_shot_time,
        ) == expected_update, payload

    await client.disconnect()


async def test_shot_counter_brewing_start_time(
    mock_bleak_client: MagicMock, ble_device: BLEDevice
) -> None:
    """Test the brewing start time is computed from the receive time."""
    callback = MagicMock()
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    await client.start_shot_counter(callback)
    handler = mock_bleak_client.start_notify.call_args.args[1]

    handler(
        MagicMock(),
        bytearray(b'{"BrewingUpdateGroup1Ev":true,"BrewingUpdateGroup1Time":5}'),
    )
    update: BluetoothShotCounterUpdate = callback.call_args.args[0]
    assert update.brewing_start_time == update.received_at - timedelta(seconds=5)
    assert update.received_at.tzinfo is not None
    await client.disconnect()


async def test_shot_counter_callback_exception_is_caught(
    mock_bleak_client: MagicMock, ble_device: BLEDevice
) -> None:
    """Test exceptions in the user callback don't escape into bleak."""
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    await client.start_shot_counter(MagicMock(side_effect=ValueError("boom")))
    handler = mock_bleak_client.start_notify.call_args.args[1]

    handler(
        MagicMock(),
        bytearray(b'{"BrewingUpdateGroup1Ev":true,"BrewingUpdateGroup1Time":5}'),
    )
    await client.disconnect()


async def test_shot_counter_reconnects_after_disconnect(
    mock_bleak_client: MagicMock, ble_device: BLEDevice
) -> None:
    """Test the shot counter resets and reconnects after a connection loss."""
    callback = MagicMock()
    connection_callback = MagicMock()
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    with patch("pylamarzocco.clients._bluetooth.RECONNECT_INITIAL_DELAY", 0):
        await client.start_shot_counter(callback, connection_callback)
        handler = mock_bleak_client.start_notify.call_args.args[1]
        disconnected_callback = mock_bleak_client.establish_mock.call_args.kwargs[
            "disconnected_callback"
        ]

        # partial data in the accumulator must be dropped on disconnect
        handler(MagicMock(), bytearray(b'{"BrewingUpdateGroup1Ev":true}'))

        mock_bleak_client.is_connected = False
        disconnected_callback(mock_bleak_client)
        connection_callback.assert_called_with(False)
        assert not client.shot_counter_active

        await asyncio.sleep(0.01)

    assert mock_bleak_client.establish_mock.await_count == 2
    assert mock_bleak_client.start_notify.await_count == 2
    connection_callback.assert_called_with(True)
    assert client.shot_counter_active

    handler = mock_bleak_client.start_notify.call_args.args[1]
    handler(MagicMock(), bytearray(b'{"BrewingUpdateGroup1Time":1}'))
    callback.assert_not_called()

    await client.disconnect()


async def test_shot_counter_gives_up_after_auth_failures(
    mock_bleak_client: MagicMock, ble_device: BLEDevice
) -> None:
    """Test reconnecting stops after 3 consecutive auth failures."""
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    with patch("pylamarzocco.clients._bluetooth.RECONNECT_INITIAL_DELAY", 0):
        await client.start_shot_counter(MagicMock())
        disconnected_callback = mock_bleak_client.establish_mock.call_args.kwargs[
            "disconnected_callback"
        ]
        mock_bleak_client.read_gatt_char.side_effect = None
        mock_bleak_client.read_gatt_char.return_value = b"\x00"
        with patch("pylamarzocco.clients._bluetooth.AUTH_READ_INTERVAL", 0):
            mock_bleak_client.is_connected = False
            disconnected_callback(mock_bleak_client)
            await asyncio.sleep(0.05)

    # initial connection + 3 failed reconnects
    assert mock_bleak_client.establish_mock.await_count == 4
    assert client._reconnect_task.done()  # pylint: disable=protected-access
    assert client.authentication_failed
    assert not client.shot_counter_active


async def test_shot_counter_no_reconnect_after_disconnect(
    mock_bleak_client: MagicMock, ble_device: BLEDevice
) -> None:
    """Test a user disconnect does not trigger a reconnect."""
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    with patch("pylamarzocco.clients._bluetooth.RECONNECT_INITIAL_DELAY", 0):
        await client.start_shot_counter(MagicMock())
        disconnected_callback = mock_bleak_client.establish_mock.call_args.kwargs[
            "disconnected_callback"
        ]
        await client.disconnect()
        disconnected_callback(mock_bleak_client)
        await asyncio.sleep(0.01)

    mock_bleak_client.establish_mock.assert_awaited_once()
    assert client._reconnect_task is None  # pylint: disable=protected-access


async def test_start_shot_counter_twice(
    mock_bleak_client: MagicMock, ble_device: BLEDevice
) -> None:
    """Test starting the shot counter twice subscribes only once."""
    first, second = MagicMock(), MagicMock()
    client = LaMarzoccoBluetoothClient(ble_device, "token")

    assert await client.start_shot_counter(first) is True
    assert await client.start_shot_counter(second) is True

    mock_bleak_client.start_notify.assert_awaited_once()
    handler = mock_bleak_client.start_notify.call_args.args[1]
    handler(
        MagicMock(),
        bytearray(b'{"BrewingUpdateGroup1Ev":true,"BrewingUpdateGroup1Time":5}'),
    )
    first.assert_not_called()
    second.assert_called_once()
    await client.disconnect()


async def test_stop_shot_counter_notifies_connection_callback(
    mock_bleak_client: MagicMock, ble_device: BLEDevice
) -> None:
    """Test stopping a subscribed shot counter reports it as disconnected."""
    connection_callback = MagicMock()
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    await client.start_shot_counter(MagicMock(), connection_callback)
    connection_callback.reset_mock()

    await client.disconnect()

    connection_callback.assert_called_once_with(False)


async def test_cancelled_connect_does_not_keep_unauthenticated_link(
    mock_bleak_client: MagicMock, ble_device: BLEDevice
) -> None:
    """Test cancelling during authentication drops the half-open connection."""
    auth_started = asyncio.Event()

    async def _slow_read(*_: Any, **__: Any) -> bytes:
        auth_started.set()
        await asyncio.sleep(10)
        return b"\x01"

    mock_bleak_client.read_gatt_char.side_effect = _slow_read
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    task = asyncio.create_task(client.get_machine_mode())
    await auth_started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert client._client is None  # pylint: disable=protected-access
    mock_bleak_client.disconnect.assert_awaited_once()


async def test_read_response_is_nul_terminated(
    mock_bleak_client: MagicMock, ble_device: BLEDevice
) -> None:
    """Test responses are cut at the first NUL byte."""
    mock_bleak_client.read_gatt_char.return_value = b'"BrewingMode"\x00\x00garbage'
    client = LaMarzoccoBluetoothClient(ble_device, "token")

    assert await client.get_machine_mode() == MachineMode.BREWING_MODE
    await client.disconnect()


@pytest.mark.parametrize(
    ("response", "expected"),
    [(b"true", True), (b"false", False), (b'"true"', True), (b'"false"', False)],
)
async def test_get_plumbed_in(
    mock_bleak_client: MagicMock,
    ble_device: BLEDevice,
    response: bytes,
    expected: bool,
) -> None:
    """Test reading the plumb-in status."""
    mock_bleak_client.read_gatt_char.return_value = response
    client = LaMarzoccoBluetoothClient(ble_device, "token")

    assert await client.get_plumbed_in() is expected
    mock_bleak_client.write_gatt_char.assert_called_with(
        char_specifier="mock_characteristic",
        data=b"isPlumbedIn\x00",
        response=True,
    )
    await client.disconnect()


async def test_requests_are_atomic(
    mock_bleak_client: MagicMock, ble_device: BLEDevice
) -> None:
    """Test concurrent requests don't interleave their write/read pairs."""
    events: list[str] = []
    last_request = b""

    async def _write(**kwargs: Any) -> None:
        nonlocal last_request
        last_request = kwargs["data"]
        events.append(f"w:{last_request[:7]!r}")
        await asyncio.sleep(0.01)

    async def _read(*_: Any) -> bytes:
        events.append("r")
        await asyncio.sleep(0.01)
        if last_request == b"token":
            return b"\x01"
        if last_request.startswith(b"boilers"):
            return b"[]"
        return b'{"id":"test-id","message":"Success","status":"success"}'

    mock_bleak_client.write_gatt_char.side_effect = _write
    mock_bleak_client.read_gatt_char.side_effect = _read
    client = LaMarzoccoBluetoothClient(ble_device, "token")

    await asyncio.gather(
        client.get_boilers(), client.set_temp(BoilerType.COFFEE, 93)
    )

    # every request write is directly followed by its read
    assert events[1::2] == ["r"] * (len(events) // 2)
    await client.disconnect()


async def test_command_error_keeps_shot_counter_connection(
    mock_bleak_client: MagicMock, ble_device: BLEDevice
) -> None:
    """Test a failed command doesn't drop the link while the shot counter runs."""
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    await client.start_shot_counter(MagicMock())
    mock_bleak_client.write_gatt_char.side_effect = BleakError("write failed")

    with pytest.raises(BleakError):
        await client.set_power(True)
    await asyncio.sleep(0.01)

    assert client.is_connected
    assert client.shot_counter_active
    mock_bleak_client.disconnect.assert_not_awaited()
    await client.disconnect()


async def test_authentication_failed_flag(
    mock_bleak_client: MagicMock, ble_device: BLEDevice
) -> None:
    """Test the authentication_failed flag is set and reset."""
    client = LaMarzoccoBluetoothClient(ble_device, "wrong")
    with (
        patch("pylamarzocco.clients._bluetooth.AUTH_READ_INTERVAL", 0),
        pytest.raises(BluetoothAuthenticationFailed),
    ):
        await client.set_power(True)
    assert client.authentication_failed

    client._ble_token = "token"  # pylint: disable=protected-access
    await client.set_power(True)
    assert not client.authentication_failed
    await client.disconnect()


async def test_discover_devices_prefixes() -> None:
    """Test discovery matches all known model name prefixes."""
    scanner = MagicMock()
    scanner.discover = AsyncMock(
        return_value=[
            BLEDevice(address=name, name=name, details=None)
            for name in ("MICRA_1", "MINI_2", "LINEA_3", "LINEAR_4", "GS3_5", "OTHER")
        ]
    )
    devices = await LaMarzoccoBluetoothClient.discover_devices(scanner)
    assert [d.name for d in devices] == [
        "MICRA_1",
        "MINI_2",
        "LINEA_3",
        "LINEAR_4",
        "GS3_5",
    ]


async def test_ble_device_callback(
    mock_bleak_client: MagicMock, ble_device: BLEDevice
) -> None:
    """Test the latest BLE device is used when connecting."""
    new_device = BLEDevice(address="test-address", name="Proxy", details=None)
    device_callback = MagicMock(return_value=new_device)
    client = LaMarzoccoBluetoothClient(ble_device, "token", device_callback)

    await client.set_power(True)

    args = mock_bleak_client.establish_mock.call_args
    assert args.args[1] is new_device
    assert args.kwargs["ble_device_callback"] is device_callback
    await client.disconnect()


async def test_missing_shot_counter_clears_service_cache(
    mock_bleak_client: MagicMock, ble_device: BLEDevice
) -> None:
    """Test a missing characteristic refreshes services on the next connect."""
    mock_bleak_client.services.get_characteristic.side_effect = lambda char: (
        None if char == SHOT_COUNTER_CHAR else "mock_characteristic"
    )
    client = LaMarzoccoBluetoothClient(ble_device, "token")

    assert await client.start_shot_counter(MagicMock()) is False
    mock_bleak_client.clear_cache.assert_awaited_once()
    await client.disconnect()


async def test_connection_callback_connect_and_idle_disconnect(
    mock_bleak_client: MagicMock, ble_device: BLEDevice
) -> None:
    """Test the connection callback follows connects and idle disconnects."""
    connection_callback = MagicMock()
    with patch("pylamarzocco.clients._bluetooth.IDLE_TIMEOUT", 0.05):
        client = LaMarzoccoBluetoothClient(ble_device, "token")
        client.register_connection_callback(connection_callback)

        await client.set_power(True)
        await client.set_steam(True)
        connection_callback.assert_called_once_with(True)

        await asyncio.sleep(0.1)

    assert not client.is_connected
    assert connection_callback.call_args_list == [call(True), call(False)]


async def test_connection_callback_connection_lost(
    mock_bleak_client: MagicMock, ble_device: BLEDevice
) -> None:
    """Test a lost connection is reported once and a reconnect again."""
    connection_callback = MagicMock()
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    client.register_connection_callback(connection_callback)
    await client.set_power(True)
    disconnected_callback = mock_bleak_client.establish_mock.call_args.kwargs[
        "disconnected_callback"
    ]

    mock_bleak_client.is_connected = False
    disconnected_callback(mock_bleak_client)
    await client.disconnect()
    assert connection_callback.call_args_list == [call(True), call(False)]

    await client.set_power(True)
    await client.disconnect()
    assert connection_callback.call_args_list == [
        call(True),
        call(False),
        call(True),
        call(False),
    ]


async def test_connection_callback_not_called_on_failed_authentication(
    mock_bleak_client: MagicMock, ble_device: BLEDevice
) -> None:
    """Test an unauthenticated connection is never reported as connected."""
    mock_bleak_client.read_gatt_char.side_effect = None
    mock_bleak_client.read_gatt_char.return_value = b"\x00"
    connection_callback = MagicMock()
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    client.register_connection_callback(connection_callback)

    with (
        patch("pylamarzocco.clients._bluetooth.AUTH_READ_INTERVAL", 0),
        pytest.raises(BluetoothAuthenticationFailed),
    ):
        await client.set_power(True)
    await asyncio.sleep(0.01)

    connection_callback.assert_not_called()


async def test_connection_callback_unregister(
    mock_bleak_client: MagicMock, ble_device: BLEDevice
) -> None:
    """Test unregistered connection callbacks are no longer called."""
    connection_callback = MagicMock()
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    unregister = client.register_connection_callback(connection_callback)

    unregister()
    unregister()
    await client.set_power(True)
    await client.disconnect()

    connection_callback.assert_not_called()
