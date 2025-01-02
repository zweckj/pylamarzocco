# """"Test the Bluetooth client."""

# from collections.abc import Generator
# from unittest.mock import AsyncMock

# from pylamarzocco.clients.bluetooth import LaMarzoccoBluetoothClient
# from pylamarzocco.const import (
#     AUTH_CHARACTERISTIC,
#     SETTINGS_CHARACTERISTIC,
#     BoilerType,
# )


# async def test_bluetooth_set_power(
#     bluetooth_client: LaMarzoccoBluetoothClient,
#     mock_bleak: Generator[AsyncMock, None, None],
# ):
#     """Test setting the power."""
#     await bluetooth_client.set_power(True)

#     mock_bleak.write_gatt_char.assert_any_call(  # type: ignore[attr-defined]
#         char_specifier=AUTH_CHARACTERISTIC,
#         data=b"dXNlcm5hbWU6c2VyaWFs@dG9rZW4=",
#         response=True,
#     )

#     mock_bleak.write_gatt_char.assert_called_with(  # type: ignore[attr-defined]
#         char_specifier=SETTINGS_CHARACTERISTIC,
#         data=b'{"name":"MachineChangeMode","parameter":{"mode":"BrewingMode"}}\x00',
#         response=True,
#     )


# async def test_bluetooth_set_steam(
#     bluetooth_client: LaMarzoccoBluetoothClient,
#     mock_bleak: Generator[AsyncMock, None, None],
# ):
#     """Test setting the steam."""
#     await bluetooth_client.set_steam(True)

#     mock_bleak.write_gatt_char.assert_any_call(  # type: ignore[attr-defined]
#         char_specifier=AUTH_CHARACTERISTIC,
#         data=b"dXNlcm5hbWU6c2VyaWFs@dG9rZW4=",
#         response=True,
#     )

#     mock_bleak.write_gatt_char.assert_called_with(  # type: ignore[attr-defined]
#         char_specifier=SETTINGS_CHARACTERISTIC,
#         data=b'{"name":"SettingBoilerEnable","parameter":{"identifier":"SteamBoiler","state":true}}\x00',
#         response=True,
#     )


# async def test_bluetooth_set_temperature(
#     bluetooth_client: LaMarzoccoBluetoothClient,
#     mock_bleak: Generator[AsyncMock, None, None],
# ):
#     """Test setting the temp."""
#     await bluetooth_client.set_temp(BoilerType.STEAM, 131)

#     mock_bleak.write_gatt_char.assert_any_call(  # type: ignore[attr-defined]
#         char_specifier=AUTH_CHARACTERISTIC,
#         data=b"dXNlcm5hbWU6c2VyaWFs@dG9rZW4=",
#         response=True,
#     )

#     mock_bleak.write_gatt_char.assert_called_with(  # type: ignore[attr-defined]
#         char_specifier=SETTINGS_CHARACTERISTIC,
#         data=b'{"name":"SettingBoilerTarget","parameter":{"identifier":"SteamBoiler","value":131}}\x00',
#         response=True,
#     )
