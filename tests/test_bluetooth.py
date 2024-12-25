""""Test the Bluetooth client."""

from unittest.mock import patch

from pylamarzocco.clients.bluetooth import LaMarzoccoBluetoothClient
from pylamarzocco.const import (
    AUTH_CHARACTERISTIC,
    SETTINGS_CHARACTERISTIC,
    BoilerType,
)


async def test_bluetooth_set_power(
    bluetooth_client: LaMarzoccoBluetoothClient,
):
    """Test setting the power."""
    with patch("pylamarzocco.clients.bluetooth.BleakClient") as bleak_client:
        await bluetooth_client.set_power(True)

        write_gatt_char = (
            bleak_client.return_value.__aenter__.return_value.write_gatt_char
        )

        write_gatt_char.assert_any_call(  # type: ignore[attr-defined]
            char_specifier=AUTH_CHARACTERISTIC,
            data=b"dXNlcm5hbWU6c2VyaWFs@dG9rZW4=",
        )

        write_gatt_char.assert_called_with(  # type: ignore[attr-defined]
            char_specifier=SETTINGS_CHARACTERISTIC,
            data=b'{"name":"MachineChangeMode","parameter":{"mode":"BrewingMode"}}\x00',
        )


async def test_bluetooth_set_steam(
    bluetooth_client: LaMarzoccoBluetoothClient,
):
    """Test setting the steam."""
    with patch("pylamarzocco.clients.bluetooth.BleakClient") as bleak_client:
        await bluetooth_client.set_steam(True)

        write_gatt_char = (
            bleak_client.return_value.__aenter__.return_value.write_gatt_char
        )

        write_gatt_char.assert_any_call(  # type: ignore[attr-defined]
            char_specifier=AUTH_CHARACTERISTIC,
            data=b"dXNlcm5hbWU6c2VyaWFs@dG9rZW4=",
        )

        write_gatt_char.assert_called_with(  # type: ignore[attr-defined]
            char_specifier=SETTINGS_CHARACTERISTIC,
            data=b'{"name":"SettingBoilerEnable","parameter":{"identifier":"SteamBoiler","state":true}}\x00',
        )


async def test_bluetooth_set_temperature(
    bluetooth_client: LaMarzoccoBluetoothClient,
):
    """Test setting the temp."""
    with patch("pylamarzocco.clients.bluetooth.BleakClient") as bleak_client:
        await bluetooth_client.set_temp(BoilerType.STEAM, 131)

        write_gatt_char = (
            bleak_client.return_value.__aenter__.return_value.write_gatt_char
        )

        write_gatt_char.assert_any_call(  # type: ignore[attr-defined]
            char_specifier=AUTH_CHARACTERISTIC,
            data=b"dXNlcm5hbWU6c2VyaWFs@dG9rZW4=",
        )

        write_gatt_char.assert_called_with(  # type: ignore[attr-defined]
            char_specifier=SETTINGS_CHARACTERISTIC,
            data=b'{"name":"SettingBoilerTarget","parameter":{"identifier":"SteamBoiler","value":131}}\x00',
        )
