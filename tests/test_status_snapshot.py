"""Test MachineStatusSnapshot functionality."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pylamarzocco import LaMarzoccoBluetoothClient, LaMarzoccoCloudClient
from pylamarzocco.const import (
    BoilerType,
    MachineMode,
    SmartStandByType,
    SteamTargetLevel,
    WidgetType,
)
from pylamarzocco.devices._machine import LaMarzoccoMachine
from pylamarzocco.models import (
    BluetoothBoilerDetails,
    CoffeeBoiler,
    MachineStatus,
    MachineStatusSnapshot,
    NoWater,
    SteamBoilerLevel,
    SteamBoilerTemperature,
    ThingDashboardConfig,
)


async def test_bluetooth_get_status_snapshot() -> None:
    """Test getting status snapshot via Bluetooth."""
    # Mock the BleakClient
    with patch("pylamarzocco.clients._bluetooth.BleakClient", autospec=True) as mock_bleak:
        mock_client = mock_bleak.return_value
        mock_client.is_connected = True
        mock_client.services.get_characteristic.return_value = "mock_characteristic"
        
        # Mock the responses
        mock_client.read_gatt_char.side_effect = [
            b'"BrewingMode"',  # machine mode (JSON string)
            b'[{"id":"SteamBoiler","isEnabled":true,"target":131,"current":45},{"id":"CoffeeBoiler1","isEnabled":true,"target":94,"current":65}]',  # boilers
            b"true",  # tank status (JSON boolean)
        ]
        
        bt_client = LaMarzoccoBluetoothClient("test_address", "test_token")
        
        async with bt_client:
            snapshot = await bt_client.get_status_snapshot()
        
        # Verify the snapshot
        assert snapshot.power_on is True
        assert snapshot.coffee_boiler_enabled is True
        assert snapshot.coffee_target_temperature == 94.0
        assert snapshot.steam_boiler_enabled is True
        assert snapshot.steam_target_temperature == 131.0
        assert snapshot.water_reservoir_contact is True


async def test_machine_update_status_bluetooth() -> None:
    """Test updating machine status via Bluetooth."""
    # Create mock Bluetooth client
    mock_bt_client = MagicMock(spec=LaMarzoccoBluetoothClient)
    mock_snapshot = MachineStatusSnapshot(
        power_on=True,
        coffee_boiler_enabled=True,
        coffee_target_temperature=94.0,
        steam_boiler_enabled=True,
        steam_target_temperature=131.0,
        water_reservoir_contact=True,
    )
    
    # Mock the context manager
    mock_bt_client.__aenter__ = AsyncMock(return_value=mock_bt_client)
    mock_bt_client.__aexit__ = AsyncMock(return_value=None)
    mock_bt_client.get_status_snapshot = AsyncMock(return_value=mock_snapshot)
    
    # Create machine with Bluetooth client
    machine = LaMarzoccoMachine("TEST123", bluetooth_client=mock_bt_client)
    
    # Update status via Bluetooth
    await machine.update_status_bluetooth()
    
    # Verify status was set
    assert machine.status is not None
    assert machine.status.power_on is True
    assert machine.status.coffee_target_temperature == 94.0
    assert machine.status.steam_target_temperature == 131.0


async def test_machine_update_status_cloud() -> None:
    """Test updating machine status via Cloud."""
    # Create mock Cloud client
    mock_cloud_client = MagicMock(spec=LaMarzoccoCloudClient)
    
    # Create a mock dashboard with widgets
    dashboard = ThingDashboardConfig(serial_number="TEST123")
    dashboard.config = {
        WidgetType.CM_MACHINE_STATUS: MachineStatus(
            status="StandBy",
            available_modes=["BrewingMode", "StandBy"],
            mode=MachineMode.BREWING_MODE,
            next_status=None,
            brewing_start_time=None,
        ),
        WidgetType.CM_COFFEE_BOILER: CoffeeBoiler(
            status="Ready",
            enabled=True,
            enabled_supported=False,
            target_temperature=94.0,
            target_temperature_min=80,
            target_temperature_max=100,
            target_temperature_step=0.1,
            ready_start_time=None,
        ),
        WidgetType.CM_STEAM_BOILER_LEVEL: SteamBoilerLevel(
            status="Ready",
            enabled=True,
            enabled_supported=True,
            target_level=SteamTargetLevel.LEVEL_3,
            target_level_supported=True,
            ready_start_time=None,
        ),
        WidgetType.CM_NO_WATER: NoWater(allarm=False),
    }
    
    # Create machine with Cloud client
    machine = LaMarzoccoMachine("TEST123", cloud_client=mock_cloud_client)
    machine.dashboard = dashboard
    
    # Update status via Cloud
    await machine.update_status_cloud()
    
    # Verify status was set correctly
    assert machine.status is not None
    assert machine.status.power_on is True
    assert machine.status.coffee_boiler_enabled is True
    assert machine.status.coffee_target_temperature == 94.0
    assert machine.status.steam_boiler_enabled is True
    assert machine.status.steam_target_temperature == 131.0  # Level 3
    assert machine.status.water_reservoir_contact is True


async def test_machine_update_status_cloud_with_steam_temperature() -> None:
    """Test updating machine status via Cloud with steam temperature widget."""
    # Create mock Cloud client
    mock_cloud_client = MagicMock(spec=LaMarzoccoCloudClient)
    
    # Create a mock dashboard with steam temperature widget
    dashboard = ThingDashboardConfig(serial_number="TEST123")
    dashboard.config = {
        WidgetType.CM_MACHINE_STATUS: MachineStatus(
            status="StandBy",
            available_modes=["BrewingMode", "StandBy"],
            mode=MachineMode.STANDBY,
            next_status=None,
            brewing_start_time=None,
        ),
        WidgetType.CM_COFFEE_BOILER: CoffeeBoiler(
            status="Ready",
            enabled=True,
            enabled_supported=False,
            target_temperature=90.0,
            target_temperature_min=80,
            target_temperature_max=100,
            target_temperature_step=0.1,
            ready_start_time=None,
        ),
        WidgetType.CM_STEAM_BOILER_TEMPERATURE: SteamBoilerTemperature(
            status="Ready",
            enabled=True,
            enabled_supported=True,
            target_temperature=125.0,
            target_temperature_supported=True,
            target_temperature_min=95,
            target_temperature_max=140,
            target_temperature_step=0.1,
            ready_start_time=None,
        ),
        WidgetType.CM_NO_WATER: NoWater(allarm=True),  # No water alarm
    }
    
    # Create machine with Cloud client
    machine = LaMarzoccoMachine("TEST123", cloud_client=mock_cloud_client)
    machine.dashboard = dashboard
    
    # Update status via Cloud
    await machine.update_status_cloud()
    
    # Verify status was set correctly
    assert machine.status is not None
    assert machine.status.power_on is False  # StandBy mode
    assert machine.status.coffee_boiler_enabled is True
    assert machine.status.coffee_target_temperature == 90.0
    assert machine.status.steam_boiler_enabled is True
    assert machine.status.steam_target_temperature == 125.0
    assert machine.status.water_reservoir_contact is False  # allarm=True means no water


async def test_machine_to_dict_includes_status() -> None:
    """Test that machine.to_dict includes status."""
    machine = LaMarzoccoMachine("TEST123")
    machine.status = MachineStatusSnapshot(
        power_on=True,
        coffee_boiler_enabled=True,
        coffee_target_temperature=94.0,
        steam_boiler_enabled=True,
        steam_target_temperature=131.0,
        water_reservoir_contact=True,
    )
    
    result = machine.to_dict()
    
    assert "status" in result
    assert result["status"]["power_on"] is True
    assert result["status"]["coffee_target_temperature"] == 94.0


async def test_machine_update_status_bluetooth_no_client() -> None:
    """Test that updating via Bluetooth without client raises error."""
    machine = LaMarzoccoMachine("TEST123")
    
    with pytest.raises(AttributeError, match="Bluetooth client not configured"):
        await machine.update_status_bluetooth()
