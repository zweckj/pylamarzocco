"""Test the base thing module."""

from unittest.mock import MagicMock

import pytest

from pylamarzocco import LaMarzoccoBluetoothClient, LaMarzoccoCloudClient
from pylamarzocco.const import MachineMode, MachineState, WidgetType
from pylamarzocco.devices._thing import LaMarzoccoThing
from pylamarzocco.exceptions import CloudOnlyFunctionality
from pylamarzocco.models import (
    MachineStatus,
    ThingDashboardConfig,
    ThingDashboardWebsocketConfig,
    ThingSettings,
    ThingStatistics,
    UpdateDetails,
    WebSocketDetails,
    Widget,
)


@pytest.fixture(name="mock_cloud_client")
def mock_lm_cloud_client() -> MagicMock:
    """Mock the LaMarzoccoCloudClient."""
    return MagicMock(spec=LaMarzoccoCloudClient)


@pytest.fixture(name="mock_thing")
def mock_lm_thing(mock_cloud_client: MagicMock) -> LaMarzoccoThing:
    """Mock a thing with a cloud client."""
    return LaMarzoccoThing(serial_number="MR123456", cloud_client=mock_cloud_client)


def _machine_status() -> MachineStatus:
    return MachineStatus(
        status=MachineState.STANDBY,
        available_modes=[MachineMode.BREWING_MODE, MachineMode.STANDBY],
        mode=MachineMode.STANDBY,
        next_status=None,
        brewing_start_time=None,
    )


async def test_cloud_only_without_cloud_client() -> None:
    """Test cloud only functionality raises without a cloud client."""
    thing = LaMarzoccoThing(serial_number="MR123456")
    with pytest.raises(CloudOnlyFunctionality):
        await thing.get_dashboard()


async def test_connection_properties_without_clients() -> None:
    """Test the connection properties without any clients."""
    thing = LaMarzoccoThing(serial_number="MR123456")
    assert not thing.cloud_client_available
    assert not thing.bluetooth_client_available
    assert not thing.bluetooth_connected
    assert not thing.websocket.connected

    unregister = thing.register_bluetooth_connection_callback(MagicMock())
    assert unregister() is None


async def test_connection_properties_with_clients(
    mock_cloud_client: MagicMock,
) -> None:
    """Test the connection properties with clients."""
    bluetooth_client = MagicMock(spec=LaMarzoccoBluetoothClient)
    bluetooth_client.is_connected = True
    mock_cloud_client.websocket = WebSocketDetails()
    thing = LaMarzoccoThing(
        serial_number="MR123456",
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


async def test_get_dashboard(
    mock_thing: LaMarzoccoThing, mock_cloud_client: MagicMock
) -> None:
    """Test getting the dashboard."""
    dashboard = ThingDashboardConfig(serial_number="MR123456")
    mock_cloud_client.get_thing_dashboard.return_value = dashboard
    await mock_thing.get_dashboard()
    mock_cloud_client.get_thing_dashboard.assert_called_once_with("MR123456")
    assert mock_thing.dashboard is dashboard


async def test_get_settings(
    mock_thing: LaMarzoccoThing, mock_cloud_client: MagicMock
) -> None:
    """Test getting the settings."""
    settings = ThingSettings(serial_number="MR123456")
    mock_cloud_client.get_thing_settings.return_value = settings
    await mock_thing.get_settings()
    mock_cloud_client.get_thing_settings.assert_called_once_with("MR123456")
    assert mock_thing.settings is settings


async def test_get_statistics(
    mock_thing: LaMarzoccoThing, mock_cloud_client: MagicMock
) -> None:
    """Test getting the statistics."""
    statistics = ThingStatistics(serial_number="MR123456")
    mock_cloud_client.get_thing_statistics.return_value = statistics
    await mock_thing.get_statistics()
    mock_cloud_client.get_thing_statistics.assert_called_once_with("MR123456")
    assert mock_thing.statistics is statistics


async def test_get_firmware(
    mock_thing: LaMarzoccoThing, mock_cloud_client: MagicMock
) -> None:
    """Test getting the firmware."""
    firmware = MagicMock(spec=UpdateDetails)
    mock_cloud_client.get_thing_firmware.return_value = firmware
    assert await mock_thing.get_firmware() is firmware
    mock_cloud_client.get_thing_firmware.assert_called_once_with("MR123456")


async def test_update_firmware(
    mock_thing: LaMarzoccoThing, mock_cloud_client: MagicMock
) -> None:
    """Test starting the firmware update."""
    await mock_thing.update_firmware()
    mock_cloud_client.update_firmware.assert_called_once_with("MR123456")


async def test_connect_dashboard_websocket(
    mock_thing: LaMarzoccoThing, mock_cloud_client: MagicMock
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
    assert kwargs["serial_number"] == "MR123456"
    assert kwargs["connect_callback"] is connect_callback
    assert kwargs["disconnect_callback"] is disconnect_callback
    assert kwargs["auto_reconnect"] is False

    # an update with widgets replaces the dashboard config
    status = _machine_status()
    config = ThingDashboardWebsocketConfig(
        widgets=[Widget(code=WidgetType.CM_MACHINE_STATUS, index=1, output=status)],
        config={WidgetType.CM_MACHINE_STATUS: status},
        connected=True,
        connection_date=0,
        uuid="uuid",
        commands=[],
    )
    kwargs["notification_callback"](config)
    assert mock_thing.dashboard.config == {WidgetType.CM_MACHINE_STATUS: status}
    update_callback.assert_called_once_with(config)

    # an update without widgets leaves the dashboard untouched
    update_callback.reset_mock()
    empty_config = ThingDashboardWebsocketConfig(
        widgets=[], config={}, connected=True, connection_date=0, uuid="uuid", commands=[]
    )
    kwargs["notification_callback"](empty_config)
    assert mock_thing.dashboard.config == {WidgetType.CM_MACHINE_STATUS: status}
    update_callback.assert_called_once_with(empty_config)


async def test_to_dict(mock_thing: LaMarzoccoThing) -> None:
    """Test the dict representation."""
    result = mock_thing.to_dict()
    assert result["serial_number"] == "MR123456"
    assert result["dashboard"] == mock_thing.dashboard.to_dict()
    assert result["settings"] == mock_thing.settings.to_dict()
    assert result["statistics"] == mock_thing.statistics.to_dict()
