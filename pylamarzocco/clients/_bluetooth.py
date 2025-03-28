"""Bluetooth class for La Marzocco machines."""

from __future__ import annotations

import json
import logging
from typing import Any

from bleak import BaseBleakScanner, BleakClient, BleakError, BleakScanner, BLEDevice

from pylamarzocco.const import BoilerType, MachineMode, SmartStandByType
from pylamarzocco.exceptions import BluetoothConnectionFailed
from pylamarzocco.models import (
    BluetoothBoilerDetails,
    BluetoothMachineCapabilities,
    BluetoothSmartStandbyDetails,
)

_logger = logging.getLogger(__name__)

READ_CHARACTERISTIC = "0a0b7847-e12b-09a8-b04b-8e0922a9abab"
WRITE_CHARACTERISTIC = "0b0b7847-e12b-09a8-b04b-8e0922a9abab"
GET_TOKEN_CHARACTERISTIC = "0c0b7847-e12b-09a8-b04b-8e0922a9abab"
AUTH_CHARACTERISTIC = "0d0b7847-e12b-09a8-b04b-8e0922a9abab"

BT_MODEL_PREFIXES = ("MICRA", "MINI", "GS3")


class LaMarzoccoBluetoothClient:
    """Class to interact with machine via Bluetooth."""

    def __init__(
        self,
        address_or_ble_device: BLEDevice | str,
        ble_token: str,
    ) -> None:
        """Initializes a new bluetooth client instance."""
        self._ble_token = ble_token
        self._address = (
            address_or_ble_device.address
            if isinstance(address_or_ble_device, BLEDevice)
            else address_or_ble_device
        )
        self._address_or_ble_device = address_or_ble_device

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
    async def read_token(address: str) -> str:
        """Read the token from the machine.

        Only possible when machine is in pairing mode.
        """
        async with BleakClient(address) as client:
            token = await client.read_gatt_char(GET_TOKEN_CHARACTERISTIC)
            return token.decode()

    @property
    def address(self) -> str:
        """Return the BT MAC address of the machine."""

        return self._address

    async def get_machine_mode(self) -> MachineMode:
        """Read the current machine mode"""
        return MachineMode(await self._read_value_from_machine("machineMode"))

    async def get_machine_capabilities(self) -> BluetoothMachineCapabilities:
        """Get general machine information."""
        capabilities = await self._read_value_from_machine("machineCapabilities")
        return BluetoothMachineCapabilities.from_dict(capabilities[0])

    async def get_tank_status(self) -> bool:
        """Get the current tank status."""
        return bool(await self._read_value_from_machine("tankStatus"))

    async def get_boilers(self) -> list[BluetoothBoilerDetails]:
        """Get the boiler status."""
        boilers = await self._read_value_from_machine("boilers")
        return [BluetoothBoilerDetails.from_dict(boiler) for boiler in boilers]

    async def get_smart_standby_settings(self) -> BluetoothSmartStandbyDetails:
        """Get the smart standby settings."""
        data = await self._read_value_from_machine("smartStandBy")
        return BluetoothSmartStandbyDetails.from_dict(data)

    async def set_power(self, enabled: bool) -> None:
        """Power on the machine."""
        mode = "BrewingMode" if enabled else "StandBy"
        data = {
            "name": "MachineChangeMode",
            "parameter": {
                "mode": mode,
            },
        }
        await self._change_setting_machine(data)

    async def set_smart_standby(
        self, enabled: bool, mode: SmartStandByType, minutes: int
    ) -> None:
        """Set the smart standby settings."""
        data = {
            "name": "SettingSmartStandby",
            "parameter": {"minutes": minutes, "mode": mode.value, "enabled": enabled},
        }
        await self._change_setting_machine(data)

    async def set_temp(self, boiler: BoilerType, temperature: float) -> None:
        """Set boiler temperature (in Celsius)"""

        data = {
            "name": "SettingBoilerTarget",
            "parameter": {
                "identifier": boiler.value,
                "value": temperature,
            },
        }
        await self._change_setting_machine(data)

    async def authenticate(self, client: BleakClient) -> None:
        """Build authentication string and send it to the machine."""

        auth_characteristic = client.services.get_characteristic(AUTH_CHARACTERISTIC)
        if auth_characteristic is None:
            raise BluetoothConnectionFailed(
                f"Could not find auth characteristic {AUTH_CHARACTERISTIC} on machine."
            )

        try:
            await client.write_gatt_char(
                char_specifier=auth_characteristic,
                data=bytes(self._ble_token, "utf-8"),
                response=True,
            )
        except (BleakError, TimeoutError) as e:
            raise BluetoothConnectionFailed(
                f"Failed to connect to machine with Bluetooth: {e}"
            ) from e

    async def _read_value_from_machine(self, value: str) -> Any:
        async with BleakClient(self._address_or_ble_device) as client:
            await self.authenticate(client)
            await self._write_bluetooth_message(client, value, READ_CHARACTERISTIC)
            return json.loads(await self._read_bluetooth_message(client))

    async def _read_bluetooth_message(
        self, client: BleakClient, characteristic: str = READ_CHARACTERISTIC
    ) -> str:
        """Read a bluetooth message."""

        read_characteristic = client.services.get_characteristic(characteristic)
        if read_characteristic is None:
            raise BluetoothConnectionFailed(
                f"Could not find auth characteristic {characteristic} on machine."
            )

        result = await client.read_gatt_char(read_characteristic)
        return result.decode()

    async def _write_bluetooth_message(
        self,
        client: BleakClient,
        message: bytes | str,
        characteristic: str = WRITE_CHARACTERISTIC,
    ) -> None:
        """Connect to machine and write a message."""

        # check if message is already bytes string
        if not isinstance(message, bytes):
            message = bytes(message, "utf-8")

        # append trailing zeros to message
        message += b"\x00"

        _logger.debug("Sending bluetooth message: %s to %s", message, characteristic)

        settings_characteristic = client.services.get_characteristic(characteristic)
        if settings_characteristic is None:
            raise BluetoothConnectionFailed(
                f"Could not find characteristic {characteristic} on machine."
            )

        await client.write_gatt_char(
            char_specifier=settings_characteristic,
            data=message,
            response=True,
        )

    async def _write_bluetooth_json_message(
        self,
        client: BleakClient,
        data: dict[str, Any],
        characteristic: str = WRITE_CHARACTERISTIC,
    ) -> None:
        """Write a json message to the machine."""

        await self._write_bluetooth_message(
            client=client,
            characteristic=characteristic,
            message=json.dumps(data, separators=(",", ":")),
        )

    async def _change_setting_machine(
        self,
        data: dict[str, Any],
    ) -> None:
        """Change a setting on the machine."""
        async with BleakClient(self._address_or_ble_device) as client:
            await self.authenticate(client)
            await self._write_bluetooth_json_message(client, data)
