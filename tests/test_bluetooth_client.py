"""Test the bluetooth client."""

import asyncio
import itertools
import json
import types
from collections.abc import Callable, Generator
from datetime import date, datetime, timedelta, timezone
from functools import reduce
from typing import Any, NamedTuple
from unittest.mock import AsyncMock, MagicMock, call, create_autospec, patch

import pytest
from bleak.backends.device import BLEDevice
from bleak.backends.service import BleakGATTServiceCollection
from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

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

from .conftest import FIXTURES_DIR

# Duplicates of the library's UUIDs on purpose, to pin the machine's protocol.
SETTINGS_CHAR = "0b0b7847-e12b-09a8-b04b-8e0922a9abab"
AUTH_CHAR = "0d0b7847-e12b-09a8-b04b-8e0922a9abab"
READ_CHAR = "0a0b7847-e12b-09a8-b04b-8e0922a9abab"
SHOT_COUNTER_CHAR = "0e0b7847-e12b-09a8-b04b-8e0922a9abab"

COMMAND_SUCCESS = b'{"id":"test-id","message":"Success","status":"success"}'
STARTED = b'{"BrewingStartedGroup1DoseIndex":"DoseA"}'


def _tick(time: float, backflush: bool = False) -> bytes:
    """Return a timer notification of a running shot."""
    return json.dumps(
        {
            "BrewingUpdateGroup1Time": time,
            "BrewingUpdateGroup1Ev": True,
            "BrewingUpdateGroup1Backflush": backflush,
        }
    ).encode()


async def _wait_for(condition: Callable[[], bool]) -> None:
    """Let the background tasks run until the condition holds."""
    for _ in range(100):
        if condition():
            return
        await asyncio.sleep(0)
    pytest.fail("Condition not met while running the background tasks")


def _no_background_tasks() -> bool:
    """Return whether all tasks besides the test itself are done."""
    return asyncio.all_tasks() == {asyncio.current_task()}


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


class IdleTimer:
    """The client's idle disconnect timer, expiring only when a test fires it."""

    # used as IDLE_TIMEOUT, no other sleep of the client has this delay
    TIMEOUT = 4321.0

    def __init__(self) -> None:
        self.started = 0
        self._timers: list[asyncio.Future[None]] = []

    @property
    def pending(self) -> int:
        """Return the number of running idle timers."""
        return sum(not timer.done() for timer in self._timers)

    async def fire(self) -> None:
        """Expire the running idle timer."""
        await _wait_for(lambda: self.pending > 0)
        for timer in self._timers:
            if not timer.done():
                timer.set_result(None)

    async def sleep(self, delay: float, result: Any = None) -> Any:
        """Block idle timeouts until fired, sleep for everything else."""
        if delay != self.TIMEOUT:
            return await asyncio.sleep(delay, result)
        self.started += 1
        timer = asyncio.get_running_loop().create_future()
        self._timers.append(timer)
        await timer
        return result


@pytest.fixture(name="idle_timer", autouse=True)
def idle_timer_fixture() -> Generator[IdleTimer]:
    """Let tests fire the idle timer instead of waiting for it.

    Only the client module sees the patched asyncio.sleep.
    """
    idle_timer = IdleTimer()
    client_asyncio = types.ModuleType("asyncio")
    vars(client_asyncio).update(vars(asyncio), sleep=idle_timer.sleep)
    with (
        patch("pylamarzocco.clients._bluetooth.asyncio", client_asyncio),
        patch("pylamarzocco.clients._bluetooth.IDLE_TIMEOUT", IdleTimer.TIMEOUT),
    ):
        yield idle_timer


