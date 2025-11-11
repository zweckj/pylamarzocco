"""Test the machine module."""

from unittest.mock import MagicMock

import pytest

from pylamarzocco import (
    LaMarzoccoBluetoothClient,
    LaMarzoccoCloudClient,
    LaMarzoccoMachine,
)
from pylamarzocco.const import (
    BoilerStatus,
    BoilerType,
    MachineMode,
    MachineState,
    SteamTargetLevel,
    SmartStandByType,
    WidgetType,
)
from pylamarzocco.exceptions import BluetoothConnectionFailed
from pylamarzocco.models import BluetoothBoilerDetails


@pytest.fixture(name="mock_bluetooth_client")
def mock_lm_bluetooth_client() -> MagicMock:
    """Mock the LaMarzoccoBluetoothClient."""
    client = MagicMock(spec=LaMarzoccoBluetoothClient)
    return client


@pytest.fixture(name="mock_cloud_client")
def mock_lm_cloud_client() -> MagicMock:
    """Mock the LaMarzoccoCloudClient."""
    client = MagicMock(spec=LaMarzoccoCloudClient)
    return client


@pytest.fixture(name="mock_machine")
def mock_lm_machine(
    mock_bluetooth_client: MagicMock,
    mock_cloud_client: MagicMock,
) -> LaMarzoccoMachine:
    """Mock the LaMarzoccoMachine."""
    machine = LaMarzoccoMachine(
        serial_number="MR123456",
        bluetooth_client=mock_bluetooth_client,
        cloud_client=mock_cloud_client,
    )
    return machine


async def test_set_power(
    mock_machine: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
) -> None:
    """Test the set_power method."""
    assert await mock_machine.set_power(True)
    mock_bluetooth_client.set_power.assert_called_once_with(enabled=True)


async def test_set_power_cloud_fallback(
    mock_machine: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
    mock_cloud_client: MagicMock,
) -> None:
    """Test the set_power method without Bluetooth."""
    mock_bluetooth_client.set_power.side_effect = BluetoothConnectionFailed(
        "Bluetooth error"
    )
    assert await mock_machine.set_power(True)
    mock_bluetooth_client.set_power.assert_called_once_with(enabled=True)
    mock_cloud_client.set_power.assert_called_once_with(
        serial_number="MR123456", enabled=True
    )


async def test_set_steam_level(
    mock_machine: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
) -> None:
    """Test the set_steam_level method."""
    assert await mock_machine.set_steam_level(SteamTargetLevel.LEVEL_2)
    mock_bluetooth_client.set_temp.assert_called_once_with(
        boiler=BoilerType.STEAM, temperature=128
    )


async def test_set_steam_level_cloud_fallback(
    mock_machine: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
    mock_cloud_client: MagicMock,
) -> None:
    """Test the set_steam_level method without Bluetooth."""
    mock_bluetooth_client.set_temp.side_effect = BluetoothConnectionFailed(
        "Bluetooth error"
    )
    assert await mock_machine.set_steam_level(SteamTargetLevel.LEVEL_2)
    mock_bluetooth_client.set_temp.assert_called_once_with(
        boiler=BoilerType.STEAM, temperature=128
    )
    mock_cloud_client.set_steam_target_level.assert_called_once_with(
        serial_number="MR123456", target_level=SteamTargetLevel.LEVEL_2
    )


async def test_set_coffee_temp(
    mock_machine: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
) -> None:
    """Test the set_coffee_temp method."""
    assert await mock_machine.set_coffee_target_temperature(93)
    mock_bluetooth_client.set_temp.assert_called_once_with(
        boiler=BoilerType.COFFEE, temperature=93
    )


async def test_set_coffee_temp_cloud_fallback(
    mock_machine: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
    mock_cloud_client: MagicMock,
) -> None:
    """Test the set_coffee_temp method without Bluetooth."""
    mock_bluetooth_client.set_temp.side_effect = BluetoothConnectionFailed(
        "Bluetooth error"
    )
    assert await mock_machine.set_coffee_target_temperature(93)
    mock_bluetooth_client.set_temp.assert_called_once_with(
        boiler=BoilerType.COFFEE, temperature=93
    )
    mock_cloud_client.set_coffee_target_temperature.assert_called_once_with(
        serial_number="MR123456", target_temperature=93
    )


