"""Test Bluetooth dashboard functionality."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from pylamarzocco import LaMarzoccoBluetoothClient, LaMarzoccoMachine
from pylamarzocco.const import (
    BoilerType,
    MachineMode,
    SteamTargetLevel,
    WidgetType,
)
from pylamarzocco.exceptions import BluetoothConnectionFailed
from pylamarzocco.models import (
    BluetoothBoilerDetails,
    BluetoothCommandStatus,
    CoffeeBoiler,
    MachineStatus,
    SteamBoilerLevel,
    SteamBoilerTemperature,
)


@pytest.fixture(name="mock_bluetooth_client")
def mock_lm_bluetooth_client() -> MagicMock:
    """Mock the LaMarzoccoBluetoothClient."""
    client = MagicMock(spec=LaMarzoccoBluetoothClient)
    return client


@pytest.fixture(name="mock_machine_with_dashboard")
def mock_lm_machine_with_dashboard(
    mock_bluetooth_client: MagicMock,
) -> LaMarzoccoMachine:
    """Mock the LaMarzoccoMachine with dashboard populated."""
    machine = LaMarzoccoMachine(
        serial_number="MR123456",
        bluetooth_client=mock_bluetooth_client,
    )
    
    # Set up dashboard config with widgets
    machine.dashboard.config = {
        WidgetType.CM_MACHINE_STATUS: MachineStatus(
            status="StandBy",
            available_modes=[MachineMode.BREWING_MODE, MachineMode.STANDBY],
            mode=MachineMode.STANDBY,
            next_status=None,
            brewing_start_time=None,
        ),
        WidgetType.CM_COFFEE_BOILER: CoffeeBoiler(
            status="StandBy",
            enabled=True,
            enabled_supported=False,
            target_temperature=93.0,
            target_temperature_min=80,
            target_temperature_max=100,
            target_temperature_step=0.1,
            ready_start_time=None,
        ),
        WidgetType.CM_STEAM_BOILER_LEVEL: SteamBoilerLevel(
            status="StandBy",
            enabled=True,
            enabled_supported=True,
            target_level=SteamTargetLevel.LEVEL_1,
            target_level_supported=True,
            ready_start_time=None,
        ),
        WidgetType.CM_STEAM_BOILER_TEMPERATURE: SteamBoilerTemperature(
            status="StandBy",
            enabled=True,
            enabled_supported=False,
            target_temperature=126.0,
            target_temperature_min=126,
            target_temperature_max=131,
            target_temperature_step=1.0,
            target_temperature_supported=True,
            ready_start_time=None,
        ),
    }
    
    return machine


async def test_get_dashboard_from_bluetooth(
    mock_machine_with_dashboard: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
    snapshot,
) -> None:
    """Test filling dashboard from Bluetooth."""
    # Set up mock responses
    mock_bluetooth_client.get_machine_mode = AsyncMock(
        return_value=MachineMode.BREWING_MODE
    )
    mock_bluetooth_client.get_boilers = AsyncMock(
        return_value=[
            BluetoothBoilerDetails(
                id=BoilerType.COFFEE,
                is_enabled=True,
                target=95,
                current=94,
            ),
            BluetoothBoilerDetails(
                id=BoilerType.STEAM,
                is_enabled=False,
                target=128,
                current=50,
            ),
        ]
    )
    
    await mock_machine_with_dashboard.get_dashboard_from_bluetooth()
    
    # Verify calls
    mock_bluetooth_client.get_machine_mode.assert_called_once()
    mock_bluetooth_client.get_boilers.assert_called_once()
    
    # Verify dashboard was updated
    machine_status = mock_machine_with_dashboard.dashboard.config[
        WidgetType.CM_MACHINE_STATUS
    ]
    assert machine_status.mode == MachineMode.BREWING_MODE
    
    coffee_boiler = mock_machine_with_dashboard.dashboard.config[
        WidgetType.CM_COFFEE_BOILER
    ]
    assert coffee_boiler.enabled is True
    assert coffee_boiler.target_temperature == 95.0
    
    steam_level = mock_machine_with_dashboard.dashboard.config[
        WidgetType.CM_STEAM_BOILER_LEVEL
    ]
    assert steam_level.enabled is False
    
    steam_temp = mock_machine_with_dashboard.dashboard.config[
        WidgetType.CM_STEAM_BOILER_TEMPERATURE
    ]
    assert steam_temp.enabled is False
    assert steam_temp.target_temperature == 128.0
    
    # Snapshot test
    assert mock_machine_with_dashboard.dashboard.config == snapshot


async def test_get_dashboard_no_bluetooth(
    mock_machine_with_dashboard: LaMarzoccoMachine,
) -> None:
    """Test filling dashboard without Bluetooth client."""
    mock_machine_with_dashboard._bluetooth_client = None
    
    with pytest.raises(BluetoothConnectionFailed):
        await mock_machine_with_dashboard.get_dashboard_from_bluetooth()


async def test_get_dashboard_initializes_missing_widgets(
    mock_machine_with_dashboard: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
) -> None:
    """Test that get_dashboard_from_bluetooth initializes widgets if they don't exist."""
    # Clear the dashboard to simulate widgets not existing
    mock_machine_with_dashboard.dashboard.config.clear()
    
    # Set up mock responses
    mock_bluetooth_client.get_machine_mode = AsyncMock(
        return_value=MachineMode.BREWING_MODE
    )
    mock_bluetooth_client.get_boilers = AsyncMock(
        return_value=[
            BluetoothBoilerDetails(
                id=BoilerType.COFFEE,
                is_enabled=True,
                target=92,
                current=91,
            ),
            BluetoothBoilerDetails(
                id=BoilerType.STEAM,
                is_enabled=True,
                target=130,
                current=125,
            ),
        ]
    )
    
    await mock_machine_with_dashboard.get_dashboard_from_bluetooth()
    
    # Verify widgets were created
    assert WidgetType.CM_MACHINE_STATUS in mock_machine_with_dashboard.dashboard.config
    assert WidgetType.CM_COFFEE_BOILER in mock_machine_with_dashboard.dashboard.config
    assert WidgetType.CM_STEAM_BOILER_LEVEL in mock_machine_with_dashboard.dashboard.config
    assert WidgetType.CM_STEAM_BOILER_TEMPERATURE in mock_machine_with_dashboard.dashboard.config
    
    # Verify widgets have correct values from Bluetooth
    machine_status = mock_machine_with_dashboard.dashboard.config[WidgetType.CM_MACHINE_STATUS]
    assert machine_status.mode == MachineMode.BREWING_MODE
    
    coffee_boiler = mock_machine_with_dashboard.dashboard.config[WidgetType.CM_COFFEE_BOILER]
    assert coffee_boiler.enabled is True
    assert coffee_boiler.target_temperature == 92.0
    
    steam_level = mock_machine_with_dashboard.dashboard.config[WidgetType.CM_STEAM_BOILER_LEVEL]
    assert steam_level.enabled is True
    
    steam_temp = mock_machine_with_dashboard.dashboard.config[WidgetType.CM_STEAM_BOILER_TEMPERATURE]
    assert steam_temp.enabled is True
    assert steam_temp.target_temperature == 130.0


