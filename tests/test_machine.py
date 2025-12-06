"""Test the machine module."""

from unittest.mock import MagicMock

import pytest

from pylamarzocco import (
    LaMarzoccoBluetoothClient,
    LaMarzoccoCloudClient,
    LaMarzoccoMachine,
)
from pylamarzocco.const import (
    BoilerType,
    DoseMode,
    ModelCode,
    SmartStandByType,
    SteamTargetLevel,
    WidgetType,
)
from pylamarzocco.exceptions import BluetoothConnectionFailed
from pylamarzocco.models import (
    BaseDoseSettings,
    BluetoothCommandStatus,
    BrewByWeightDoses,
    BrewByWeightDoseSettings,
)


@pytest.fixture(name="mock_bluetooth_client")
def mock_lm_bluetooth_client() -> MagicMock:
    """Mock the LaMarzoccoBluetoothClient."""

    client = MagicMock(spec=LaMarzoccoBluetoothClient)
    # Set up default return values for Bluetooth commands
    client.set_power.return_value = BluetoothCommandStatus(
        id="ble", message="power on", status="success"
    )
    client.set_steam.return_value = BluetoothCommandStatus(
        id="ble", message="boiler enable success", status="success"
    )
    client.set_temp.return_value = BluetoothCommandStatus(
        id="ble", message="Setting Temperature Success", status="success"
    )
    client.set_smart_standby.return_value = BluetoothCommandStatus(
        id="ble", message="Success", status="success"
    )
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


async def test_set_steam_temp(
    mock_machine: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
) -> None:
    """Test the set_steam_temp method."""
    mock_machine.dashboard.model_code = ModelCode.GS3
    assert await mock_machine.set_steam_target_temperature(124)
    mock_bluetooth_client.set_temp.assert_called_once_with(
        boiler=BoilerType.STEAM, temperature=124
    )


async def test_set_steam_temp_cloud_fallback(
    mock_machine: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
    mock_cloud_client: MagicMock,
) -> None:
    """Test the set_steam_temp method."""
    mock_machine.dashboard.model_code = ModelCode.GS3
    mock_bluetooth_client.set_temp.side_effect = BluetoothConnectionFailed(
        "Bluetooth error"
    )
    assert await mock_machine.set_steam_target_temperature(124)
    mock_cloud_client.set_steam_target_temperature.assert_called_once_with(
        serial_number="MR123456", target_temperature=124
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


async def test_set_brew_by_weight_dose_mode(
    mock_machine: LaMarzoccoMachine,
    mock_cloud_client: MagicMock,
) -> None:
    """Test the set_brew_by_weight_dose_mode method."""
    mock_machine.dashboard.model_code = ModelCode.LINEA_MINI_R
    mock_cloud_client.change_brew_by_weight_dose_mode.return_value = True

    assert await mock_machine.set_brew_by_weight_dose_mode(DoseMode.DOSE_1)
    mock_cloud_client.change_brew_by_weight_dose_mode.assert_called_once_with(
        "MR123456", DoseMode.DOSE_1
    )


async def test_set_brew_by_weight_dose(
    mock_machine: LaMarzoccoMachine,
    mock_cloud_client: MagicMock,
) -> None:
    """Test the set_brew_by_weight_dose method."""
    mock_machine.dashboard.model_code = ModelCode.LINEA_MINI_R
    mock_cloud_client.set_brew_by_weight_dose.return_value = True

    # Set up the dashboard with brew by weight widget
    mock_machine.dashboard.config[WidgetType.CM_BREW_BY_WEIGHT_DOSES] = (
        BrewByWeightDoses(
            mode=DoseMode.DOSE_1,
            doses=BrewByWeightDoseSettings(
                dose_1=BaseDoseSettings(
                    dose=32.0, dose_min=5, dose_max=100, dose_step=1
                ),
                dose_2=BaseDoseSettings(
                    dose=34.0, dose_min=5, dose_max=100, dose_step=1
                ),
            ),
        )
    )

    assert await mock_machine.set_brew_by_weight_dose(DoseMode.DOSE_1, 36.5)
    mock_cloud_client.set_brew_by_weight_dose.assert_called_once_with(
        "MR123456", 36.5, 34.0
    )