async def test_set_smart_standby(
    mock_machine: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
) -> None:
    """Test the set_smart_standby method."""
    assert await mock_machine.set_smart_standby(True, 30, SmartStandByType.POWER_ON)
    mock_bluetooth_client.set_smart_standby.assert_called_once_with(
        enabled=True, minutes=30, mode=SmartStandByType.POWER_ON
    )


async def test_set_smart_standby_cloud_fallback(
    mock_machine: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
    mock_cloud_client: MagicMock,
) -> None:
    """Test the set_smart_standby method without Bluetooth."""
    mock_bluetooth_client.set_smart_standby.side_effect = BluetoothConnectionFailed(
        "Bluetooth error"
    )
    assert await mock_machine.set_smart_standby(True, 30, SmartStandByType.POWER_ON)
    mock_bluetooth_client.set_smart_standby.assert_called_once_with(
        enabled=True, minutes=30, mode=SmartStandByType.POWER_ON
    )
    mock_cloud_client.set_smart_standby.assert_called_once_with(
        serial_number="MR123456",
        enabled=True,
        minutes=30,
        after=SmartStandByType.POWER_ON,
    )


async def test_failing_command(
    mock_machine: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
    mock_cloud_client: MagicMock,
) -> None:
    """Check we return false if both clients fail."""
    mock_bluetooth_client.set_power.side_effect = BluetoothConnectionFailed(
        "Bluetooth error"
    )
    mock_cloud_client.set_power.return_value = False
    assert not await mock_machine.set_power(True)


async def test_get_dashboard_from_bluetooth(
    mock_machine: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
) -> None:
    """Test getting dashboard from Bluetooth."""
    # Mock the Bluetooth client methods
    mock_bluetooth_client.get_boilers.return_value = [
        BluetoothBoilerDetails(
            id=BoilerType.COFFEE,
            is_enabled=True,
            target=94,
            current=93,
        ),
        BluetoothBoilerDetails(
            id=BoilerType.STEAM,
            is_enabled=True,
            target=131,
            current=130,
        ),
    ]
    mock_bluetooth_client.get_machine_mode.return_value = MachineMode.BREWING_MODE

    await mock_machine.get_dashboard_from_bluetooth()

    # Verify the Bluetooth client methods were called
    mock_bluetooth_client.get_boilers.assert_called_once()
    mock_bluetooth_client.get_machine_mode.assert_called_once()

    # Verify the dashboard was updated
    assert mock_machine.dashboard.serial_number == "MR123456"
    assert len(mock_machine.dashboard.widgets) == 3

    # Verify machine status widget
    machine_status_widget = next(
        w for w in mock_machine.dashboard.widgets if w.code == WidgetType.CM_MACHINE_STATUS
    )
    assert machine_status_widget.output.status == MachineState.POWERED_ON
    assert machine_status_widget.output.mode == MachineMode.BREWING_MODE

    # Verify coffee boiler widget
    coffee_boiler_widget = next(
        w for w in mock_machine.dashboard.widgets if w.code == WidgetType.CM_COFFEE_BOILER
    )
    assert coffee_boiler_widget.output.target_temperature == 94.0
    assert coffee_boiler_widget.output.enabled is True
    assert coffee_boiler_widget.output.status == BoilerStatus.READY

    # Verify steam boiler widget
    steam_boiler_widget = next(
        w for w in mock_machine.dashboard.widgets if w.code == WidgetType.CM_STEAM_BOILER_LEVEL
    )
    assert steam_boiler_widget.output.target_level == SteamTargetLevel.LEVEL_3
    assert steam_boiler_widget.output.enabled is True
    assert steam_boiler_widget.output.status == BoilerStatus.READY


async def test_get_dashboard_from_bluetooth_no_client(
    mock_cloud_client: MagicMock,
) -> None:
    """Test getting dashboard from Bluetooth without Bluetooth client."""
    machine = LaMarzoccoMachine(
        serial_number="MR123456",
        bluetooth_client=None,
        cloud_client=mock_cloud_client,
    )

    with pytest.raises(BluetoothConnectionFailed, match="Bluetooth client is not initialized"):
        await machine.get_dashboard_from_bluetooth()