async def test_set_power_updates_dashboard(
    mock_machine_with_dashboard: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
    snapshot,
) -> None:
    """Test that set_power updates dashboard on success."""
    mock_bluetooth_client.set_power = AsyncMock(
        return_value=BluetoothCommandStatus(
            id="123", message="Success", status="success"
        )
    )
    
    result = await mock_machine_with_dashboard.set_power(True)
    
    assert result is True
    machine_status = mock_machine_with_dashboard.dashboard.config[
        WidgetType.CM_MACHINE_STATUS
    ]
    assert machine_status.mode == MachineMode.BREWING_MODE
    assert machine_status == snapshot


async def test_set_power_off_updates_dashboard(
    mock_machine_with_dashboard: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
) -> None:
    """Test that set_power(False) updates dashboard on success."""
    # First set to brewing mode
    mock_machine_with_dashboard.dashboard.config[
        WidgetType.CM_MACHINE_STATUS
    ].mode = MachineMode.BREWING_MODE
    
    mock_bluetooth_client.set_power = AsyncMock(
        return_value=BluetoothCommandStatus(
            id="123", message="Success", status="success"
        )
    )
    
    result = await mock_machine_with_dashboard.set_power(False)
    
    assert result is True
    machine_status = mock_machine_with_dashboard.dashboard.config[
        WidgetType.CM_MACHINE_STATUS
    ]
    assert machine_status.mode == MachineMode.STANDBY


