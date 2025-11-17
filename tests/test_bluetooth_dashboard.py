"""Test Bluetooth dashboard functionality."""

from datetime import datetime, timezone
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from pylamarzocco import LaMarzoccoBluetoothClient, LaMarzoccoMachine
from pylamarzocco.const import (
    BoilerStatus,
    BoilerType,
    MachineMode,
    MachineState,
    ModelCode,
    ModelName,
    SteamTargetLevel,
    WidgetType,
)
from pylamarzocco.exceptions import BluetoothConnectionFailed
from pylamarzocco.models import (
    BluetoothBoilerDetails,
    BluetoothCommandStatus,
    BluetoothMachineCapabilities,
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

    # Mock the connection_date to a fixed value for snapshot tests
    machine.dashboard.connection_date = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    # Set up dashboard config with widgets
    machine.dashboard.config = {
        WidgetType.CM_MACHINE_STATUS: MachineStatus(
            status=MachineState.STANDBY,
            available_modes=[MachineMode.BREWING_MODE, MachineMode.STANDBY],
            mode=MachineMode.STANDBY,
            next_status=None,
            brewing_start_time=None,
        ),
        WidgetType.CM_COFFEE_BOILER: CoffeeBoiler(
            status=BoilerStatus.STAND_BY,
            enabled=True,
            enabled_supported=False,
            target_temperature=93.0,
            target_temperature_min=80,
            target_temperature_max=100,
            target_temperature_step=0.1,
            ready_start_time=None,
        ),
        WidgetType.CM_STEAM_BOILER_LEVEL: SteamBoilerLevel(
            status=BoilerStatus.STAND_BY,
            enabled=True,
            enabled_supported=True,
            target_level=SteamTargetLevel.LEVEL_1,
            target_level_supported=True,
            ready_start_time=None,
        ),
        WidgetType.CM_STEAM_BOILER_TEMPERATURE: SteamBoilerTemperature(
            status=BoilerStatus.STAND_BY,
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
    snapshot: SnapshotAssertion,
) -> None:
    """Test filling dashboard from Bluetooth."""
    # Set up mock responses
    mock_bluetooth_client.get_machine_capabilities = AsyncMock(
        return_value=BluetoothMachineCapabilities(
            family=ModelName.LINEA_MICRA,
            groups_number=1,
            coffee_boilers_number=1,
            has_cup_warmer=False,
            steam_boilers_number=1,
            tea_doses_number=0,
            machine_modes=[MachineMode.BREWING_MODE, MachineMode.STANDBY],
            scheduling_type="weekly",
        )
    )
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

    # Verify calls - capabilities should NOT be called automatically anymore
    mock_bluetooth_client.get_machine_capabilities.assert_not_called()
    mock_bluetooth_client.get_machine_mode.assert_called_once()
    mock_bluetooth_client.get_boilers.assert_called_once()

    # Snapshot test includes model_name, model_code, and config
    assert mock_machine_with_dashboard.dashboard.to_dict() == snapshot

    # Verify dashboard was updated
    machine_status = cast(
        MachineStatus,
        mock_machine_with_dashboard.dashboard.config[WidgetType.CM_MACHINE_STATUS],
    )
    assert machine_status.mode == MachineMode.BREWING_MODE

    coffee_boiler = cast(
        CoffeeBoiler,
        mock_machine_with_dashboard.dashboard.config[WidgetType.CM_COFFEE_BOILER],
    )
    assert coffee_boiler.enabled is True
    assert coffee_boiler.target_temperature == 95.0

    # MICRA only has steam level widget, not temperature
    steam_level = cast(
        SteamBoilerLevel,
        mock_machine_with_dashboard.dashboard.config[WidgetType.CM_STEAM_BOILER_LEVEL],
    )
    assert steam_level.enabled is False

    # MICRA should NOT have steam temperature widget
    assert (
        WidgetType.CM_STEAM_BOILER_TEMPERATURE
        not in mock_machine_with_dashboard.dashboard.config
    )


async def test_get_dashboard_no_bluetooth(
    mock_machine_with_dashboard: LaMarzoccoMachine,
) -> None:
    """Test filling dashboard without Bluetooth client."""
    mock_machine_with_dashboard._bluetooth_client = None  # pylint:disable=W0212

    with pytest.raises(BluetoothConnectionFailed):
        await mock_machine_with_dashboard.get_dashboard_from_bluetooth()


async def test_get_model_info_from_bluetooth(
    mock_machine_with_dashboard: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
) -> None:
    """Test fetching model information from Bluetooth."""
    # Set up mock responses
    mock_bluetooth_client.get_machine_capabilities = AsyncMock(
        return_value=BluetoothMachineCapabilities(
            family=ModelName.GS3,
            groups_number=3,
            coffee_boilers_number=2,
            has_cup_warmer=True,
            steam_boilers_number=1,
            tea_doses_number=0,
            machine_modes=[MachineMode.BREWING_MODE, MachineMode.STANDBY],
            scheduling_type="weekly",
        )
    )

    # Call the method to fetch model info
    await mock_machine_with_dashboard.get_model_info_from_bluetooth()

    # Verify capabilities were called
    mock_bluetooth_client.get_machine_capabilities.assert_called_once()

    # Verify model info was set correctly
    assert mock_machine_with_dashboard.dashboard.model_name == ModelName.GS3
    assert mock_machine_with_dashboard.dashboard.model_code == ModelCode.GS3


async def test_get_dashboard_initializes_missing_widgets(
    mock_machine_with_dashboard: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that get_dashboard_from_bluetooth initializes widgets if they don't exist."""
    # Clear the dashboard to simulate widgets not existing
    mock_machine_with_dashboard.dashboard.config.clear()

    # Set up mock responses
    mock_bluetooth_client.get_machine_capabilities = AsyncMock(
        return_value=BluetoothMachineCapabilities(
            family=ModelName.LINEA_MINI_R,
            groups_number=1,
            coffee_boilers_number=1,
            has_cup_warmer=True,
            steam_boilers_number=1,
            tea_doses_number=0,
            machine_modes=[MachineMode.BREWING_MODE, MachineMode.STANDBY],
            scheduling_type="weekly",
        )
    )
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

    # First fetch model info explicitly
    await mock_machine_with_dashboard.get_model_info_from_bluetooth()

    # Then get dashboard
    await mock_machine_with_dashboard.get_dashboard_from_bluetooth()

    # Verify model_name and model_code were set from capabilities
    assert mock_machine_with_dashboard.dashboard.model_name == ModelName.LINEA_MINI_R
    assert mock_machine_with_dashboard.dashboard.model_code == ModelCode.LINEA_MINI_R

    # Verify widgets were created (Linea Mini R supports steam level, not temperature)
    assert WidgetType.CM_MACHINE_STATUS in mock_machine_with_dashboard.dashboard.config
    assert WidgetType.CM_COFFEE_BOILER in mock_machine_with_dashboard.dashboard.config
    assert (
        WidgetType.CM_STEAM_BOILER_LEVEL in mock_machine_with_dashboard.dashboard.config
    )
    assert (
        WidgetType.CM_STEAM_BOILER_TEMPERATURE
        not in mock_machine_with_dashboard.dashboard.config
    )

    # Verify widgets have correct values from Bluetooth
    assert mock_machine_with_dashboard.dashboard.to_dict() == snapshot


async def test_get_dashboard_without_steam_level_support(
    mock_machine_with_dashboard: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
) -> None:
    """Test that models without steam level support only get temperature widget."""
    # Clear the dashboard to simulate widgets not existing
    mock_machine_with_dashboard.dashboard.config.clear()

    # Set up mock responses for GS3 (does not support steam level)
    mock_bluetooth_client.get_machine_capabilities = AsyncMock(
        return_value=BluetoothMachineCapabilities(
            family=ModelName.GS3,
            groups_number=3,
            coffee_boilers_number=2,
            has_cup_warmer=True,
            steam_boilers_number=1,
            tea_doses_number=0,
            machine_modes=[MachineMode.BREWING_MODE, MachineMode.STANDBY],
            scheduling_type="weekly",
        )
    )
    mock_bluetooth_client.get_machine_mode = AsyncMock(
        return_value=MachineMode.BREWING_MODE
    )
    mock_bluetooth_client.get_boilers = AsyncMock(
        return_value=[
            BluetoothBoilerDetails(
                id=BoilerType.COFFEE,
                is_enabled=True,
                target=94,
                current=93,
            ),
            BluetoothBoilerDetails(
                id=BoilerType.STEAM,
                is_enabled=True,
                target=128,
                current=120,
            ),
        ]
    )

    # First fetch model info explicitly
    await mock_machine_with_dashboard.get_model_info_from_bluetooth()

    # Then get dashboard
    await mock_machine_with_dashboard.get_dashboard_from_bluetooth()

    # Verify model_name and model_code were set from capabilities
    assert mock_machine_with_dashboard.dashboard.model_name == ModelName.GS3
    assert mock_machine_with_dashboard.dashboard.model_code == ModelCode.GS3

    # Verify widgets were created - GS3 should NOT have steam level widget
    assert WidgetType.CM_MACHINE_STATUS in mock_machine_with_dashboard.dashboard.config
    assert WidgetType.CM_COFFEE_BOILER in mock_machine_with_dashboard.dashboard.config
    assert (
        WidgetType.CM_STEAM_BOILER_LEVEL
        not in mock_machine_with_dashboard.dashboard.config
    )
    assert (
        WidgetType.CM_STEAM_BOILER_TEMPERATURE
        in mock_machine_with_dashboard.dashboard.config
    )

    # Verify temperature widget has correct values
    steam_temp = cast(
        SteamBoilerTemperature,
        mock_machine_with_dashboard.dashboard.config[
            WidgetType.CM_STEAM_BOILER_TEMPERATURE
        ],
    )
    assert steam_temp.enabled is True
    assert steam_temp.target_temperature == 128.0


async def test_get_dashboard_mini_original_temperature_only(
    mock_machine_with_dashboard: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
) -> None:
    """Test that original Linea Mini (without R) only gets temperature widget."""
    # Clear the dashboard to simulate widgets not existing
    mock_machine_with_dashboard.dashboard.config.clear()

    # Set up mock responses for original Linea Mini
    mock_bluetooth_client.get_machine_capabilities = AsyncMock(
        return_value=BluetoothMachineCapabilities(
            family=ModelName.LINEA_MINI,
            groups_number=1,
            coffee_boilers_number=1,
            has_cup_warmer=False,
            steam_boilers_number=1,
            tea_doses_number=0,
            machine_modes=[MachineMode.BREWING_MODE, MachineMode.STANDBY],
            scheduling_type="weekly",
        )
    )
    mock_bluetooth_client.get_machine_mode = AsyncMock(
        return_value=MachineMode.BREWING_MODE
    )
    mock_bluetooth_client.get_boilers = AsyncMock(
        return_value=[
            BluetoothBoilerDetails(
                id=BoilerType.COFFEE,
                is_enabled=True,
                target=93,
                current=92,
            ),
            BluetoothBoilerDetails(
                id=BoilerType.STEAM,
                is_enabled=True,
                target=127,
                current=115,
            ),
        ]
    )

    # First fetch model info explicitly
    await mock_machine_with_dashboard.get_model_info_from_bluetooth()

    # Then get dashboard
    await mock_machine_with_dashboard.get_dashboard_from_bluetooth()

    # Verify model_name and model_code were set from capabilities
    assert mock_machine_with_dashboard.dashboard.model_name == ModelName.LINEA_MINI
    assert mock_machine_with_dashboard.dashboard.model_code == ModelCode.LINEA_MINI

    # Verify widgets - original Mini should NOT have steam level, only temperature
    assert WidgetType.CM_MACHINE_STATUS in mock_machine_with_dashboard.dashboard.config
    assert WidgetType.CM_COFFEE_BOILER in mock_machine_with_dashboard.dashboard.config
    assert (
        WidgetType.CM_STEAM_BOILER_LEVEL
        not in mock_machine_with_dashboard.dashboard.config
    )
    assert (
        WidgetType.CM_STEAM_BOILER_TEMPERATURE
        in mock_machine_with_dashboard.dashboard.config
    )

    # Verify temperature widget has correct values
    steam_temp = cast(
        SteamBoilerTemperature,
        mock_machine_with_dashboard.dashboard.config[
            WidgetType.CM_STEAM_BOILER_TEMPERATURE
        ],
    )
    assert steam_temp.enabled is True
    assert steam_temp.target_temperature == 127.0


async def test_set_power_updates_dashboard(
    mock_machine_with_dashboard: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that set_power updates dashboard on success."""
    mock_bluetooth_client.set_power = AsyncMock(
        return_value=BluetoothCommandStatus(
            id="ble", message="power on", status="success"
        )
    )

    result = await mock_machine_with_dashboard.set_power(True)

    assert result is True
    machine_status = cast(
        MachineStatus,
        mock_machine_with_dashboard.dashboard.config[WidgetType.CM_MACHINE_STATUS],
    )
    assert machine_status.mode == MachineMode.BREWING_MODE
    assert machine_status.to_dict() == snapshot


async def test_set_power_off_updates_dashboard(
    mock_machine_with_dashboard: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
) -> None:
    """Test that set_power(False) updates dashboard on success."""
    # First set to brewing mode
    machine_status_temp = cast(
        MachineStatus,
        mock_machine_with_dashboard.dashboard.config[WidgetType.CM_MACHINE_STATUS],
    )
    machine_status_temp.mode = MachineMode.BREWING_MODE

    mock_bluetooth_client.set_power = AsyncMock(
        return_value=BluetoothCommandStatus(
            id="ble", message="power on", status="success"
        )
    )

    result = await mock_machine_with_dashboard.set_power(False)

    assert result is True
    machine_status = cast(
        MachineStatus,
        mock_machine_with_dashboard.dashboard.config[WidgetType.CM_MACHINE_STATUS],
    )
    assert machine_status.mode == MachineMode.STANDBY


async def test_set_steam_updates_dashboard(
    mock_machine_with_dashboard: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
) -> None:
    """Test that set_steam updates dashboard on success."""
    mock_bluetooth_client.set_steam = AsyncMock(
        return_value=BluetoothCommandStatus(
            id="ble", message="boiler enable success", status="success"
        )
    )

    result = await mock_machine_with_dashboard.set_steam(False)

    assert result is True
    steam_level = cast(
        SteamBoilerLevel,
        mock_machine_with_dashboard.dashboard.config[WidgetType.CM_STEAM_BOILER_LEVEL],
    )
    assert steam_level.enabled is False

    steam_temp = cast(
        SteamBoilerTemperature,
        mock_machine_with_dashboard.dashboard.config[
            WidgetType.CM_STEAM_BOILER_TEMPERATURE
        ],
    )
    assert steam_temp.enabled is False


async def test_set_coffee_temp_updates_dashboard(
    mock_machine_with_dashboard: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that set_coffee_target_temperature updates dashboard on success."""
    mock_bluetooth_client.set_temp = AsyncMock(
        return_value=BluetoothCommandStatus(
            id="ble", message="Setting Temperature Success", status="success"
        )
    )

    result = await mock_machine_with_dashboard.set_coffee_target_temperature(96.5)

    assert result is True
    coffee_boiler = cast(
        CoffeeBoiler,
        mock_machine_with_dashboard.dashboard.config[WidgetType.CM_COFFEE_BOILER],
    )
    assert coffee_boiler.target_temperature == 96.5
    assert coffee_boiler.to_dict() == snapshot


async def test_set_steam_temp_updates_dashboard(
    mock_machine_with_dashboard: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
) -> None:
    """Test that set_steam_level updates dashboard on success."""
    mock_bluetooth_client.set_temp = AsyncMock(
        return_value=BluetoothCommandStatus(
            id="ble", message="Setting Temperature Success", status="success"
        )
    )

    # Call set_steam_level which uses set_temp for steam boiler
    result = await mock_machine_with_dashboard.set_steam_level(SteamTargetLevel.LEVEL_3)

    assert result is True
    steam_temp = cast(
        SteamBoilerTemperature,
        mock_machine_with_dashboard.dashboard.config[
            WidgetType.CM_STEAM_BOILER_TEMPERATURE
        ],
    )
    assert steam_temp.target_temperature == 131.0


async def test_failed_command_does_not_update_dashboard(
    mock_machine_with_dashboard: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
) -> None:
    """Test that failed commands don't update dashboard."""
    machine_status_orig = cast(
        MachineStatus,
        mock_machine_with_dashboard.dashboard.config[WidgetType.CM_MACHINE_STATUS],
    )
    original_mode = machine_status_orig.mode

    mock_bluetooth_client.set_power = AsyncMock(
        return_value=BluetoothCommandStatus(id="ble", message="Failed", status="error")
    )

    result = await mock_machine_with_dashboard.set_power(True)

    # Command returns False but doesn't raise exception
    assert result is False
    # Dashboard should not be updated
    machine_status = cast(
        MachineStatus,
        mock_machine_with_dashboard.dashboard.config[WidgetType.CM_MACHINE_STATUS],
    )
    assert machine_status.mode == original_mode


async def test_bluetooth_exception_does_not_update_dashboard(
    mock_machine_with_dashboard: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
) -> None:
    """Test that Bluetooth exceptions don't update dashboard."""
    coffee_boiler_orig = cast(
        CoffeeBoiler,
        mock_machine_with_dashboard.dashboard.config[WidgetType.CM_COFFEE_BOILER],
    )
    original_temp = coffee_boiler_orig.target_temperature

    mock_bluetooth_client.set_temp = AsyncMock(
        side_effect=BluetoothConnectionFailed("Connection lost")
    )

    # This will fail and return False (no cloud client)
    result = await mock_machine_with_dashboard.set_coffee_target_temperature(96.5)

    assert result is False
    # Dashboard should not be updated
    coffee_boiler = cast(
        CoffeeBoiler,
        mock_machine_with_dashboard.dashboard.config[WidgetType.CM_COFFEE_BOILER],
    )
    assert coffee_boiler.target_temperature == original_temp