class FakeBleakClient:
    """A machine behind a fake BleakClientWithServiceCache.

    The client methods are AsyncMocks spec'd on the real class, so calls are
    checked against the real signatures and can be asserted, while they act on
    the explicit state of the machine below.
    """

    def __init__(self) -> None:
        self.is_connected = False
        # the token the machine accepts, and the reads until it confirms it
        self.token = "token"
        self.auth_confirm_reads = 1
        # value read from each characteristic
        self.values: dict[str, bytes] = {SETTINGS_CHAR: COMMAND_SUCCESS}
        # characteristics the machine lacks, or that the cached services lack
        self.missing: set[str] = set()
        self.uncached: set[str] = set()
        # the last notification, which the machine replays on subscribe
        self.replay: bytes | None = _tick(3.34)
        # errors raised by the next connection attempts
        self.connect_errors: list[Exception] = []
        self.writes: list[tuple[str, bytes]] = []
        self.subscribed: str | None = None

        self._from_cache = True
        self._authenticated = False
        self._auth_reads = 0
        self._disconnected_callback: Callable[[Any], None] | None = None
        self._notification_handler: Callable[[Any, bytearray], None] | None = None

        spec = create_autospec(BleakClientWithServiceCache, instance=True)
        self.write_gatt_char = spec.write_gatt_char
        self.write_gatt_char.side_effect = self._write_gatt_char
        self.read_gatt_char = spec.read_gatt_char
        self.read_gatt_char.side_effect = self._read_gatt_char
        self.start_notify = spec.start_notify
        self.start_notify.side_effect = self._start_notify
        self.stop_notify = spec.stop_notify
        self.stop_notify.side_effect = self._stop_notify
        self.disconnect = spec.disconnect
        self.disconnect.side_effect = self._disconnect
        self.clear_cache = spec.clear_cache
        self.services = create_autospec(BleakGATTServiceCollection, instance=True)
        self.services.get_characteristic.side_effect = self._get_characteristic
        self.establish_connection = create_autospec(
            establish_connection, side_effect=self._establish_connection
        )

    def notify(self, payload: bytes) -> None:
        """Send a notification to the subscribed handler."""
        assert self._notification_handler is not None, "nothing is subscribed"
        self._notification_handler(self.subscribed, bytearray(payload))

    def drop_connection(self) -> None:
        """Lose the connection, like when the machine goes out of range."""
        assert self._disconnected_callback is not None
        self.is_connected = False
        self.subscribed = self._notification_handler = None
        self._disconnected_callback(self)

    def _establish_connection(
        self,
        client_class: type,
        *_: Any,
        disconnected_callback: Callable[[Any], None] | None = None,
        use_services_cache: bool = True,
        **__: Any,
    ) -> "FakeBleakClient":
        assert client_class is BleakClientWithServiceCache
        if self.connect_errors:
            raise self.connect_errors.pop(0)
        self.is_connected = True
        self._from_cache = use_services_cache
        self._authenticated = False
        self._disconnected_callback = disconnected_callback
        return self

    def _check_connected(self) -> None:
        if not self.is_connected:
            raise BleakError("Not connected")

    def _get_characteristic(self, specifier: str) -> str | None:
        if specifier in self.missing or (
            self._from_cache and specifier in self.uncached
        ):
            return None
        return specifier

    def _write_gatt_char(self, char_specifier: str, data: bytes, **_: Any) -> None:
        self._check_connected()
        self.writes.append((char_specifier, bytes(data)))
        if char_specifier == AUTH_CHAR:
            self._authenticated = bytes(data) == self.token.encode()
            self._auth_reads = 0

    def _read_gatt_char(self, char_specifier: str, **_: Any) -> bytearray:
        self._check_connected()
        if char_specifier != AUTH_CHAR:
            return bytearray(self.values[char_specifier])
        self._auth_reads += 1
        confirmed = (
            self._authenticated and self._auth_reads >= self.auth_confirm_reads
        )
        return bytearray(b"\x01" if confirmed else b"\x00")

    def _start_notify(
        self,
        char_specifier: str,
        callback: Callable[[Any, bytearray], None],
        **_: Any,
    ) -> None:
        self._check_connected()
        self.subscribed = char_specifier
        self._notification_handler = callback
        if self.replay is not None:
            callback(char_specifier, bytearray(self.replay))

    def _stop_notify(self, _char_specifier: str) -> None:
        self.subscribed = self._notification_handler = None

    async def _disconnect(self) -> None:
        # like bleak, yield and report the disconnect to the callback
        await asyncio.sleep(0)
        self.drop_connection()


@pytest.fixture(name="bleak_client", autouse=True)
def bleak_client_fixture() -> Generator[FakeBleakClient]:
    """Connect the clients to a fake machine."""
    bleak_client = FakeBleakClient()
    with patch(
        "pylamarzocco.clients._bluetooth.establish_connection",
        bleak_client.establish_connection,
    ):
        yield bleak_client


async def test_ble_set_power(
    bleak_client: FakeBleakClient, ble_device: BLEDevice
) -> None:
    """Test setting power on the machine."""
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    await client.set_power(True)

    bleak_client.write_gatt_char.assert_awaited_with(
        char_specifier=SETTINGS_CHAR,
        data=b'{"name":"MachineChangeMode","parameter":{"mode":"BrewingMode"}}\x00',
        response=True,
    )
    await client.disconnect()


async def test_ble_set_temperature(
    bleak_client: FakeBleakClient, ble_device: BLEDevice
) -> None:
    """Test setting temperature on the machine."""
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    await client.set_temp(BoilerType.STEAM, 90)

    assert bleak_client.writes[-1] == (
        SETTINGS_CHAR,
        b'{"name":"SettingBoilerTarget","parameter":{"identifier":"SteamBoiler","value":90}}\x00',
    )
    await client.disconnect()


