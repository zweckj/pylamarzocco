"""Test the machine module."""

from unittest.mock import MagicMock

import pytest
from syrupy import SnapshotAssertion

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
from pylamarzocco.models import (
    BluetoothBoilerDetails,
    BluetoothSmartStandbyDetails,
)


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
    snapshot: SnapshotAssertion,
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
    mock_bluetooth_client.get_tank_status.return_value = True
    mock_bluetooth_client.get_smart_standby_settings.return_value = (
        BluetoothSmartStandbyDetails(
            mode=SmartStandByType.POWER_ON,
            minutes=30,
            enabled=True,
        )
    )

    await mock_machine.get_dashboard_from_bluetooth()

    # Verify the Bluetooth client methods were called
    mock_bluetooth_client.get_boilers.assert_called_once()
    mock_bluetooth_client.get_machine_mode.assert_called_once()
    mock_bluetooth_client.get_tank_status.assert_called_once()
    mock_bluetooth_client.get_smart_standby_settings.assert_called_once()

    # Verify the dashboard was updated with snapshot (excluding dynamic connection_date)
    dashboard_dict = mock_machine.dashboard.to_dict()
    dashboard_dict.pop("connection_date")
    assert dashboard_dict == snapshot
    
    # Verify schedule was updated with smart standby settings
    assert mock_machine.schedule.smart_stand_by_enabled is True
    assert mock_machine.schedule.smart_stand_by_minutes == 30
    assert mock_machine.schedule.smart_stand_by_after == SmartStandByType.POWER_ON


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


async def test_get_dashboard_from_bluetooth_disabled_boilers(
    mock_machine: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
) -> None:
    """Test getting dashboard from Bluetooth with disabled boilers."""
    # Mock the Bluetooth client methods with disabled boilers
    mock_bluetooth_client.get_boilers.return_value = [
        BluetoothBoilerDetails(
            id=BoilerType.COFFEE,
            is_enabled=False,
            target=94,
            current=25,
        ),
        BluetoothBoilerDetails(
            id=BoilerType.STEAM,
            is_enabled=False,
            target=131,
            current=25,
        ),
    ]
    mock_bluetooth_client.get_machine_mode.return_value = MachineMode.STANDBY
    mock_bluetooth_client.get_tank_status.return_value = False
    mock_bluetooth_client.get_smart_standby_settings.return_value = (
        BluetoothSmartStandbyDetails(
            mode=SmartStandByType.LAST_BREW,
            minutes=10,
            enabled=False,
        )
    )

    await mock_machine.get_dashboard_from_bluetooth()

    # Verify the dashboard was updated (now includes NoWater widget)
    assert len(mock_machine.dashboard.widgets) == 4

    # Verify coffee boiler widget has STAND_BY status
    coffee_boiler_widget = next(
        w for w in mock_machine.dashboard.widgets if w.code == WidgetType.CM_COFFEE_BOILER
    )
    assert coffee_boiler_widget.output.status == BoilerStatus.STAND_BY
    assert coffee_boiler_widget.output.enabled is False

    # Verify steam boiler widget has STAND_BY status
    steam_boiler_widget = next(
        w for w in mock_machine.dashboard.widgets if w.code == WidgetType.CM_STEAM_BOILER_LEVEL
    )
    assert steam_boiler_widget.output.status == BoilerStatus.STAND_BY
    assert steam_boiler_widget.output.enabled is False
    
    # Verify no water widget (tank_status=False means no water alarm)
    no_water_widget = next(
        w for w in mock_machine.dashboard.widgets if w.code == WidgetType.CM_NO_WATER
    )
    assert no_water_widget.output.allarm is True
