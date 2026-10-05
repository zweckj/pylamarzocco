"""Bluetooth class for La Marzocco machines."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import datetime, timezone
from functools import wraps
import json
import logging
from typing import Any, Callable, Concatenate, Coroutine

from bleak import BaseBleakScanner, BleakClient, BleakError, BleakScanner, BLEDevice
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from pylamarzocco.const import (
    BluetoothBrewingState,
    BluetoothReadSetting,
    BoilerType,
    MachineMode,
    SmartStandByType,
)
from pylamarzocco.exceptions import (
    BluetoothAuthenticationFailed,
    BluetoothConnectionFailed,
)
from pylamarzocco.models import (
    BluetoothBoilerDetails,
    BluetoothBrewingData,
    BluetoothCommandStatus,
    BluetoothMachineCapabilities,
    BluetoothMachineTelemetry,
    BluetoothShotCounterUpdate,
    BluetoothSmartStandbyDetails,
)

_logger = logging.getLogger(__name__)

READ_CHARACTERISTIC = "0a0b7847-e12b-09a8-b04b-8e0922a9abab"
WRITE_CHARACTERISTIC = "0b0b7847-e12b-09a8-b04b-8e0922a9abab"
GET_TOKEN_CHARACTERISTIC = "0c0b7847-e12b-09a8-b04b-8e0922a9abab"
AUTH_CHARACTERISTIC = "0d0b7847-e12b-09a8-b04b-8e0922a9abab"
SHOT_COUNTER_CHARACTERISTIC = "0e0b7847-e12b-09a8-b04b-8e0922a9abab"

BT_MODEL_PREFIXES = ("MICRA", "MINI", "LINEA", "GS3")
IDLE_TIMEOUT = 30  # seconds

AUTH_SUCCESS = b"\x01"
AUTH_READ_ATTEMPTS = 10
AUTH_READ_INTERVAL = 0.05  # seconds
MAX_AUTH_FAILURES = 3
RECONNECT_INITIAL_DELAY = 1  # seconds
RECONNECT_MAX_DELAY = 60  # seconds


def _utcnow() -> datetime:
    """Return the current time in UTC."""
    return datetime.now(timezone.utc)


def _parse_bool(value: Any) -> bool:
    """Parse a boolean that the machine may send as JSON bool or string."""
    return str(value).lower() == "true"


def _safe_call(callback: Callable[[Any], Any] | None, arg: Any) -> None:
    """Call a user callback, never letting it raise into bleak or asyncio."""
    if callback is None:
        return
    try:
        callback(arg)
    except Exception:  # pylint: disable=broad-except
        _logger.exception("Error in Bluetooth callback")


class _BrewingTracker:
    """Turn the brewing part of shot counter notifications into state updates."""

    _data: BluetoothBrewingData
    _start_time: datetime | None

    def __init__(self) -> None:
        self._reset()

    def _reset(self) -> None:
        self._data = BluetoothBrewingData()
        self._start_time = None

    def process(
        self, message: BluetoothBrewingData, received_at: datetime
    ) -> BluetoothShotCounterUpdate | None:
        """Process a notification and return the resulting state, if any."""
        if message.started_dose_index is not None:
            # a new shot or flush started
            self._reset()
        self._data = self._data.merge(message)
        update = self._data.derive_state(received_at)
        if update is None:
            _logger.debug("No brewing state could be extracted")
        elif update.state in (
            BluetoothBrewingState.FLUSHED,
            BluetoothBrewingState.BREWING_STOPPED,
        ):
            self._reset()
        elif update.brewing_start_time is not None:
            # notifications can only be delayed, so the earliest start is the best
            if self._start_time is None or update.brewing_start_time < self._start_time:
                self._start_time = update.brewing_start_time
            update.brewing_start_time = self._start_time
        return update


def disconnect_on_exception[
    T: "LaMarzoccoBluetoothClient", _R, **P
](
    func: Callable[Concatenate[T, P], Coroutine[Any, Any, _R]],
) -> Callable[Concatenate[T, P], Coroutine[Any, Any, _R]]:
    """Decorator for request/response calls: serialize them, disconnect on error."""

    @wraps(func)
    async def wrapper(
        self: T, *args: P.args, **kwargs: P.kwargs
    ) -> _R:
        try:
            # keep write -> read pairs atomic so responses can't interleave
            async with self._request_lock:
                return await func(self, *args, **kwargs)
        except (BleakError, TimeoutError, BluetoothConnectionFailed):
            # a single failed command must not kill a running shot counter
            if not (self._shot_counter_enabled and self.is_connected):
                # Disconnect on error (outside the lock to avoid deadlock)
                asyncio.create_task(self._drop_connection())
            raise

    return wrapper


class LaMarzoccoBluetoothClient:
    """Class to interact with machine via Bluetooth."""

    def __init__(
        self,
        ble_device: BLEDevice,
        ble_token: str,
        ble_device_callback: Callable[[], BLEDevice] | None = None,
    ) -> None:
        """Initializes a new bluetooth client instance.
        
        Args:
            ble_device: The BLE device to connect to
            ble_token: Authentication token for the device
            ble_device_callback: Optional callback returning the most recent
                BLEDevice (e.g. after switching adapters/proxies), used when
                (re)connecting
        """
        self._ble_token = ble_token
        self._address = ble_device.address
        self._ble_device = ble_device
        self._ble_device_callback = ble_device_callback
        self._client: BleakClientWithServiceCache | None = None
        self._lock: asyncio.Lock = asyncio.Lock()
        self._request_lock: asyncio.Lock = asyncio.Lock()
        self._authentication_failed = False
        self._disconnect_task: asyncio.Task[None] | None = None
        self._connection_callbacks: list[Callable[[bool], Any]] = []
        self._reported_connected = False

        # shot counter state
        self._shot_counter_enabled = False
        self._shot_counter_subscribed = False
        self._shot_counter_callback: (
            Callable[[BluetoothShotCounterUpdate], Any] | None
        ) = None
        self._shot_counter_connection_callback: Callable[[bool], Any] | None = None
        self._shot_counter_telemetry_callback: (
            Callable[[BluetoothMachineTelemetry], Any] | None
        ) = None
        self._brewing_tracker = _BrewingTracker()
        self._replay_pending = False
        self._reconnect_task: asyncio.Task[None] | None = None

    @property
    def is_connected(self) -> bool:
        """Return whether the client is currently connected."""
        return self._client is not None and self._client.is_connected

    def register_connection_callback(
        self, callback: Callable[[bool], Any]
    ) -> Callable[[], None]:
        """Register a callback for connection changes.

        The callback is called with True once a connection is established and
        authenticated, and with False when it is closed or lost, including
        idle disconnects.

        Returns:
            A function that unregisters the callback.
        """
        self._connection_callbacks.append(callback)

        def unregister() -> None:
            if callback in self._connection_callbacks:
                self._connection_callbacks.remove(callback)

        return unregister

    def _set_connected(self, connected: bool) -> None:
        """Notify the connection callbacks if the connection state changed."""
        if connected == self._reported_connected:
            return
        self._reported_connected = connected
        for callback in tuple(self._connection_callbacks):
            _safe_call(callback, connected)

    @property
    def authentication_failed(self) -> bool:
        """Return whether the last connection attempt was rejected by the machine.

        Usually means the Bluetooth token is wrong.
        """
        return self._authentication_failed

    @property
    def shot_counter_active(self) -> bool:
        """Return whether shot counter notifications are currently subscribed."""
        return (
            self._shot_counter_enabled
            and self._shot_counter_subscribed
            and self.is_connected
        )

    async def _ensure_connected(self, use_services_cache: bool = True) -> None:
        """Ensure we're connected to the device, connecting if necessary."""
        async with self._lock:
            if self.is_connected:
                # Reset the disconnect timer
                self._reset_disconnect_timer()
                return
            
            _logger.debug("Connecting to Bluetooth device %s", self._address)
            # a new connection never has active notifications
            self._shot_counter_subscribed = False
            try:
                if self._ble_device_callback is not None:
                    self._ble_device = self._ble_device_callback()
                self._client = await establish_connection(
                    BleakClientWithServiceCache,
                    self._ble_device,
                    self._ble_device.name or "Unknown",
                    disconnected_callback=self._on_bleak_disconnected,
                    max_attempts=3,
                    ble_device_callback=self._ble_device_callback,
                    use_services_cache=use_services_cache,
                )
                await self._authenticate()
            except BaseException as e:
                # also on cancellation: never keep an unauthenticated link
                _logger.error("Failed to connect to Bluetooth device: %r", e)
                client, self._client = self._client, None
                if client is not None and client.is_connected:
                    with suppress(Exception):
                        await client.disconnect()
                raise
            else:
                _logger.debug("Successfully connected to Bluetooth device %s", self._address)
                # Start the disconnect timer
                self._reset_disconnect_timer()
                self._set_connected(True)

    def _reset_disconnect_timer(self) -> None:
        """Reset the auto-disconnect timer."""
        if self._disconnect_task is not None:
            self._disconnect_task.cancel()
        # Keep the connection open while the shot counter is running
        self._disconnect_task = (
            None
            if self._shot_counter_enabled
            else asyncio.create_task(self._auto_disconnect())
        )

    async def _auto_disconnect(self) -> None:
        """Automatically disconnect after idle timeout."""
        try:
            await asyncio.sleep(IDLE_TIMEOUT)
        except asyncio.CancelledError:
            # Timer was reset, this is normal
            pass
        else:
            _logger.debug("Auto-disconnect timer expired, disconnecting from %s", self._address)
            await self._drop_connection()

    async def _disconnect_internal(self) -> None:
        """Internal disconnect that doesn't acquire lock (assumes lock is already held)."""
        # cancel the idle timer, unless it is the one disconnecting
        if (
            self._disconnect_task is not None
            and self._disconnect_task is not asyncio.current_task()
        ):
            self._disconnect_task.cancel()
        self._disconnect_task = None

        # detach first, so bleak doesn't report this as a lost connection
        client, self._client = self._client, None
        if client is not None and client.is_connected:
            _logger.debug("Disconnecting from Bluetooth device %s", self._address)
            try:
                await client.disconnect()
            except Exception as e:
                _logger.error("Error disconnecting from Bluetooth device: %s", e)
        self._set_connected(False)

    async def _drop_connection(self) -> None:
        """Disconnect without stopping the shot counter (it will reconnect)."""
        async with self._lock:
            await self._disconnect_internal()
        self._handle_connection_lost()

    async def disconnect(self) -> None:
        """Disconnect from the device and stop the shot counter."""
        connection_callback = self._disable_shot_counter()
        async with self._lock:
            await self._stop_notify_internal()
            await self._disconnect_internal()
        _safe_call(connection_callback, False)

    async def start_shot_counter(
        self,
        callback: Callable[[BluetoothShotCounterUpdate], Any],
        connection_callback: Callable[[bool], Any] | None = None,
        telemetry_callback: Callable[[BluetoothMachineTelemetry], Any] | None = None,
    ) -> bool:
        """Subscribe to real-time brewing notifications from the machine.

        Keeps the Bluetooth connection open (no idle disconnect) and reconnects
        automatically until `stop_shot_counter` or `disconnect` is called.

        Args:
            callback: Called with every brewing state update.
            connection_callback: Called with True when notifications are
                (re-)subscribed and with False when the connection is lost or
                the shot counter is stopped.
            telemetry_callback: Called with the live machine values, like boiler
                temperatures or the machine mode, sent with the notifications.
                Only the values of the notification are set.

        Returns:
            False if the machine does not expose the shot counter characteristic.
        """
        self._shot_counter_callback = callback
        self._shot_counter_connection_callback = connection_callback
        self._shot_counter_telemetry_callback = telemetry_callback
        self._shot_counter_enabled = True
        supported = False
        try:
            supported = await self._subscribe_shot_counter()
        finally:
            if not supported:
                self._disable_shot_counter()
                if self.is_connected:
                    self._reset_disconnect_timer()
        return supported

    async def stop_shot_counter(self) -> None:
        """Unsubscribe from brewing notifications and resume idle disconnects."""
        connection_callback = self._disable_shot_counter()
        async with self._lock:
            await self._stop_notify_internal()
            if self.is_connected:
                self._reset_disconnect_timer()
        _safe_call(connection_callback, False)

    def _disable_shot_counter(self) -> Callable[[bool], Any] | None:
        """Clear the shot counter state and stop reconnecting.

        Returns the connection callback if notifications were subscribed. Call
        it last, so a callback stopping the shot counter again is a no-op.
        """
        if not self._shot_counter_enabled:
            return None
        connection_callback = (
            self._shot_counter_connection_callback
            if self._shot_counter_subscribed
            else None
        )
        self._shot_counter_enabled = False
        self._shot_counter_callback = None
        self._shot_counter_connection_callback = None
        self._shot_counter_telemetry_callback = None
        self._brewing_tracker = _BrewingTracker()
        if self._reconnect_task is not None:
            self._reconnect_task.cancel()
            self._reconnect_task = None
        return connection_callback

    async def _stop_notify_internal(self) -> None:
        """Best-effort unsubscribe from the shot counter (lock must be held)."""
        if self._shot_counter_subscribed and self._client is not None:
            with suppress(Exception):
                await self._client.stop_notify(SHOT_COUNTER_CHARACTERISTIC)
        self._shot_counter_subscribed = False

    async def _subscribe_shot_counter(self) -> bool:
        """Connect, authenticate and subscribe to the shot counter."""
        # use the cache, then try without it if necessary
        for use_services_cache in (True, False):
            await self._ensure_connected(use_services_cache)
            async with self._lock:
                if self._client is None or not self._client.is_connected:
                    raise BluetoothConnectionFailed("Client is not connected")
                if not self._shot_counter_enabled:
                    return False
                if self._shot_counter_subscribed:
                    return True
                characteristic = self._client.services.get_characteristic(
                    SHOT_COUNTER_CHARACTERISTIC
                )
                if characteristic is None:
                    _logger.info(
                        "Shot counter characteristic not found on %s", self._address
                    )
                    if not use_services_cache:
                        return False
                    # the cached service table may be stale or incomplete
                    await self._client.clear_cache()
                    await self._disconnect_internal()
                    continue
                self._brewing_tracker = _BrewingTracker()
                # on subscribe, the machine first replays its last notification,
                # which can be hours old
                self._replay_pending = True
                await self._client.start_notify(
                    characteristic, self._handle_shot_counter_notification
                )
                self._shot_counter_subscribed = True
            _logger.debug("Subscribed to shot counter on %s", self._address)
            _safe_call(self._shot_counter_connection_callback, True)
            return True
        return False

    def _handle_shot_counter_notification(
        self, _: BleakGATTCharacteristic, data: bytearray
    ) -> None:
        """Handle a shot counter notification from the machine."""
        received_at = _utcnow()
        if self._replay_pending:
            self._replay_pending = False
            _logger.debug("Ignoring the replayed shot counter notification: %s", data)
            return
        _logger.debug("Shot counter received data: %s", data)
        try:
            payload = json.loads(bytes(data).strip(b"\x00"))
            brewing = BluetoothBrewingData.from_dict(payload)
            telemetry = BluetoothMachineTelemetry.from_dict(payload)
        except Exception as e:  # pylint: disable=broad-except
            _logger.debug("Failed to parse shot counter data %s: %s", data, e)
            return

        # most notifications are telemetry only and must not touch the brewing state
        if not brewing.is_empty:
            update = self._brewing_tracker.process(brewing, received_at)
            if update is not None:
                _safe_call(self._shot_counter_callback, update)
        if not telemetry.is_empty:
            _safe_call(self._shot_counter_telemetry_callback, telemetry)

    def _on_bleak_disconnected(self, client: BleakClient) -> None:
        """Handle a disconnect reported by bleak."""
        if client is not self._client:
            return
        _logger.debug("Bluetooth device %s disconnected", self._address)
        self._set_connected(False)
        self._handle_connection_lost()

    def _handle_connection_lost(self) -> None:
        """Reset the shot counter and schedule a reconnect if still enabled."""
        was_subscribed = self._shot_counter_subscribed
        self._shot_counter_subscribed = False
        self._brewing_tracker = _BrewingTracker()
        if not self._shot_counter_enabled:
            return
        if was_subscribed:
            _logger.debug("Shot counter connection lost, reinitializing brewing data")
            _safe_call(self._shot_counter_connection_callback, False)
        if self._reconnect_task is None or self._reconnect_task.done():
            self._reconnect_task = asyncio.create_task(self._reconnect_shot_counter())

    async def _reconnect_shot_counter(self) -> None:
        """Reconnect with backoff until the shot counter is subscribed again."""
        delay: float = RECONNECT_INITIAL_DELAY
        auth_failures = 0
        while self._shot_counter_enabled:
            await asyncio.sleep(delay)
            try:
                supported = await self._subscribe_shot_counter()
            except BluetoothAuthenticationFailed as e:
                auth_failures += 1
                _logger.warning(
                    "Shot counter authentication failed (%s/%s): %s",
                    auth_failures,
                    MAX_AUTH_FAILURES,
                    e,
                )
                if auth_failures >= MAX_AUTH_FAILURES:
                    _logger.error("Giving up reconnecting the shot counter")
                    break
            except (BleakError, TimeoutError, BluetoothConnectionFailed) as e:
                _logger.debug("Shot counter reconnect failed: %s", e)
                async with self._lock:
                    await self._disconnect_internal()
                delay = min(delay * 2, RECONNECT_MAX_DELAY)
            else:
                if supported:
                    return
                break
        # give up for good, without cancelling this task
        self._reconnect_task = None
        self._disable_shot_counter()
        if self.is_connected:
            self._reset_disconnect_timer()

    @staticmethod
    async def discover_devices(
        scanner: BaseBleakScanner | BleakScanner | None = None,
    ) -> list[BLEDevice]:
        """Find machines based on model name."""
        ble_devices: list[BLEDevice] = []

        if scanner is None:
            scanner = BleakScanner()
        assert hasattr(scanner, "discover")
        devices: list[BLEDevice] = await scanner.discover()
        for device in devices:
            if device.name and device.name.startswith(BT_MODEL_PREFIXES):
                ble_devices.append(device)

        return ble_devices

    @staticmethod
    async def read_token(address_or_ble_device: BLEDevice | str) -> str:
        """Read the token from the machine.

        Only possible when machine is in pairing mode.
        """
        async with BleakClient(address_or_ble_device) as client:
            token = await client.read_gatt_char(GET_TOKEN_CHARACTERISTIC)
            return token.decode()

    @property
    def address(self) -> str:
        """Return the BT MAC address of the machine."""

        return self._address

    @disconnect_on_exception
    async def get_machine_mode(self) -> MachineMode:
        """Read the current machine mode"""
        return MachineMode(
            await self.__read_value_from_machine(BluetoothReadSetting.MACHINE_MODE)
        )

    @disconnect_on_exception
    async def get_machine_capabilities(self) -> BluetoothMachineCapabilities:
        """Get general machine information."""
        capabilities = await self.__read_value_from_machine(
            BluetoothReadSetting.MACHINE_CAPABILITIES
        )
        return BluetoothMachineCapabilities.from_dict(capabilities[0])

    @disconnect_on_exception
    async def get_tank_status(self) -> bool:
        """Get the current tank status."""
        return _parse_bool(
            await self.__read_value_from_machine(BluetoothReadSetting.TANK_STATUS)
        )

    @disconnect_on_exception
    async def get_plumbed_in(self) -> bool:
        """Get whether the machine is plumbed in."""
        return _parse_bool(
            await self.__read_value_from_machine(BluetoothReadSetting.IS_PLUMBED_IN)
        )

    @disconnect_on_exception
    async def get_boilers(self) -> list[BluetoothBoilerDetails]:
        """Get the boiler status."""
        boilers = await self.__read_value_from_machine(BluetoothReadSetting.BOILERS)
        return [BluetoothBoilerDetails.from_dict(boiler) for boiler in boilers]

    @disconnect_on_exception
    async def get_smart_standby_settings(self) -> BluetoothSmartStandbyDetails:
        """Get the smart standby settings."""
        data = await self.__read_value_from_machine(BluetoothReadSetting.SMART_STAND_BY)
        return BluetoothSmartStandbyDetails.from_dict(data)

    @disconnect_on_exception
    async def set_power(self, enabled: bool) -> BluetoothCommandStatus:
        """Power on the machine."""
        mode = "BrewingMode" if enabled else "StandBy"
        data = {
            "name": "MachineChangeMode",
            "parameter": {
                "mode": mode,
            },
        }
        await self.__write_bluetooth_json_message(data)
        return await self._check_command_status()

    @disconnect_on_exception
    async def set_steam(self, enabled: bool) -> BluetoothCommandStatus:
        """Enable or disable the steam boiler."""
        data = {
            "name": "SettingBoilerEnable",
            "parameter": {
                "identifier": "SteamBoiler",
                "state": enabled,
            },
        }
        await self.__write_bluetooth_json_message(data)
        return await self._check_command_status()

    @disconnect_on_exception
    async def set_smart_standby(
        self, enabled: bool, mode: SmartStandByType, minutes: int
    ) -> BluetoothCommandStatus:
        """Set the smart standby settings."""
        data = {
            "name": "SettingSmartStandby",
            "parameter": {"minutes": minutes, "mode": mode.value, "enabled": enabled},
        }
        await self.__write_bluetooth_json_message(data)
        return await self._check_command_status()

    @disconnect_on_exception
    async def set_temp(self, boiler: BoilerType, temperature: float) -> BluetoothCommandStatus:
        """Set boiler temperature (in Celsius)"""
        data = {
            "name": "SettingBoilerTarget",
            "parameter": {
                "identifier": boiler.value,
                "value": temperature,
            },
        }
        await self.__write_bluetooth_json_message(data)
        return await self._check_command_status()

    async def _authenticate(self) -> None:
        """Build authentication string and send it to the machine."""
        if self._client is None:
            raise BluetoothConnectionFailed("Client is not connected")
            
        auth_characteristic = await self._resolve_characteristic(AUTH_CHARACTERISTIC)

        try:
            await self._client.write_gatt_char(
                char_specifier=auth_characteristic,
                data=bytes(self._ble_token, "utf-8"),
                response=True,
            )
            # the machine confirms a successful authentication with 0x01
            for attempt in range(AUTH_READ_ATTEMPTS):
                if attempt:
                    await asyncio.sleep(AUTH_READ_INTERVAL)
                result = await self._client.read_gatt_char(auth_characteristic)
                self._authentication_failed = bytes(result) != AUTH_SUCCESS
                if not self._authentication_failed:
                    return
        except (BleakError, TimeoutError) as e:
            raise BluetoothConnectionFailed(
                f"Failed to connect to machine with Bluetooth: {e}"
            ) from e
        raise BluetoothAuthenticationFailed("Bluetooth authentication failed")

    async def __read_value_from_machine(self, setting: BluetoothReadSetting) -> Any:
        await self.__write_bluetooth_message(setting.value, READ_CHARACTERISTIC)
        return json.loads(await self._read_bluetooth_message())

    async def _read_bluetooth_message(
        self, characteristic: str = READ_CHARACTERISTIC
    ) -> str:
        """Read a bluetooth message."""
        await self._ensure_connected()
        
        if self._client is None:
            raise BluetoothConnectionFailed("Client is not connected")

        read_characteristic = await self._resolve_characteristic(characteristic)
        result = await self._client.read_gatt_char(read_characteristic)
        # responses are NUL-terminated, ignore anything after it
        return bytes(result).split(b"\x00", 1)[0].decode()
    
    async def _check_command_status(
        self,
        characteristic: str = WRITE_CHARACTERISTIC,
    ) -> BluetoothCommandStatus:
        """Check the status of a command sent via Bluetooth."""
        result = await self._read_bluetooth_message(characteristic)
        return BluetoothCommandStatus.from_json(result)

    async def __write_bluetooth_message(
        self,
        message: bytes | str,
        characteristic: str = WRITE_CHARACTERISTIC,
    ) -> None:
        """Connect to machine and write a message."""
        await self._ensure_connected()
        
        if self._client is None:
            raise BluetoothConnectionFailed("Client is not connected")

        # check if message is already bytes string
        if not isinstance(message, bytes):
            message = bytes(message, "utf-8")

        # append trailing zeros to message
        message += b"\x00"

        _logger.debug("Sending bluetooth message: %s to %s", message, characteristic)

        settings_characteristic = await self._resolve_characteristic(characteristic)

        await self._client.write_gatt_char(
            char_specifier=settings_characteristic,
            data=message,
            response=True,
        )

    async def __write_bluetooth_json_message(
        self,
        data: dict[str, Any],
        characteristic: str = WRITE_CHARACTERISTIC,
    ) -> None:
        """Write a json message to the machine."""

        await self.__write_bluetooth_message(
            characteristic=characteristic,
            message=json.dumps(data, separators=(",", ":")),
        )

    async def _resolve_characteristic(
        self, characteristic: str
    ) -> BleakGATTCharacteristic:
        """Resolve characteristic UUID from machine services."""
        if self._client is None:
            raise BluetoothConnectionFailed("Client is not connected")
            
        resolved_characteristic = self._client.services.get_characteristic(
            characteristic
        )
        if resolved_characteristic is not None:
            return resolved_characteristic

        _logger.debug(
            "Characteristic %s not found in cache, clearing cache and retrying.",
            characteristic,
        )
        await self._client.clear_cache()

        resolved_characteristic = self._client.services.get_characteristic(
            characteristic
        )
        if resolved_characteristic is not None:
            return resolved_characteristic

        # Can't resolve characteristic - clear cache and schedule disconnect
        _logger.info(
            "Could not find characteristic %s on machine. Clearing cache and disconnecting.",
            characteristic,
        )
        await self._client.clear_cache()
        # Schedule disconnect outside the lock to avoid deadlock
        asyncio.create_task(self._drop_connection())
        raise BluetoothConnectionFailed(
            f"Could not find characteristic {characteristic} on machine."
        )