async def test_ble_set_smart_standby(
    bleak_client: FakeBleakClient, ble_device: BLEDevice
) -> None:
    """Test setting smart standby on the machine."""
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    await client.set_smart_standby(True, SmartStandByType.POWER_ON, 42)

    assert bleak_client.writes[-1] == (
        SETTINGS_CHAR,
        b'{"name":"SettingSmartStandby","parameter":{"minutes":42,"mode":"PowerOn","enabled":true}}\x00',
    )
    await client.disconnect()


async def test_ble_get_machine_capability(
    bleak_client: FakeBleakClient, ble_device: BLEDevice
) -> None:
    """Test getting machine capability."""
    bleak_client.values[READ_CHAR] = b'[{"family":"MICRA","groupsNumber":1,"coffeeBoilersNumber":1,"hasCupWarmer":false,"steamBoilersNumber":1,"teaDosesNumber":0,"machineModes":["BrewingMode","StandBy"],"schedulingType":"smartWakeUpSleep"}]'

    client = LaMarzoccoBluetoothClient(ble_device, "token")
    response = await client.get_machine_capabilities()

    assert bleak_client.writes[-1] == (READ_CHAR, b"machineCapabilities\x00")
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
    bleak_client: FakeBleakClient, ble_device: BLEDevice
) -> None:
    """Test getting boiler details."""
    bleak_client.values[READ_CHAR] = b'[{"id":"SteamBoiler","isEnabled":true,"target":131,"current":45},{"id":"CoffeeBoiler1","isEnabled":true,"target":94,"current":65}]'

    client = LaMarzoccoBluetoothClient(ble_device, "token")
    response = await client.get_boilers()

    assert bleak_client.writes[-1] == (READ_CHAR, b"boilers\x00")
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
    bleak_client: FakeBleakClient, ble_device: BLEDevice
) -> None:
    """Test getting smart standby details."""
    bleak_client.values[READ_CHAR] = (
        b'{"mode":"PowerOn","minutes":42,"enabled":"true"}'
    )

    client = LaMarzoccoBluetoothClient(ble_device, "token")
    response = await client.get_smart_standby_settings()

    assert bleak_client.writes[-1] == (READ_CHAR, b"smartStandBy\x00")
    assert response == BluetoothSmartStandbyDetails(
        mode=SmartStandByType.POWER_ON, minutes=42, enabled=True
    )
    await client.disconnect()


async def test_ble_get_tank_status(
    bleak_client: FakeBleakClient, ble_device: BLEDevice
) -> None:
    """Test getting tank status."""
    bleak_client.values[READ_CHAR] = b'"true"'

    client = LaMarzoccoBluetoothClient(ble_device, "token")
    response = await client.get_tank_status()

    assert bleak_client.writes[-1] == (READ_CHAR, b"tankStatus\x00")
    assert response is True
    await client.disconnect()


async def test_get_machine_mode(
    bleak_client: FakeBleakClient, ble_device: BLEDevice
) -> None:
    """Test getting machine mode."""
    bleak_client.values[READ_CHAR] = b'"BrewingMode"'

    client = LaMarzoccoBluetoothClient(ble_device, "token")
    response = await client.get_machine_mode()

    assert bleak_client.writes[-1] == (READ_CHAR, b"machineMode\x00")
    assert response == MachineMode.BREWING_MODE
    await client.disconnect()


async def test_persistent_connection_auto_connect(
    bleak_client: FakeBleakClient, ble_device: BLEDevice
) -> None:
    """Test that connection is established automatically on first command."""
    client = LaMarzoccoBluetoothClient(ble_device, "token")

    # Connection should not be established yet
    assert not client.is_connected

    # First command should trigger connection
    await client.set_power(True)

    # Connection should now be established and authenticated
    bleak_client.establish_connection.assert_awaited_once()
    assert bleak_client.writes[0] == (AUTH_CHAR, b"token")

    # Cleanup
    await client.disconnect()


async def test_persistent_connection_reuse(
    bleak_client: FakeBleakClient, ble_device: BLEDevice
) -> None:
    """Test that connection is reused for multiple commands."""
    client = LaMarzoccoBluetoothClient(ble_device, "token")

    # Execute multiple commands
    await client.set_power(True)
    await client.set_power(False)
    await client.set_steam(True)

    # Connection should only be established once
    bleak_client.establish_connection.assert_awaited_once()

    # Connection should still be active
    assert client.is_connected

    # Cleanup
    await client.disconnect()


async def test_auto_disconnect_after_idle(
    bleak_client: FakeBleakClient, ble_device: BLEDevice, idle_timer: IdleTimer
) -> None:
    """Test that connection is automatically disconnected after idle timeout."""
    client = LaMarzoccoBluetoothClient(ble_device, "token")

    # Execute a command to establish connection
    await client.set_power(True)
    assert client.is_connected

    await idle_timer.fire()
    await _wait_for(lambda: not bleak_client.is_connected)

    # Connection should be closed
    assert not client.is_connected
    bleak_client.disconnect.assert_awaited_once()