async def test_set_steam_updates_dashboard(
    mock_machine_with_dashboard: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
) -> None:
    """Test that set_steam updates dashboard on success."""
    mock_bluetooth_client.set_steam = AsyncMock(
        return_value=BluetoothCommandStatus(
            id="123", message="Success", status="success"
        )
    )
    
    result = await mock_machine_with_dashboard.set_steam(False)
    
    assert result is True
    steam_level = mock_machine_with_dashboard.dashboard.config[
        WidgetType.CM_STEAM_BOILER_LEVEL
    ]
    assert steam_level.enabled is False
    
    steam_temp = mock_machine_with_dashboard.dashboard.config[
        WidgetType.CM_STEAM_BOILER_TEMPERATURE
    ]
    assert steam_temp.enabled is False


async def test_set_coffee_temp_updates_dashboard(
    mock_machine_with_dashboard: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
    snapshot,
) -> None:
    """Test that set_coffee_target_temperature updates dashboard on success."""
    mock_bluetooth_client.set_temp = AsyncMock(
        return_value=BluetoothCommandStatus(
            id="123", message="Success", status="success"
        )
    )
    
    result = await mock_machine_with_dashboard.set_coffee_target_temperature(96.5)
    
    assert result is True
    coffee_boiler = mock_machine_with_dashboard.dashboard.config[
        WidgetType.CM_COFFEE_BOILER
    ]
    assert coffee_boiler.target_temperature == 96.5
    assert coffee_boiler == snapshot


async def test_set_steam_temp_updates_dashboard(
    mock_machine_with_dashboard: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
) -> None:
    """Test that set_steam_level updates dashboard on success."""
    mock_bluetooth_client.set_temp = AsyncMock(
        return_value=BluetoothCommandStatus(
            id="123", message="Success", status="success"
        )
    )
    
    # Call set_steam_level which uses set_temp for steam boiler
    result = await mock_machine_with_dashboard.set_steam_level(SteamTargetLevel.LEVEL_3)
    
    assert result is True
    steam_temp = mock_machine_with_dashboard.dashboard.config[
        WidgetType.CM_STEAM_BOILER_TEMPERATURE
    ]
    assert steam_temp.target_temperature == 131.0


async def test_failed_command_does_not_update_dashboard(
    mock_machine_with_dashboard: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
) -> None:
    """Test that failed commands don't update dashboard."""
    original_mode = mock_machine_with_dashboard.dashboard.config[
        WidgetType.CM_MACHINE_STATUS
    ].mode
    
    mock_bluetooth_client.set_power = AsyncMock(
        return_value=BluetoothCommandStatus(
            id="123", message="Failed", status="error"
        )
    )
    
    result = await mock_machine_with_dashboard.set_power(True)
    
    # Command returns False but doesn't raise exception
    assert result is False
    # Dashboard should not be updated
    machine_status = mock_machine_with_dashboard.dashboard.config[
        WidgetType.CM_MACHINE_STATUS
    ]
    assert machine_status.mode == original_mode


async def test_bluetooth_exception_does_not_update_dashboard(
    mock_machine_with_dashboard: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
) -> None:
    """Test that Bluetooth exceptions don't update dashboard."""
    original_temp = mock_machine_with_dashboard.dashboard.config[
        WidgetType.CM_COFFEE_BOILER
    ].target_temperature
    
    mock_bluetooth_client.set_temp = AsyncMock(
        side_effect=BluetoothConnectionFailed("Connection lost")
    )
    
    # This will fail and return False (no cloud client)
    result = await mock_machine_with_dashboard.set_coffee_target_temperature(96.5)
    
    assert result is False
    # Dashboard should not be updated
    coffee_boiler = mock_machine_with_dashboard.dashboard.config[
        WidgetType.CM_COFFEE_BOILER
    ]
    assert coffee_boiler.target_temperature == original_temp
