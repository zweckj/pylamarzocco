"""Bluetooth class for La Marzocco machines."""

from __future__ import annotations

import asyncio
from functools import wraps
import json
import logging
from typing import Any, Callable, Concatenate, Coroutine

from bleak import BaseBleakScanner, BleakClient, BleakError, BleakScanner, BLEDevice
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from pylamarzocco.const import (
    BluetoothReadSetting,
    BoilerType,
    MachineMode,
    SmartStandByType,
)
from pylamarzocco.exceptions import BluetoothConnectionFailed
from pylamarzocco.models import (
    BluetoothBoilerDetails,
    BluetoothCommandStatus,
    BluetoothMachineCapabilities,
    BluetoothSmartStandbyDetails,
)

_logger = logging.getLogger(__name__)

READ_CHARACTERISTIC = "0a0b7847-e12b-09a8-b04b-8e0922a9abab"
WRITE_CHARACTERISTIC = "0b0b7847-e12b-09a8-b04b-8e0922a9abab"
GET_TOKEN_CHARACTERISTIC = "0c0b7847-e12b-09a8-b04b-8e0922a9abab"
AUTH_CHARACTERISTIC = "0d0b7847-e12b-09a8-b04b-8e0922a9abab"

BT_MODEL_PREFIXES = ("MICRA", "MINI", "GS3")
IDLE_TIMEOUT = 30  # seconds


def disconnect_on_exception[
    T: "LaMarzoccoBluetoothClient", _R, **P
](
    func: Callable[Concatenate[T, P], Coroutine[Any, Any, _R]],
) -> Callable[Concatenate[T, P], Coroutine[Any, Any, _R]]:
    """Decorator to disconnect on exception."""

    @wraps(func)
    async def wrapper(
        self: T, *args: P.args, **kwargs: P.kwargs
    ) -> _R:
        try:
            return await func(self, *args, **kwargs)
        except (BleakError, TimeoutError, BluetoothConnectionFailed):
            # Disconnect on error (outside the lock to avoid deadlock)
            asyncio.create_task(self.disconnect())
            raise

    return wrapper


class LaMarzoccoBluetoothClient:
    """Class to interact with machine via Bluetooth."""

    def __init__(
        self,
        ble_device: BLEDevice,
        ble_token: str,
    ) -> None:
        """Initializes a new bluetooth client instance.
        
        Args:
            ble_device: The BLE device to connect to
            ble_token: Authentication token for the device
        """
        self._ble_token = ble_token
        self._address = ble_device.address
        self._ble_device = ble_device
        self._client: BleakClientWithServiceCache | None = None
        self._lock: asyncio.Lock = asyncio.Lock()
        self._disconnect_task: asyncio.Task[None] | None = None



    @property
    def is_connected(self) -> bool:
        """Return whether the client is currently connected."""
        return self._client is not None and self._client.is_connected

    async def _ensure_connected(self) -> None:
        """Ensure we're connected to the device, connecting if necessary."""
        async with self._lock:
            if self.is_connected:
                # Reset the disconnect timer
                self._reset_disconnect_timer()
                return
            
            _logger.debug("Connecting to Bluetooth device %s", self._address)
            try:
                self._client = await establish_connection(
                    BleakClientWithServiceCache,
                    self._ble_device,
                    self._ble_device.name or "Unknown",
                    max_attempts=3,
                )
                await self._authenticate()
            except (BleakError, TimeoutError, BluetoothConnectionFailed) as e:
                _logger.error("Failed to connect to Bluetooth device: %s", e)
                self._client = None
                raise
            else:
                _logger.debug("Successfully connected to Bluetooth device %s", self._address)
                # Start the disconnect timer
                self._reset_disconnect_timer()

    def _reset_disconnect_timer(self) -> None:
        """Reset the auto-disconnect timer."""
        # Cancel existing timer if any
        if self._disconnect_task is not None and not self._disconnect_task.done():
            self._disconnect_task.cancel()
        
        # Start new timer
        self._disconnect_task = asyncio.create_task(self._auto_disconnect())

    async def _auto_disconnect(self) -> None:
        """Automatically disconnect after idle timeout."""
        try:
            await asyncio.sleep(IDLE_TIMEOUT)
        except asyncio.CancelledError:
            # Timer was reset, this is normal
            pass
        else:
            _logger.debug("Auto-disconnect timer expired, disconnecting from %s", self._address)
            await self.disconnect()

    async def _disconnect_internal(self) -> None:
        """Internal disconnect that doesn't acquire lock (assumes lock is already held)."""
        # Cancel disconnect timer
        if self._disconnect_task is not None and not self._disconnect_task.done():
            self._disconnect_task.cancel()
            self._disconnect_task = None

        if self._client is not None and self._client.is_connected:
            _logger.debug("Disconnecting from Bluetooth device %s", self._address)
            try:
                await self._client.disconnect()
            except Exception as e:
                _logger.error("Error disconnecting from Bluetooth device: %s", e)
            finally:
                self._client = None

    async def disconnect(self) -> None:
        """Disconnect from the device."""
        async with self._lock:
            await self._disconnect_internal()

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
        return bool(
            await self.__read_value_from_machine(BluetoothReadSetting.TANK_STATUS)
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
        except (BleakError, TimeoutError) as e:
            raise BluetoothConnectionFailed(
                f"Failed to connect to machine with Bluetooth: {e}"
            ) from e

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
        return result.decode()
    
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
        asyncio.create_task(self.disconnect())
        raise BluetoothConnectionFailed(
            f"Could not find characteristic {characteristic} on machine."
        )