async def test_timer_reset_on_new_command(
    ble_device: BLEDevice, idle_timer: IdleTimer
) -> None:
    """Test that disconnect timer is reset when a new command is issued."""
    client = LaMarzoccoBluetoothClient(ble_device, "token")

    # Execute a command
    await client.set_power(True)
    await _wait_for(lambda: idle_timer.pending == 1)

    # Execute another command, which restarts the timer
    await client.set_steam(True)
    await _wait_for(lambda: idle_timer.started == 2)
    assert idle_timer.pending == 1
    assert client.is_connected

    await idle_timer.fire()
    await _wait_for(lambda: not client.is_connected)

    # Cleanup
    await client.disconnect()


async def test_concurrent_commands_thread_safe(
    bleak_client: FakeBleakClient, ble_device: BLEDevice
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
    bleak_client.establish_connection.assert_awaited_once()

    # All commands should have executed
    assert [char for char, _ in bleak_client.writes] == [
        AUTH_CHAR,
        SETTINGS_CHAR,
        SETTINGS_CHAR,
        SETTINGS_CHAR,
    ]

    # Cleanup
    await client.disconnect()


async def test_exception_triggers_disconnect(
    bleak_client: FakeBleakClient, ble_device: BLEDevice
) -> None:
    """Test that an exception during command execution triggers disconnect."""
    client = LaMarzoccoBluetoothClient(ble_device, "token")

    # First command succeeds to establish connection
    await client.set_power(True)
    assert client.is_connected

    # Make subsequent write fail
    bleak_client.write_gatt_char.side_effect = BleakError("Connection failed")

    # Command should fail and trigger disconnect
    with pytest.raises(BleakError):
        await client.set_power(False)

    await _wait_for(lambda: not bleak_client.is_connected)
    assert not client.is_connected


async def test_characteristic_resolution_failure_clears_cache(
    bleak_client: FakeBleakClient, ble_device: BLEDevice
) -> None:
    """Test that failing to resolve characteristic clears cache and disconnects."""
    client = LaMarzoccoBluetoothClient(ble_device, "token")

    # Make characteristic resolution fail
    bleak_client.missing.add(SETTINGS_CHAR)

    # Command should fail
    with pytest.raises(BluetoothConnectionFailed):
        await client.set_power(True)

    # Cache should be cleared and disconnected
    bleak_client.clear_cache.assert_awaited()
    await _wait_for(lambda: not bleak_client.is_connected)
    assert not client.is_connected


async def test_is_connected_property(ble_device: BLEDevice) -> None:
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


async def test_reconnect_after_disconnect(ble_device: BLEDevice) -> None:
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


async def test_auth_read_back_failure(
    bleak_client: FakeBleakClient, ble_device: BLEDevice
) -> None:
    """Test authentication fails if the machine never confirms with 0x01."""
    bleak_client.token = "other"
    client = LaMarzoccoBluetoothClient(ble_device, "token")

    with (
        patch("pylamarzocco.clients._bluetooth.AUTH_READ_INTERVAL", 0),
        pytest.raises(BluetoothConnectionFailed, match="authentication failed"),
    ):
        await client.set_power(True)

    assert bleak_client.read_gatt_char.await_count == 10
    assert not client.is_connected
    assert not bleak_client.is_connected
    bleak_client.disconnect.assert_awaited_once()


async def test_auth_read_back_retries_until_confirmed(
    bleak_client: FakeBleakClient, ble_device: BLEDevice
) -> None:
    """Test authentication succeeds once the machine returns 0x01."""
    bleak_client.auth_confirm_reads = 3
    client = LaMarzoccoBluetoothClient(ble_device, "token")

    with patch("pylamarzocco.clients._bluetooth.AUTH_READ_INTERVAL", 0):
        await client.set_power(True)

    # 3 authentication reads and the command status
    assert bleak_client.read_gatt_char.await_count == 4
    assert client.is_connected
    await client.disconnect()


async def test_start_shot_counter_characteristic_missing(
    bleak_client: FakeBleakClient, ble_device: BLEDevice, idle_timer: IdleTimer
) -> None:
    """Test the shot counter is not started if rediscovery doesn't find it."""
    bleak_client.missing.add(SHOT_COUNTER_CHAR)
    client = LaMarzoccoBluetoothClient(ble_device, "token")

    assert await client.start_shot_counter(MagicMock()) is False

    bleak_client.start_notify.assert_not_awaited()
    # only the cached services are cleared, before rediscovering them once
    bleak_client.clear_cache.assert_awaited_once()
    bleak_client.disconnect.assert_awaited_once()
    assert [
        connect.kwargs["use_services_cache"]
        for connect in bleak_client.establish_connection.call_args_list
    ] == [True, False]
    assert client.is_connected
    assert not client.shot_counter_active

    # the idle disconnect is running again
    await idle_timer.fire()
    await _wait_for(lambda: not client.is_connected)


async def test_start_shot_counter_rediscovers_services(
    bleak_client: FakeBleakClient, ble_device: BLEDevice
) -> None:
    """Test a characteristic missing from stale cached services is found again."""
    bleak_client.uncached.add(SHOT_COUNTER_CHAR)
    connection_callback = MagicMock()
    client = LaMarzoccoBluetoothClient(ble_device, "token")

    assert await client.start_shot_counter(MagicMock(), connection_callback) is True

    bleak_client.clear_cache.assert_awaited_once()
    bleak_client.disconnect.assert_awaited_once()
    assert (
        bleak_client.establish_connection.call_args.kwargs["use_services_cache"]
        is False
    )
    bleak_client.start_notify.assert_awaited_once()
    assert client.shot_counter_active
    connection_callback.assert_called_once_with(True)
    await client.disconnect()


async def test_start_shot_counter(
    bleak_client: FakeBleakClient, ble_device: BLEDevice
) -> None:
    """Test subscribing to the shot counter."""
    connection_callback = MagicMock()
    client = LaMarzoccoBluetoothClient(ble_device, "token")

    assert await client.start_shot_counter(MagicMock(), connection_callback) is True

    bleak_client.start_notify.assert_awaited_once()
    assert bleak_client.subscribed == SHOT_COUNTER_CHAR
    assert client.shot_counter_active
    connection_callback.assert_called_once_with(True)

    await client.disconnect()
    bleak_client.stop_notify.assert_awaited_once_with(SHOT_COUNTER_CHAR)
    assert bleak_client.subscribed is None
    assert not client.shot_counter_active


async def test_shot_counter_suppresses_auto_disconnect(
    bleak_client: FakeBleakClient, ble_device: BLEDevice, idle_timer: IdleTimer
) -> None:
    """Test the idle disconnect is suppressed while the shot counter runs."""
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    await client.start_shot_counter(MagicMock())
    await client.set_power(True)

    # no idle timer is running
    await _wait_for(_no_background_tasks)
    assert idle_timer.started == 0
    assert client.is_connected

    # stopping the shot counter resumes the idle disconnect
    await client.stop_shot_counter()
    bleak_client.stop_notify.assert_awaited_once()
    await idle_timer.fire()
    await _wait_for(lambda: not client.is_connected)
    bleak_client.disconnect.assert_awaited_once()


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
    bleak_client: FakeBleakClient,
    ble_device: BLEDevice,
    steps: list[tuple[bytes, tuple[BluetoothBrewingState, float | None, float | None] | None]],
) -> None:
    """Test the shot counter state machine, other messages never repeat a state."""
    callback = MagicMock()
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    assert await client.start_shot_counter(callback)

    for payload, expected in steps:
        callback.reset_mock()
        bleak_client.notify(payload)
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
    "replay_during_subscribe",
    [
        pytest.param(True, id="during_subscribe"),
        # proxies may deliver it after subscribing
        pytest.param(False, id="after_subscribe"),
    ],
)
async def test_shot_counter_discards_replay(
    bleak_client: FakeBleakClient,
    ble_device: BLEDevice,
    replay_during_subscribe: bool,
) -> None:
    """Test the replay of the machine's last notification on subscribe is dropped."""
    callback = MagicMock()
    telemetry_callback = MagicMock()
    bleak_client.replay = REPLAY if replay_during_subscribe else None
    client = LaMarzoccoBluetoothClient(ble_device, "token")

    await client.start_shot_counter(callback, telemetry_callback=telemetry_callback)
    if not replay_during_subscribe:
        bleak_client.notify(REPLAY)

    callback.assert_not_called()
    telemetry_callback.assert_not_called()

    # only the first notification is dropped
    bleak_client.notify(REPLAY)
    telemetry_callback.assert_called_once_with(
        BluetoothMachineTelemetry(machine_mode=MachineMode.STANDBY)
    )
    await client.disconnect()


