"""Test the base thing module."""

from unittest.mock import MagicMock

import pytest

from pylamarzocco import LaMarzoccoBluetoothClient
from pylamarzocco.const import MachineMode, MachineState, WidgetType
from pylamarzocco.devices import LaMarzoccoThing
from pylamarzocco.exceptions import CloudOnlyFunctionality
from pylamarzocco.models import (
    ThingDashboardConfig,
    ThingSchedulingSettings,
    ThingSettings,
    ThingStatistics,
    UpdateDetails,
    WebSocketDetails,
)

from .conftest import machine_status, websocket_config


@pytest.fixture(name="mock_thing")
def mock_lm_thing(serial: str, mock_cloud_client: MagicMock) -> LaMarzoccoThing:
    """Mock a thing with a cloud client."""
    return LaMarzoccoThing(serial_number=serial, cloud_client=mock_cloud_client)


async def test_cloud_only_without_cloud_client(serial: str) -> None:
    """Test cloud only functionality raises without a cloud client."""
    thing = LaMarzoccoThing(serial_number=serial)
    with pytest.raises(CloudOnlyFunctionality):
        await thing.get_dashboard()


async def test_connection_properties_without_clients(serial: str) -> None:
    """Test the connection properties without any clients."""
    thing = LaMarzoccoThing(serial_number=serial)
    assert not thing.cloud_client_available
    assert not thing.bluetooth_client_available
    assert not thing.bluetooth_connected
    assert not thing.websocket.connected

    unregister = thing.register_bluetooth_connection_callback(MagicMock())
    assert unregister() is None


async def test_connection_properties_with_clients(
    serial: str,
    mock_cloud_client: MagicMock,
) -> None:
    """Test the connection properties with clients."""
    bluetooth_client = MagicMock(spec=LaMarzoccoBluetoothClient)
    bluetooth_client.is_connected = True
    mock_cloud_client.websocket = WebSocketDetails()
    thing = LaMarzoccoThing(
        serial_number=serial,
        cloud_client=mock_cloud_client,
        bluetooth_client=bluetooth_client,
    )
    assert thing.cloud_client_available
    assert thing.bluetooth_client_available
    assert thing.bluetooth_connected
    assert thing.websocket is mock_cloud_client.websocket


async def test_ensure_token_valid(
    mock_thing: LaMarzoccoThing, mock_cloud_client: MagicMock
) -> None:
    """Test ensuring the token is valid."""
    await mock_thing.ensure_token_valid()
    mock_cloud_client.async_get_access_token.assert_called_once()


@pytest.mark.parametrize(
    ("method", "cloud_method", "attribute", "model"),
    [
        ("get_dashboard", "get_thing_dashboard", "dashboard", ThingDashboardConfig),
        ("get_settings", "get_thing_settings", "settings", ThingSettings),
        ("get_statistics", "get_thing_statistics", "statistics", ThingStatistics),
        ("get_schedule", "get_thing_schedule", "schedule", ThingSchedulingSettings),
    ],
)
async def test_get_thing_data(
    mock_thing: LaMarzoccoThing,
    mock_cloud_client: MagicMock,
    serial: str,
    method: str,
    cloud_method: str,
    attribute: str,
    model: type,
) -> None:
    """Test fetching the dashboard, settings, statistics and schedule."""
    data = model(serial_number=serial)
    getattr(mock_cloud_client, cloud_method).return_value = data
    await getattr(mock_thing, method)()
    getattr(mock_cloud_client, cloud_method).assert_called_once_with(serial)
    assert getattr(mock_thing, attribute) is data


async def test_get_firmware(
    mock_thing: LaMarzoccoThing, mock_cloud_client: MagicMock, serial: str
) -> None:
    """Test getting the firmware."""
    firmware = MagicMock(spec=UpdateDetails)
    mock_cloud_client.get_thing_firmware.return_value = firmware
    assert await mock_thing.get_firmware() is firmware
    mock_cloud_client.get_thing_firmware.assert_called_once_with(serial)


async def test_update_firmware(
    mock_thing: LaMarzoccoThing, mock_cloud_client: MagicMock, serial: str
) -> None:
    """Test starting the firmware update."""
    await mock_thing.update_firmware()
    mock_cloud_client.update_firmware.assert_called_once_with(serial)


async def test_connect_dashboard_websocket(
    mock_thing: LaMarzoccoThing, mock_cloud_client: MagicMock, serial: str
) -> None:
    """Test connecting to the dashboard websocket and receiving updates."""
    update_callback = MagicMock()
    connect_callback = MagicMock()
    disconnect_callback = MagicMock()
    await mock_thing.connect_dashboard_websocket(
        update_callback=update_callback,
        connect_callback=connect_callback,
        disconnect_callback=disconnect_callback,
        auto_reconnect=False,
    )
    mock_cloud_client.websocket_connect.assert_called_once()
    kwargs = mock_cloud_client.websocket_connect.call_args.kwargs
    assert kwargs["serial_number"] == serial
    assert kwargs["connect_callback"] is connect_callback
    assert kwargs["disconnect_callback"] is disconnect_callback
    assert kwargs["auto_reconnect"] is False

    # an update with widgets replaces the dashboard config
    status = machine_status(MachineState.STANDBY, mode=MachineMode.STANDBY)
    config = websocket_config(status)
    kwargs["notification_callback"](config)
    assert mock_thing.dashboard.config == {WidgetType.CM_MACHINE_STATUS: status}
    update_callback.assert_called_once_with(config)

    # an update without widgets leaves the dashboard untouched
    update_callback.reset_mock()
    empty_config = websocket_config(None)
    kwargs["notification_callback"](empty_config)
    assert mock_thing.dashboard.config == {WidgetType.CM_MACHINE_STATUS: status}
    update_callback.assert_called_once_with(empty_config)


async def test_to_dict(mock_thing: LaMarzoccoThing, serial: str) -> None:
    """Test the dict representation."""
    result = mock_thing.to_dict()
    assert result["serial_number"] == serial
    assert result["dashboard"] == mock_thing.dashboard.to_dict()
    assert result["settings"] == mock_thing.settings.to_dict()
    assert result["statistics"] == mock_thing.statistics.to_dict()
    assert result["schedule"] == mock_thing.schedule.to_dict()
