"""Test the bluetooth client."""

import asyncio
import itertools
import json
from collections.abc import Callable, Generator
from datetime import date, datetime, timedelta, timezone
from functools import reduce
from pathlib import Path
from typing import Any, NamedTuple
from unittest.mock import DEFAULT, AsyncMock, MagicMock, call, patch

import pytest
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError

from pylamarzocco import LaMarzoccoBluetoothClient, LaMarzoccoMachine
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
    BluetoothMachineTelemetry,
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


class FakeClock:
    """Clock for the shot counter notifications."""

    def __init__(self) -> None:
        self.now = datetime(2026, 10, 5, 7, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now

    def tick(self, seconds: float) -> None:
        """Advance the clock."""
        self.now += timedelta(seconds=seconds)


@pytest.fixture(name="clock")
def clock_fixture() -> Generator[FakeClock]:
    """Patch the time the shot counter notifications are received at."""
    clock = FakeClock()
    with patch("pylamarzocco.clients._bluetooth._utcnow", clock):
        yield clock


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
STARTED = b'{"BrewingStartedGroup1DoseIndex":"DoseA"}'
FIXTURES = Path(__file__).parent / "fixtures"


def _tick(time: float, backflush: bool = False) -> bytes:
    """Return a timer notification of a running shot."""
    return json.dumps(
        {
            "BrewingUpdateGroup1Time": time,
            "BrewingUpdateGroup1Ev": True,
            "BrewingUpdateGroup1Backflush": backflush,
        }
    ).encode()


async def _start_shot_counter(
    client: LaMarzoccoBluetoothClient,
    mock_bleak_client: MagicMock,
    *args: Any,
    **kwargs: Any,
) -> Callable[[bytes], None]:
    """Start the shot counter and return a function sending it notifications."""
    assert await client.start_shot_counter(*args, **kwargs)
    handler = mock_bleak_client.start_notify.call_args.args[1]

    def notify(payload: bytes) -> None:
        handler(MagicMock(), bytearray(payload))

    # the machine first replays its last notification
    notify(_tick(3.34))
    return notify


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
    """Test the shot counter is not started if rediscovery doesn't find it."""
    mock_bleak_client.services.get_characteristic.side_effect = lambda char: (
        None if char == SHOT_COUNTER_CHAR else "mock_characteristic"
    )
    client = LaMarzoccoBluetoothClient(ble_device, "token")

    assert await client.start_shot_counter(MagicMock()) is False

    mock_bleak_client.start_notify.assert_not_awaited()
    # only the cached services are cleared, before rediscovering them once
    mock_bleak_client.clear_cache.assert_awaited_once()
    mock_bleak_client.disconnect.assert_awaited_once()
    assert [
        connect.kwargs["use_services_cache"]
        for connect in mock_bleak_client.establish_mock.call_args_list
    ] == [True, False]
    assert client.is_connected
    assert not client.shot_counter_active
    # idle disconnect timer is running again
    assert client._disconnect_task is not None  # pylint: disable=protected-access
    await client.disconnect()


async def test_start_shot_counter_rediscovers_services(
    mock_bleak_client: MagicMock, ble_device: BLEDevice
) -> None:
    """Test a characteristic missing from stale cached services is found again."""
    mock_bleak_client.services.get_characteristic.side_effect = lambda char: (
        None
        if char == SHOT_COUNTER_CHAR
        and mock_bleak_client.establish_mock.await_count < 2
        else char
    )
    connection_callback = MagicMock()
    client = LaMarzoccoBluetoothClient(ble_device, "token")

    assert await client.start_shot_counter(MagicMock(), connection_callback) is True

    mock_bleak_client.clear_cache.assert_awaited_once()
    mock_bleak_client.disconnect.assert_awaited_once()
    assert mock_bleak_client.establish_mock.call_args.kwargs["use_services_cache"] is False
    mock_bleak_client.start_notify.assert_awaited_once()
    assert client.shot_counter_active
    connection_callback.assert_called_once_with(True)
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


BREWING = BluetoothBrewingState.BREWING
BREWING_STOPPED = BluetoothBrewingState.BREWING_STOPPED
FLUSHED = BluetoothBrewingState.FLUSHED
BACKFLUSHING = BluetoothBrewingState.BACKFLUSHING


@pytest.mark.parametrize(
    "steps",
    [
        pytest.param(
            [
                (STARTED, (BREWING, 0.0, None)),
                (_tick(0.1), (BREWING, 0.1, None)),
                (_tick(1.17), (BREWING, 1.17, None)),
                (b'{"BrewingUpdateGroup1Ev":false}', (BREWING_STOPPED, None, None)),
                (
                    b'{"BrewingStoppedGroup1Time":27.4,"BrewingStoppedGroup1DoseIndex":"DoseA",'
                    b'"BrewingStoppedGroup1StopType":"X","BrewingStoppedGroup1StopReason":"Manual"}',
                    (BREWING_STOPPED, None, 27.4),
                ),
                (b'{"FlushStoppedGroup1Time":3.1}', (FLUSHED, None, None)),
                (STARTED, (BREWING, 0.0, None)),
                (_tick(0.1, backflush=True), (BACKFLUSHING, None, None)),
                (b'{"BrewingUpdateGroup1Ev":false}', (BREWING_STOPPED, None, None)),
                # without a start event, e.g. when subscribing during a shot
                (_tick(5.2), (BREWING, 5.2, None)),
            ],
            id="sequence",
        ),
        pytest.param(
            [
                (STARTED, (BREWING, 0.0, None)),
                (b"not json", None),
                (b'{"BrewingUpdateGroup1Time":"abc"}', None),
                (b"[]", None),
                (b"\xff\xfe", None),
                (b'{"SteamBoilerUpdateTemperature":130}', None),
                (b'{"SomethingNew":1,"BrewingUpdateGroup1Time":3.5}', (BREWING, 3.5, None)),
                (_tick(4.5) + b"\x00", (BREWING, 4.5, None)),
            ],
            id="malformed",
        ),
    ],
)
async def test_shot_counter_state_machine(
    mock_bleak_client: MagicMock,
    ble_device: BLEDevice,
    steps: list[tuple[bytes, tuple[BluetoothBrewingState, float | None, float | None] | None]],
) -> None:
    """Test the shot counter state machine, other messages never repeat a state."""
    callback = MagicMock()
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    notify = await _start_shot_counter(client, mock_bleak_client, callback)

    for payload, expected in steps:
        callback.reset_mock()
        notify(payload)
        if expected is None:
            callback.assert_not_called()
            continue
        callback.assert_called_once()
        update: BluetoothShotCounterUpdate = callback.call_args.args[0]
        assert (
            update.state,
            update.timer_value,
            update.final_shot_time,
        ) == expected, payload

    await client.disconnect()


REPLAY = b'{"MachineMode":"StandBy"}'


@pytest.mark.parametrize(
    ("during_subscribe", "after_subscribe"),
    [
        pytest.param([REPLAY], [], id="during_subscribe"),
        # proxies may deliver it after subscribing
        pytest.param([], [REPLAY], id="after_subscribe"),
    ],
)
async def test_shot_counter_discards_replay(
    mock_bleak_client: MagicMock,
    ble_device: BLEDevice,
    during_subscribe: list[bytes],
    after_subscribe: list[bytes],
) -> None:
    """Test the replay of the machine's last notification on subscribe is dropped."""
    callback = MagicMock()
    telemetry_callback = MagicMock()

    async def start_notify(_: Any, handler: Callable[..., None]) -> None:
        for payload in during_subscribe:
            handler(MagicMock(), bytearray(payload))

    mock_bleak_client.start_notify.side_effect = start_notify
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    await client.start_shot_counter(callback, telemetry_callback=telemetry_callback)
    handler = mock_bleak_client.start_notify.call_args.args[1]
    for payload in after_subscribe:
        handler(MagicMock(), bytearray(payload))

    callback.assert_not_called()
    telemetry_callback.assert_not_called()

    # only the first notification is dropped
    handler(MagicMock(), bytearray(REPLAY))
    telemetry_callback.assert_called_once_with(
        BluetoothMachineTelemetry(machine_mode=MachineMode.STANDBY)
    )
    await client.disconnect()


async def test_shot_counter_telemetry(
    mock_bleak_client: MagicMock, ble_device: BLEDevice
) -> None:
    """Test telemetry is passed on without touching the brewing state."""
    callback = MagicMock()
    telemetry_callback = MagicMock()
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    notify = await _start_shot_counter(
        client,
        mock_bleak_client,
        callback,
        telemetry_callback=telemetry_callback,
    )

    notify(b'{"CoffeeBoiler1UpdateTemperature":95}')
    telemetry_callback.assert_called_once_with(
        BluetoothMachineTelemetry(coffee_boiler_temperature=95)
    )
    # values the library doesn't know are ignored
    telemetry_callback.reset_mock()
    notify(b'{"SteamBoilerHeatingCoeff":"[{\\"temperature\\":18}]"}')
    notify(b'{"MachineMode":"Unknown"}')
    telemetry_callback.assert_not_called()

    notify(b'{"MachineStatistics":"{\\"tot_doses\\":2123}"}')
    telemetry_callback.assert_called_once_with(
        BluetoothMachineTelemetry(machine_statistics={"tot_doses": 2123})
    )

    # a notification with both kinds of data
    telemetry_callback.reset_mock()
    notify(b'{"BrewingStartedGroup1DoseIndex":"DoseA","SteamBoilerUpdateTemperature":127}')
    telemetry_callback.assert_called_once_with(
        BluetoothMachineTelemetry(steam_boiler_temperature=127)
    )
    callback.assert_called_once()
    assert callback.call_args.args[0].state == BREWING
    await client.disconnect()


class _Session(NamedTuple):
    """Recorded shot counter session."""

    replay: tuple[datetime, bytes]
    notifications: list[tuple[datetime, bytes]]


def _load_sessions(file_name: str, day: date) -> list[_Session]:
    """Load recorded shot counter sessions."""
    sessions: list[_Session] = []
    for line in (FIXTURES / "machine" / file_name).read_text().splitlines():
        if line.startswith("#"):
            continue
        time, payload = line.split(" ", 1)
        received_at = datetime.combine(
            day, datetime.strptime(time, "%H:%M:%S.%f").time(), timezone.utc
        )
        if payload.endswith("# replay"):
            replay = payload.removesuffix("# replay").strip().encode()
            sessions.append(_Session((received_at, replay), []))
        else:
            sessions[-1].notifications.append((received_at, payload.encode()))
    return sessions


async def test_shot_counter_recorded_sessions(
    mock_bleak_client: MagicMock, ble_device: BLEDevice, clock: FakeClock
) -> None:
    """Test the brewing states and telemetry of a recorded morning."""
    updates: list[BluetoothShotCounterUpdate] = []
    telemetry: list[BluetoothMachineTelemetry] = []
    client = LaMarzoccoBluetoothClient(ble_device, "token")

    for session in _load_sessions("shot_counter_2026-10-05.txt", date(2026, 10, 5)):

        async def start_notify(
            _: Any, handler: Callable[..., None], session: _Session = session
        ) -> None:
            clock.now, payload = session.replay
            handler(MagicMock(), bytearray(payload))

        mock_bleak_client.start_notify.side_effect = start_notify
        assert await client.start_shot_counter(
            updates.append, telemetry_callback=telemetry.append
        )
        handler = mock_bleak_client.start_notify.call_args.args[1]
        for received_at, payload in session.notifications:
            clock.now = received_at
            handler(MagicMock(), bytearray(payload))
        # the machine went to standby, which stops the shot counter
        await client.stop_shot_counter()

    assert [
        (state, len(list(group)))
        for state, group in itertools.groupby(update.state for update in updates)
    ] == [
        (BREWING, 3),
        (FLUSHED, 1),
        (BREWING, 3),
        (FLUSHED, 1),
        (BREWING, 13),
        (BREWING_STOPPED, 1),
        (BREWING, 10),
        (FLUSHED, 1),
    ]
    starts = [update for update in updates if update.timer_value == 0.0]
    assert [f"{update.received_at:%H:%M:%S.%f}"[:-3] for update in starts] == [
        "07:50:02.612",
        "07:50:09.360",
        "07:57:49.729",
        "07:59:22.007",
    ]
    # late ticks, like 0.64 s at 07:50:11.215, don't move the start time
    for update in updates:
        if update.timer_value == 0.0:
            started_at = update.received_at
        if update.brewing_start_time is not None:
            assert timedelta(0) <= started_at - update.brewing_start_time
            assert started_at - update.brewing_start_time < timedelta(seconds=0.05)

    stopped = next(update for update in updates if update.state == BREWING_STOPPED)
    assert f"{stopped.received_at:%H:%M:%S}" == "07:58:02"
    assert stopped.final_shot_time == 12.727
    assert stopped.stop_reason == "Manual"
    assert stopped.started_dose_index == "ContinuousDose"

    assert [item.machine_mode for item in telemetry if item.machine_mode] == [
        MachineMode.STANDBY,
        MachineMode.STANDBY,
    ]
    latest = reduce(BluetoothMachineTelemetry.merge, telemetry)
    assert (
        latest.coffee_boiler_temperature,
        latest.steam_boiler_temperature,
        latest.sleep,
    ) == (87, 115, "command")
    assert latest.machine_statistics is not None
    assert latest.machine_statistics["tot_doses"] == 2123


async def test_shot_counter_brewing_start_time(
    mock_bleak_client: MagicMock, ble_device: BLEDevice, clock: FakeClock
) -> None:
    """Test the brewing start time is the earliest estimate of the running shot."""
    callback = MagicMock()
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    notify = await _start_shot_counter(client, mock_bleak_client, callback)

    started_at = clock.now
    notify(STARTED)
    assert callback.call_args.args[0].brewing_start_time == started_at

    # a late tick doesn't move the start
    clock.tick(5.07)
    notify(_tick(5))
    update: BluetoothShotCounterUpdate = callback.call_args.args[0]
    assert update.timer_value == 5
    assert update.brewing_start_time == started_at
    assert update.started_dose_index == "DoseA"

    # an earlier estimate does
    clock.tick(1)
    notify(_tick(6.1))
    assert callback.call_args.args[0].brewing_start_time == clock.now - timedelta(
        seconds=6.1
    )
    await client.disconnect()


async def test_shot_counter_callback_exception_is_caught(
    mock_bleak_client: MagicMock, ble_device: BLEDevice
) -> None:
    """Test exceptions in the user callback don't escape into bleak."""
    callback = MagicMock(side_effect=ValueError("boom"))
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    notify = await _start_shot_counter(client, mock_bleak_client, callback)

    notify(STARTED)
    callback.assert_called_once()
    await client.disconnect()


async def test_shot_counter_reconnects_after_disconnect(
    mock_bleak_client: MagicMock, ble_device: BLEDevice
) -> None:
    """Test the shot counter resets and reconnects after a connection loss."""
    callback = MagicMock()
    connection_callback = MagicMock()
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    with patch("pylamarzocco.clients._bluetooth.RECONNECT_INITIAL_DELAY", 0):
        notify = await _start_shot_counter(
            client, mock_bleak_client, callback, connection_callback
        )
        disconnected_callback = mock_bleak_client.establish_mock.call_args.kwargs[
            "disconnected_callback"
        ]

        # the running shot must be forgotten on disconnect
        notify(STARTED)
        callback.reset_mock()

        mock_bleak_client.is_connected = False
        disconnected_callback(mock_bleak_client)
        connection_callback.assert_called_with(False)
        assert not client.shot_counter_active

        await asyncio.sleep(0.01)

    assert mock_bleak_client.establish_mock.await_count == 2
    assert mock_bleak_client.start_notify.await_count == 2
    connection_callback.assert_called_with(True)
    assert client.shot_counter_active

    # the new subscription drops the replay again, then nothing of the shot is left
    handler = mock_bleak_client.start_notify.call_args.args[1]
    handler(MagicMock(), bytearray(_tick(3.34)))
    handler(MagicMock(), bytearray(b'{"BrewingUpdateGroup1Backflush":false}'))
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
    assert client._reconnect_task is None  # pylint: disable=protected-access
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
    notify = await _start_shot_counter(client, mock_bleak_client, second)

    mock_bleak_client.start_notify.assert_awaited_once()
    notify(STARTED)
    first.assert_not_called()
    second.assert_called_once()
    await client.disconnect()


@pytest.mark.parametrize("stop", ["stop_shot_counter", "disconnect"])
async def test_stop_shot_counter_reentrant(
    mock_bleak_client: MagicMock, ble_device: BLEDevice, stop: str
) -> None:
    """Test stopping again from the connection callback doesn't recurse."""
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    loop = asyncio.get_running_loop()
    calls: list[bool] = []
    stops: list[asyncio.Task[None]] = []

    def connection_callback(connected: bool) -> None:
        calls.append(connected)
        if not connected:
            # like Home Assistant, in a task that runs eagerly up to its first await
            stops.append(
                asyncio.Task(
                    getattr(client, stop)(), loop=loop, eager_start=True
                )
            )

    await client.start_shot_counter(MagicMock(), connection_callback)
    await getattr(client, stop)()
    await asyncio.gather(*stops)

    assert calls == [True, False]
    assert len(stops) == 1
    assert not client.shot_counter_active
    mock_bleak_client.stop_notify.assert_awaited_once()


async def test_machine_stop_from_update_callback(
    mock_bleak_client: MagicMock, ble_device: BLEDevice
) -> None:
    """Test stopping from the update callback ends, it recursed in 2.5.1."""
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    machine = LaMarzoccoMachine("MR012345", bluetooth_client=client)
    loop = asyncio.get_running_loop()
    stops: list[asyncio.Task[None]] = []

    def update_callback(_: Any) -> None:
        # Home Assistant stopped the shot counter on every update in standby
        stops.append(
            asyncio.Task(
                machine.disconnect_bluetooth_shot_counter(), loop=loop, eager_start=True
            )
        )

    assert await machine.connect_bluetooth_shot_counter(update_callback)
    update_callback(None)
    await asyncio.gather(*stops)

    assert len(stops) == 1
    assert not client.shot_counter_active
    mock_bleak_client.stop_notify.assert_awaited_once()


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


async def test_connection_callback_connect_and_idle_disconnect(
    mock_bleak_client: MagicMock, ble_device: BLEDevice
) -> None:
    """Test the connection callback follows connects and idle disconnects."""
    connection_callback = MagicMock()

    async def disconnect() -> None:
        # a real disconnect yields, the idle timer must not cancel itself
        await asyncio.sleep(0)
        mock_bleak_client.is_connected = False

    mock_bleak_client.disconnect.side_effect = disconnect
    with patch("pylamarzocco.clients._bluetooth.IDLE_TIMEOUT", 0.05):
        client = LaMarzoccoBluetoothClient(ble_device, "token")
        client.register_connection_callback(connection_callback)

        await client.set_power(True)
        await client.set_steam(True)
        connection_callback.assert_called_once_with(True)

        await asyncio.sleep(0.1)

    assert not client.is_connected
    assert not mock_bleak_client.is_connected
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