async def test_shot_counter_telemetry(
    bleak_client: FakeBleakClient, ble_device: BLEDevice
) -> None:
    """Test telemetry is passed on without touching the brewing state."""
    callback = MagicMock()
    telemetry_callback = MagicMock()
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    assert await client.start_shot_counter(
        callback, telemetry_callback=telemetry_callback
    )

    bleak_client.notify(b'{"CoffeeBoiler1UpdateTemperature":95}')
    telemetry_callback.assert_called_once_with(
        BluetoothMachineTelemetry(coffee_boiler_temperature=95)
    )
    # values the library doesn't know are ignored
    telemetry_callback.reset_mock()
    bleak_client.notify(b'{"SteamBoilerHeatingCoeff":"[{\\"temperature\\":18}]"}')
    bleak_client.notify(b'{"MachineMode":"Unknown"}')
    telemetry_callback.assert_not_called()

    bleak_client.notify(b'{"MachineStatistics":"{\\"tot_doses\\":2123}"}')
    telemetry_callback.assert_called_once_with(
        BluetoothMachineTelemetry(machine_statistics={"tot_doses": 2123})
    )

    # a notification with both kinds of data
    telemetry_callback.reset_mock()
    bleak_client.notify(
        b'{"BrewingStartedGroup1DoseIndex":"DoseA","SteamBoilerUpdateTemperature":127}'
    )
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
    for line in (FIXTURES_DIR / "machine" / file_name).read_text().splitlines():
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
    bleak_client: FakeBleakClient, ble_device: BLEDevice, clock: FakeClock
) -> None:
    """Test the brewing states and telemetry of a recorded morning."""
    updates: list[BluetoothShotCounterUpdate] = []
    telemetry: list[BluetoothMachineTelemetry] = []
    client = LaMarzoccoBluetoothClient(ble_device, "token")

    for session in _load_sessions("shot_counter_2026-10-05.txt", date(2026, 10, 5)):
        clock.now, bleak_client.replay = session.replay
        assert await client.start_shot_counter(
            updates.append, telemetry_callback=telemetry.append
        )
        for received_at, payload in session.notifications:
            clock.now = received_at
            bleak_client.notify(payload)
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
    await client.disconnect()


