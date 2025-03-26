"""Bluetooth class for La Marzocco machines."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import Any

from bleak import (
    BaseBleakScanner,
    BleakClient,
    BleakError,
    BleakScanner,
    BLEDevice,
)

from pylamarzocco.legacy.const import (
    AUTH_CHARACTERISTIC,
    BT_MODEL_PREFIXES,
    SETTINGS_CHARACTERISTIC,
    BoilerType,
)
from pylamarzocco.legacy.exceptions import BluetoothConnectionFailed

_logger = logging.getLogger(__name__)


class LaMarzoccoBluetoothClient:
    """Class to interact with machine via Bluetooth."""

    def __init__(
        self,
        username: str,
        serial_number: str,
        token: str,
        address_or_ble_device: BLEDevice | str,
    ) -> None:
        """Initializes a new LaMarzoccoBluetoothClient instance."""
        self._username = username
        self._serial_number = serial_number
        self._token = token
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

    @property
    def address(self) -> str:
        """Return the BT MAC address of the machine."""

        return self._address

    async def set_power(self, enabled: bool) -> None:
        """Power on the machine."""

        mode = "BrewingMode" if enabled else "StandBy"
        data = {
            "name": "MachineChangeMode",
            "parameter": {
                "mode": mode,
            },
        }
        await self._write_bluetooth_json_message(data)

    async def set_steam(self, enabled: bool) -> None:
        """Power cycle steam."""

        data = {
            "name": "SettingBoilerEnable",
            "parameter": {
                "identifier": "SteamBoiler",
                "state": enabled,
            },
        }
        await self._write_bluetooth_json_message(data)

    async def set_temp(self, boiler: BoilerType, temperature: float) -> None:
        """Set boiler temperature (in Celsius)"""

        data = {
            "name": "SettingBoilerTarget",
            "parameter": {
                "identifier": boiler.value,
                "value": temperature,
            },
        }
        await self._write_bluetooth_json_message(data)

    async def _write_bluetooth_message(
        self, characteristic: str, message: bytes | str
    ) -> None:
        """Connect to machine and write a message."""

        # check if message is already bytes string
        if not isinstance(message, bytes):
            message = bytes(message, "utf-8")

        # append trailing zeros to message
        message += b"\x00"

        async with BleakClient(self._address_or_ble_device) as client:

            async def authenticate() -> None:
                """Build authentication string and send it to the machine."""

                user = self._username + ":" + self._serial_number
                user_bytes = user.encode("utf-8")
                token = self._token.encode("utf-8")
                auth_string = (
                    base64.b64encode(user_bytes) + b"@" + base64.b64encode(token)
                )

                auth_characteristic = client.services.get_characteristic(
                    AUTH_CHARACTERISTIC
                )
                if auth_characteristic is None:
                    raise BluetoothConnectionFailed(
                        f"Could not find auth characteristic {AUTH_CHARACTERISTIC} on machine."
                    )

                try:
                    await client.write_gatt_char(
                        char_specifier=auth_characteristic,
                        data=auth_string,
                        response=True,
                    )
                except (BleakError, TimeoutError) as e:
                    raise BluetoothConnectionFailed(
                        f"Failed to connect to machine with Bluetooth: {e}"
                    ) from e

            await authenticate()
            await asyncio.sleep(0.1)
            _logger.debug(
                "Sending bluetooth message: %s to %s", message, characteristic
            )

            settings_characteristic = client.services.get_characteristic(
                SETTINGS_CHARACTERISTIC
            )
            if settings_characteristic is None:
                raise BluetoothConnectionFailed(
                    f"Could not find settings characteristic {SETTINGS_CHARACTERISTIC} on machine."
                )

            await client.write_gatt_char(
                char_specifier=settings_characteristic,
                data=message,
                response=True,
            )

    async def _write_bluetooth_json_message(
        self,
        data: dict[str, Any],
        characteristic: str = SETTINGS_CHARACTERISTIC,
    ) -> None:
        """Write a json message to the machine."""

        await self._write_bluetooth_message(
            characteristic=characteristic,
            message=json.dumps(data, separators=(",", ":")),
        )