async def test_shot_counter_brewing_start_time(
    bleak_client: FakeBleakClient, ble_device: BLEDevice, clock: FakeClock
) -> None:
    """Test the brewing start time is the earliest estimate of the running shot."""
    callback = MagicMock()
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    assert await client.start_shot_counter(callback)

    started_at = clock.now
    bleak_client.notify(STARTED)
    assert callback.call_args.args[0].brewing_start_time == started_at

    # a late tick doesn't move the start
    clock.tick(5.07)
    bleak_client.notify(_tick(5))
    update: BluetoothShotCounterUpdate = callback.call_args.args[0]
    assert update.timer_value == 5
    assert update.brewing_start_time == started_at
    assert update.started_dose_index == "DoseA"

    # an earlier estimate does
    clock.tick(1)
    bleak_client.notify(_tick(6.1))
    assert callback.call_args.args[0].brewing_start_time == clock.now - timedelta(
        seconds=6.1
    )
    await client.disconnect()


async def test_shot_counter_callback_exception_is_caught(
    bleak_client: FakeBleakClient, ble_device: BLEDevice
) -> None:
    """Test exceptions in the user callback don't escape into bleak."""
    callback = MagicMock(side_effect=ValueError("boom"))
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    assert await client.start_shot_counter(callback)

    bleak_client.notify(STARTED)
    callback.assert_called_once()
    await client.disconnect()


async def test_shot_counter_reconnects_after_disconnect(
    bleak_client: FakeBleakClient, ble_device: BLEDevice
) -> None:
    """Test the shot counter resets and reconnects after a connection loss."""
    callback = MagicMock()
    connection_callback = MagicMock()
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    with patch("pylamarzocco.clients._bluetooth.RECONNECT_INITIAL_DELAY", 0):
        assert await client.start_shot_counter(callback, connection_callback)

        # the running shot must be forgotten on disconnect
        bleak_client.notify(STARTED)
        callback.reset_mock()

        bleak_client.drop_connection()
        connection_callback.assert_called_with(False)
        assert not client.shot_counter_active

        await _wait_for(lambda: client.shot_counter_active)

    assert bleak_client.establish_connection.await_count == 2
    assert bleak_client.start_notify.await_count == 2
    connection_callback.assert_called_with(True)

    # the new subscription dropped the replay again, nothing of the shot is left
    bleak_client.notify(b'{"BrewingUpdateGroup1Backflush":false}')
    callback.assert_not_called()

    await client.disconnect()


async def test_shot_counter_reconnect_retries_failed_connections(
    bleak_client: FakeBleakClient, ble_device: BLEDevice
) -> None:
    """Test the shot counter keeps reconnecting while connecting fails."""
    connection_callback = MagicMock()
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    with patch("pylamarzocco.clients._bluetooth.RECONNECT_INITIAL_DELAY", 0):
        assert await client.start_shot_counter(MagicMock(), connection_callback)
        bleak_client.connect_errors = [BleakError("out of range"), TimeoutError()]

        bleak_client.drop_connection()
        await _wait_for(lambda: client.shot_counter_active)

    # initial connection + 2 failed reconnects + the successful one
    assert bleak_client.establish_connection.await_count == 4
    assert connection_callback.call_args_list == [call(True), call(False), call(True)]
    await client.disconnect()


async def test_shot_counter_gives_up_after_auth_failures(
    bleak_client: FakeBleakClient, ble_device: BLEDevice
) -> None:
    """Test reconnecting stops after 3 consecutive auth failures."""
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    with (
        patch("pylamarzocco.clients._bluetooth.RECONNECT_INITIAL_DELAY", 0),
        patch("pylamarzocco.clients._bluetooth.AUTH_READ_INTERVAL", 0),
    ):
        await client.start_shot_counter(MagicMock())
        # the machine was paired again with another token
        bleak_client.token = "other"
        bleak_client.drop_connection()
        await _wait_for(_no_background_tasks)

    # initial connection + 3 failed reconnects
    assert bleak_client.establish_connection.await_count == 4
    assert client.authentication_failed
    assert not client.shot_counter_active
    assert not client.is_connected


async def test_shot_counter_no_reconnect_after_disconnect(
    bleak_client: FakeBleakClient, ble_device: BLEDevice
) -> None:
    """Test a user disconnect, which bleak reports as well, doesn't reconnect."""
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    with patch("pylamarzocco.clients._bluetooth.RECONNECT_INITIAL_DELAY", 0):
        await client.start_shot_counter(MagicMock())
        await client.disconnect()
        await _wait_for(_no_background_tasks)

    bleak_client.establish_connection.assert_awaited_once()
    assert not client.is_connected


async def test_start_shot_counter_twice(
    bleak_client: FakeBleakClient, ble_device: BLEDevice
) -> None:
    """Test starting the shot counter twice subscribes only once."""
    first, second = MagicMock(), MagicMock()
    client = LaMarzoccoBluetoothClient(ble_device, "token")

    assert await client.start_shot_counter(first) is True
    assert await client.start_shot_counter(second) is True

    bleak_client.start_notify.assert_awaited_once()
    bleak_client.notify(STARTED)
    first.assert_not_called()
    second.assert_called_once()
    await client.disconnect()


@pytest.mark.parametrize("stop", ["stop_shot_counter", "disconnect"])
async def test_stop_shot_counter_reentrant(
    bleak_client: FakeBleakClient, ble_device: BLEDevice, stop: str
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
    bleak_client.stop_notify.assert_awaited_once()
    await client.disconnect()


async def test_machine_stop_from_update_callback(
    bleak_client: FakeBleakClient, ble_device: BLEDevice
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
    bleak_client.stop_notify.assert_awaited_once()
    await client.disconnect()


async def test_stop_shot_counter_notifies_connection_callback(
    ble_device: BLEDevice,
) -> None:
    """Test stopping a subscribed shot counter reports it as disconnected."""
    connection_callback = MagicMock()
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    await client.start_shot_counter(MagicMock(), connection_callback)
    connection_callback.reset_mock()

    await client.disconnect()

    connection_callback.assert_called_once_with(False)


async def test_cancelled_connect_does_not_keep_unauthenticated_link(
    bleak_client: FakeBleakClient, ble_device: BLEDevice
) -> None:
    """Test cancelling during authentication drops the half-open connection."""
    auth_started = asyncio.Event()

    async def _unanswered_read(*_: Any, **__: Any) -> bytes:
        auth_started.set()
        return await asyncio.get_running_loop().create_future()

    bleak_client.read_gatt_char.side_effect = _unanswered_read
    connection_callback = MagicMock()
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    client.register_connection_callback(connection_callback)
    task = asyncio.create_task(client.get_machine_mode())
    await auth_started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert not client.is_connected
    assert not bleak_client.is_connected
    bleak_client.disconnect.assert_awaited_once()
    connection_callback.assert_not_called()


async def test_read_response_is_nul_terminated(
    bleak_client: FakeBleakClient, ble_device: BLEDevice
) -> None:
    """Test responses are cut at the first NUL byte."""
    bleak_client.values[READ_CHAR] = b'"BrewingMode"\x00\x00garbage'
    client = LaMarzoccoBluetoothClient(ble_device, "token")

    assert await client.get_machine_mode() == MachineMode.BREWING_MODE
    await client.disconnect()


@pytest.mark.parametrize(
    ("response", "expected"),
    [(b"true", True), (b"false", False), (b'"true"', True), (b'"false"', False)],
)
async def test_get_plumbed_in(
    bleak_client: FakeBleakClient,
    ble_device: BLEDevice,
    response: bytes,
    expected: bool,
) -> None:
    """Test reading the plumb-in status."""
    bleak_client.values[READ_CHAR] = response
    client = LaMarzoccoBluetoothClient(ble_device, "token")

    assert await client.get_plumbed_in() is expected
    assert bleak_client.writes[-1] == (READ_CHAR, b"isPlumbedIn\x00")
    await client.disconnect()


async def test_requests_are_atomic(
    bleak_client: FakeBleakClient, ble_device: BLEDevice
) -> None:
    """Test concurrent requests don't interleave their write/read pairs."""
    events: list[str] = []
    write = bleak_client.write_gatt_char.side_effect
    read = bleak_client.read_gatt_char.side_effect

    async def _write(**kwargs: Any) -> None:
        write(**kwargs)
        events.append(f"w:{kwargs['data'][:7]!r}")
        # let the other request run
        await asyncio.sleep(0)

    async def _read(*args: Any, **kwargs: Any) -> bytearray:
        events.append("r")
        await asyncio.sleep(0)
        return read(*args, **kwargs)

    bleak_client.write_gatt_char.side_effect = _write
    bleak_client.read_gatt_char.side_effect = _read
    bleak_client.values[READ_CHAR] = b"[]"
    client = LaMarzoccoBluetoothClient(ble_device, "token")

    await asyncio.gather(
        client.get_boilers(), client.set_temp(BoilerType.COFFEE, 93)
    )

    # every request write is directly followed by its read
    assert len(events) == 6
    assert events[1::2] == ["r"] * 3
    await client.disconnect()


async def test_command_error_keeps_shot_counter_connection(
    bleak_client: FakeBleakClient, ble_device: BLEDevice
) -> None:
    """Test a failed command doesn't drop the link while the shot counter runs."""
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    await client.start_shot_counter(MagicMock())
    bleak_client.write_gatt_char.side_effect = BleakError("write failed")

    with pytest.raises(BleakError):
        await client.set_power(True)
    await _wait_for(_no_background_tasks)

    assert client.is_connected
    assert client.shot_counter_active
    bleak_client.disconnect.assert_not_awaited()
    await client.disconnect()


async def test_authentication_failed_flag(
    bleak_client: FakeBleakClient, ble_device: BLEDevice
) -> None:
    """Test the authentication_failed flag is set and reset."""
    bleak_client.token = "other"
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    with (
        patch("pylamarzocco.clients._bluetooth.AUTH_READ_INTERVAL", 0),
        pytest.raises(BluetoothAuthenticationFailed),
    ):
        await client.set_power(True)
    assert client.authentication_failed
    await _wait_for(_no_background_tasks)

    # the machine was paired with the client's token
    bleak_client.token = "token"
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
    bleak_client: FakeBleakClient, ble_device: BLEDevice
) -> None:
    """Test the latest BLE device is used when connecting."""
    new_device = BLEDevice(address="test-address", name="Proxy", details=None)
    device_callback = MagicMock(return_value=new_device)
    client = LaMarzoccoBluetoothClient(ble_device, "token", device_callback)

    await client.set_power(True)

    args = bleak_client.establish_connection.call_args
    assert args.args[1] is new_device
    assert args.kwargs["ble_device_callback"] is device_callback
    await client.disconnect()


async def test_connection_callback_connect_and_idle_disconnect(
    bleak_client: FakeBleakClient, ble_device: BLEDevice, idle_timer: IdleTimer
) -> None:
    """Test the connection callback follows connects and idle disconnects."""
    connection_callback = MagicMock()
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    client.register_connection_callback(connection_callback)

    await client.set_power(True)
    await client.set_steam(True)
    connection_callback.assert_called_once_with(True)

    # the fake disconnect yields, the idle timer must not cancel itself
    await idle_timer.fire()
    await _wait_for(lambda: connection_callback.call_count == 2)

    assert not client.is_connected
    assert not bleak_client.is_connected
    assert connection_callback.call_args_list == [call(True), call(False)]


async def test_connection_callback_connection_lost(
    bleak_client: FakeBleakClient, ble_device: BLEDevice
) -> None:
    """Test a lost connection is reported once and a reconnect again."""
    connection_callback = MagicMock()
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    client.register_connection_callback(connection_callback)
    await client.set_power(True)

    bleak_client.drop_connection()
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
    bleak_client: FakeBleakClient, ble_device: BLEDevice
) -> None:
    """Test an unauthenticated connection is never reported as connected."""
    bleak_client.token = "other"
    connection_callback = MagicMock()
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    client.register_connection_callback(connection_callback)

    with (
        patch("pylamarzocco.clients._bluetooth.AUTH_READ_INTERVAL", 0),
        pytest.raises(BluetoothAuthenticationFailed),
    ):
        await client.set_power(True)
    await _wait_for(_no_background_tasks)

    connection_callback.assert_not_called()


async def test_connection_callback_unregister(ble_device: BLEDevice) -> None:
    """Test unregistered connection callbacks are no longer called."""
    connection_callback = MagicMock()
    client = LaMarzoccoBluetoothClient(ble_device, "token")
    unregister = client.register_connection_callback(connection_callback)

    unregister()
    unregister()
    await client.set_power(True)
    await client.disconnect()

    connection_callback.assert_not_called()
