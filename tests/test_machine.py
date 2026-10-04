"""Test the machine module."""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from pylamarzocco import (
    LaMarzoccoBluetoothClient,
    LaMarzoccoCloudClient,
    LaMarzoccoMachine,
)
from pylamarzocco.const import (
    BluetoothBrewingState,
    BoilerType,
    DoseIndex,
    DoseMode,
    MachineMode,
    MachineState,
    ModelCode,
    SmartStandByType,
    SteamTargetLevel,
    WidgetType,
)
from pylamarzocco.exceptions import (
    BluetoothConnectionFailed,
    OperationNotAvailable,
    UnsupportedModel,
)
from pylamarzocco.models import (
    BaseDoseSettings,
    BluetoothBrewingData,
    BluetoothCommandStatus,
    BluetoothShotCounterUpdate,
    BrewByWeightDoses,
    BrewByWeightDoseSettings,
    DosePulsesType,
    DoseSettings,
    GroupDosesSettings,
    MachineStatus,
    ThingDashboardWebsocketConfig,
    Widget,
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


async def test_set_mode(
    mock_machine: LaMarzoccoMachine,
    mock_cloud_client: MagicMock,
) -> None:
    """Test the set_mode method."""
    mock_machine.dashboard.model_code = ModelCode.STRADA_X
    assert await mock_machine.set_mode(MachineMode.ECO_MODE)
    mock_cloud_client.set_mode.assert_called_once_with(
        "MR123456", MachineMode.ECO_MODE
    )


async def test_set_auto_flush(
    mock_machine: LaMarzoccoMachine,
    mock_cloud_client: MagicMock,
) -> None:
    """Test the set_auto_flush method."""
    mock_machine.dashboard.model_code = ModelCode.STRADA_X
    assert await mock_machine.set_auto_flush(False)
    mock_cloud_client.set_auto_flush.assert_called_once_with("MR123456", False)


async def test_set_steam_flush(
    mock_machine: LaMarzoccoMachine,
    mock_cloud_client: MagicMock,
) -> None:
    """Test the set_steam_flush method."""
    mock_machine.dashboard.model_code = ModelCode.STRADA_X
    assert await mock_machine.set_steam_flush(False)
    mock_cloud_client.set_steam_flush.assert_called_once_with("MR123456", False)


async def test_set_rinse_flush(
    mock_machine: LaMarzoccoMachine,
    mock_cloud_client: MagicMock,
) -> None:
    """Test the set_rinse_flush method."""
    mock_machine.dashboard.model_code = ModelCode.STRADA_X
    assert await mock_machine.set_rinse_flush(True)
    mock_cloud_client.set_rinse_flush.assert_called_once_with("MR123456", True)


async def test_set_hot_water_dose_enabled(
    mock_machine: LaMarzoccoMachine,
    mock_cloud_client: MagicMock,
) -> None:
    """Test the set_hot_water_dose_enabled method."""
    mock_machine.dashboard.model_code = ModelCode.STRADA_X
    assert await mock_machine.set_hot_water_dose_enabled(False)
    mock_cloud_client.set_hot_water_dose_enabled.assert_called_once_with(
        "MR123456", False
    )


async def test_set_cup_warmer(
    mock_machine: LaMarzoccoMachine,
    mock_cloud_client: MagicMock,
) -> None:
    """Test the set_cup_warmer method."""
    assert await mock_machine.set_cup_warmer(True)
    mock_cloud_client.set_cup_warmer.assert_called_once_with("MR123456", True)


async def test_set_group_mode(
    mock_machine: LaMarzoccoMachine,
    mock_cloud_client: MagicMock,
) -> None:
    """Test the set_group_mode method."""
    mock_machine.dashboard.model_code = ModelCode.STRADA_X
    assert await mock_machine.set_group_mode(MachineMode.BREWING_MODE)
    mock_cloud_client.set_group_mode.assert_called_once_with(
        "MR123456", MachineMode.BREWING_MODE, 1
    )


async def test_set_coffee_boiler(
    mock_machine: LaMarzoccoMachine,
    mock_cloud_client: MagicMock,
) -> None:
    """Test the set_coffee_boiler method."""
    mock_machine.dashboard.model_code = ModelCode.STRADA_X
    assert await mock_machine.set_coffee_boiler(True)
    mock_cloud_client.set_coffee_boiler.assert_called_once_with("MR123456", True, 1)


async def test_set_rinse_flush_time(
    mock_machine: LaMarzoccoMachine,
    mock_cloud_client: MagicMock,
) -> None:
    """Test the set_rinse_flush_time method."""
    mock_machine.dashboard.model_code = ModelCode.STRADA_X
    assert await mock_machine.set_rinse_flush_time(4.0)
    mock_cloud_client.set_rinse_flush_time.assert_called_once_with("MR123456", 4.0)


@pytest.mark.parametrize("model_code", (ModelCode.STRADA_X, ModelCode.GS3_AV))
async def test_set_hot_water_dose(
    mock_machine: LaMarzoccoMachine,
    mock_cloud_client: MagicMock,
    model_code: ModelCode,
) -> None:
    """Test the set_hot_water_dose method."""
    mock_machine.dashboard.model_code = model_code
    assert await mock_machine.set_hot_water_dose(8.0, DoseIndex.DOSE_A)
    mock_cloud_client.set_hot_water_dose.assert_called_once_with(
        "MR123456", 8.0, DoseIndex.DOSE_A
    )


@pytest.mark.parametrize("model_code", (ModelCode.STRADA_X, ModelCode.GS3_AV))
async def test_set_group_dose_mode(
    mock_machine: LaMarzoccoMachine,
    mock_cloud_client: MagicMock,
    model_code: ModelCode,
) -> None:
    """Test the set_group_dose_mode method."""
    mock_machine.dashboard.model_code = model_code
    assert await mock_machine.set_group_dose_mode(DoseMode.PULSES_TYPE)
    mock_cloud_client.set_group_dose_mode.assert_called_once_with(
        "MR123456", DoseMode.PULSES_TYPE, 1
    )


@pytest.mark.parametrize("model_code", (ModelCode.STRADA_X, ModelCode.GS3_AV))
async def test_set_group_dose(
    mock_machine: LaMarzoccoMachine,
    mock_cloud_client: MagicMock,
    model_code: ModelCode,
) -> None:
    """Test the set_group_dose method."""
    mock_machine.dashboard.model_code = model_code
    assert await mock_machine.set_group_dose(
        DoseMode.PULSES_TYPE, DoseIndex.DOSE_A, 36.0
    )
    mock_cloud_client.set_group_dose.assert_called_once_with(
        "MR123456", DoseMode.PULSES_TYPE, DoseIndex.DOSE_A, 36.0, 1
    )


async def test_set_brewing_pressure(
    mock_machine: LaMarzoccoMachine,
    mock_cloud_client: MagicMock,
) -> None:
    """Test the set_brewing_pressure method."""
    mock_machine.dashboard.model_code = ModelCode.STRADA_X
    assert await mock_machine.set_brewing_pressure(9.0)
    mock_cloud_client.set_brewing_pressure.assert_called_once_with("MR123456", 9.0, 1)


@pytest.mark.parametrize("model_code", (ModelCode.STRADA_X, ModelCode.GS3_AV))
async def test_set_continuous_dose_enabled(
    mock_machine: LaMarzoccoMachine,
    mock_cloud_client: MagicMock,
    model_code: ModelCode,
) -> None:
    """Test the set_continuous_dose_enabled method."""
    mock_machine.dashboard.model_code = model_code
    assert await mock_machine.set_continuous_dose_enabled(True)
    mock_cloud_client.set_continuous_dose_enabled.assert_called_once_with(
        "MR123456", True, 1
    )


@pytest.mark.parametrize("model_code", (ModelCode.STRADA_X, ModelCode.GS3_AV))
async def test_set_continuous_dose(
    mock_machine: LaMarzoccoMachine,
    mock_cloud_client: MagicMock,
    model_code: ModelCode,
) -> None:
    """Test the set_continuous_dose method."""
    mock_machine.dashboard.model_code = model_code
    assert await mock_machine.set_continuous_dose(3.0)
    mock_cloud_client.set_continuous_dose.assert_called_once_with("MR123456", 3.0, 1)


async def test_set_mirror_group1(
    mock_machine: LaMarzoccoMachine,
    mock_cloud_client: MagicMock,
) -> None:
    """Test the set_mirror_group1 method."""
    mock_machine.dashboard.model_code = ModelCode.STRADA_X
    assert await mock_machine.set_mirror_group1(True)
    mock_cloud_client.set_mirror_group1.assert_called_once_with("MR123456", True, 2)


async def test_set_mirror_group1_group_3(
    mock_machine: LaMarzoccoMachine,
    mock_cloud_client: MagicMock,
) -> None:
    """Test the set_mirror_group1 method accepts group 3."""
    mock_machine.dashboard.model_code = ModelCode.STRADA_X

    assert await mock_machine.set_mirror_group1(True, group_index=3)
    mock_cloud_client.set_mirror_group1.assert_called_once_with("MR123456", True, 3)


@pytest.mark.parametrize("group_index", (1, 4))
async def test_set_mirror_group1_invalid_group_index_raises(
    mock_machine: LaMarzoccoMachine,
    mock_cloud_client: MagicMock,
    group_index: int,
) -> None:
    """Test the set_mirror_group1 method rejects invalid group indices."""
    mock_machine.dashboard.model_code = ModelCode.STRADA_X

    with pytest.raises(ValueError):
        await mock_machine.set_mirror_group1(True, group_index=group_index)
    mock_cloud_client.set_mirror_group1.assert_not_called()


async def test_set_continuous_dose_gs3_mp_unsupported(
    mock_machine: LaMarzoccoMachine,
    mock_cloud_client: MagicMock,
) -> None:
    """Test the set_continuous_dose method remains gated on unsupported models."""
    mock_machine.dashboard.model_code = ModelCode.GS3_MP

    with pytest.raises(UnsupportedModel):
        await mock_machine.set_continuous_dose(3.0)
    mock_cloud_client.set_continuous_dose.assert_not_called()


async def test_set_plumb_in(
    mock_machine: LaMarzoccoMachine,
    mock_cloud_client: MagicMock,
) -> None:
    """Test the set_plumb_in method."""
    assert await mock_machine.set_plumb_in(True)
    mock_cloud_client.set_plumb_in.assert_called_once_with("MR123456", True)


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


def _set_group_doses(
    machine: LaMarzoccoMachine, group_doses: GroupDosesSettings
) -> None:
    """Attach a group-doses widget to the machine dashboard."""
    machine.dashboard.model_code = ModelCode.STRADA_X
    machine.dashboard.config[WidgetType.CM_GROUP_DOSES] = group_doses


async def test_set_group_dose_mode_unavailable_raises(
    mock_machine: LaMarzoccoMachine,
    mock_cloud_client: MagicMock,
) -> None:
    """A mode outside availableModes is rejected without calling the cloud."""
    _set_group_doses(
        mock_machine,
        GroupDosesSettings(
            available_modes=[DoseMode.MANUAL_TYPE],
            mode=DoseMode.MANUAL_TYPE,
            doses=DosePulsesType(),
        ),
    )

    with pytest.raises(OperationNotAvailable):
        await mock_machine.set_group_dose_mode(DoseMode.PROFILE_TYPE)
    mock_cloud_client.set_group_dose_mode.assert_not_called()


async def test_set_group_dose_mode_available_passes(
    mock_machine: LaMarzoccoMachine,
    mock_cloud_client: MagicMock,
) -> None:
    """A mode within availableModes is forwarded to the cloud."""
    _set_group_doses(
        mock_machine,
        GroupDosesSettings(
            available_modes=[DoseMode.MASS_TYPE, DoseMode.PULSES_TYPE],
            mode=DoseMode.MASS_TYPE,
            doses=DosePulsesType(),
        ),
    )

    assert await mock_machine.set_group_dose_mode(DoseMode.PULSES_TYPE)
    mock_cloud_client.set_group_dose_mode.assert_called_once_with(
        "MR123456", DoseMode.PULSES_TYPE, 1
    )


async def test_set_brewing_pressure_unsupported_raises(
    mock_machine: LaMarzoccoMachine,
    mock_cloud_client: MagicMock,
) -> None:
    """Brewing pressure is rejected when unsupported in the current mode."""
    _set_group_doses(
        mock_machine,
        GroupDosesSettings(
            mode=DoseMode.MANUAL_TYPE,
            doses=DosePulsesType(),
            brewing_pressure_supported=False,
        ),
    )

    with pytest.raises(OperationNotAvailable):
        await mock_machine.set_brewing_pressure(9.0)
    mock_cloud_client.set_brewing_pressure.assert_not_called()


async def test_set_brewing_pressure_supported_passes(
    mock_machine: LaMarzoccoMachine,
    mock_cloud_client: MagicMock,
) -> None:
    """Brewing pressure is forwarded when supported in the current mode."""
    _set_group_doses(
        mock_machine,
        GroupDosesSettings(
            mode=DoseMode.MASS_TYPE,
            doses=DosePulsesType(),
            brewing_pressure_supported=True,
        ),
    )

    assert await mock_machine.set_brewing_pressure(9.0)
    mock_cloud_client.set_brewing_pressure.assert_called_once_with("MR123456", 9.0, 1)


async def test_set_group_dose_inactive_mode_raises(
    mock_machine: LaMarzoccoMachine,
    mock_cloud_client: MagicMock,
) -> None:
    """Setting a dose for a mode with no populated doses is rejected."""
    _set_group_doses(
        mock_machine,
        GroupDosesSettings(
            mode=DoseMode.MANUAL_TYPE,
            doses=DosePulsesType(),
        ),
    )

    with pytest.raises(OperationNotAvailable):
        await mock_machine.set_group_dose(DoseMode.MASS_TYPE, DoseIndex.DOSE_A, 16.0)
    mock_cloud_client.set_group_dose.assert_not_called()


async def test_set_group_dose_unknown_index_raises(
    mock_machine: LaMarzoccoMachine,
    mock_cloud_client: MagicMock,
) -> None:
    """Setting a dose for an index not present in the active mode is rejected."""
    _set_group_doses(
        mock_machine,
        GroupDosesSettings(
            mode=DoseMode.MASS_TYPE,
            doses=DosePulsesType(
                mass_type=[
                    DoseSettings(
                        dose_index=DoseIndex.DOSE_A,
                        dose=16.0,
                        dose_min=0,
                        dose_max=800,
                        dose_step=0.1,
                    )
                ]
            ),
        ),
    )

    with pytest.raises(OperationNotAvailable):
        await mock_machine.set_group_dose(DoseMode.MASS_TYPE, DoseIndex.DOSE_B, 16.0)
    mock_cloud_client.set_group_dose.assert_not_called()


async def test_set_group_dose_active_passes(
    mock_machine: LaMarzoccoMachine,
    mock_cloud_client: MagicMock,
) -> None:
    """Setting a dose for an active mode and known index is forwarded."""
    group_doses = GroupDosesSettings(
        mode=DoseMode.MASS_TYPE,
        doses=DosePulsesType(
            mass_type=[
                DoseSettings(
                    dose_index=DoseIndex.DOSE_A,
                    dose=16.0,
                    dose_min=0,
                    dose_max=800,
                    dose_step=0.1,
                )
            ]
        ),
    )
    _set_group_doses(mock_machine, group_doses)

    assert await mock_machine.set_group_dose(
        DoseMode.MASS_TYPE, DoseIndex.DOSE_A, 18.0
    )
    mock_cloud_client.set_group_dose.assert_called_once_with(
        "MR123456", DoseMode.MASS_TYPE, DoseIndex.DOSE_A, 18.0, 1
    )
    assert group_doses.doses.mass_type[0].dose == 18.0


def _brewing_update(
    state: BluetoothBrewingState,
    timer_value: float | None = None,
    final_shot_time: float | None = None,
) -> BluetoothShotCounterUpdate:
    return BluetoothShotCounterUpdate(
        state=state,
        timer_value=timer_value,
        final_shot_time=final_shot_time,
        received_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        raw=BluetoothBrewingData(),
    )


def _machine_status(
    status: MachineState, brewing_start_time: datetime | None = None
) -> MachineStatus:
    return MachineStatus(
        status=status,
        available_modes=[MachineMode.BREWING_MODE, MachineMode.STANDBY],
        mode=MachineMode.BREWING_MODE,
        next_status=None,
        brewing_start_time=brewing_start_time,
    )


def _websocket_config(status: MachineStatus) -> ThingDashboardWebsocketConfig:
    return ThingDashboardWebsocketConfig(
        widgets=[Widget(code=WidgetType.CM_MACHINE_STATUS, index=1, output=status)],
        config={WidgetType.CM_MACHINE_STATUS: status},
        connected=True,
        connection_date=0,
        uuid="uuid",
        commands=[],
    )


async def test_connect_bluetooth_shot_counter(
    mock_machine: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
) -> None:
    """Test starting the shot counter doesn't depend on cloud data."""
    mock_bluetooth_client.start_shot_counter.return_value = True

    assert not mock_machine.dashboard.shot_counter_supported
    assert await mock_machine.connect_bluetooth_shot_counter() is True
    mock_bluetooth_client.start_shot_counter.assert_awaited_once()

    mock_bluetooth_client.start_shot_counter.return_value = False
    assert await mock_machine.connect_bluetooth_shot_counter() is False

    mock_machine._bluetooth_client = None  # pylint: disable=protected-access
    assert await mock_machine.connect_bluetooth_shot_counter() is False


async def test_register_bluetooth_connection_callback(
    mock_machine: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
) -> None:
    """Test connection callbacks are registered on the Bluetooth client."""
    callback = MagicMock()

    unregister = mock_machine.register_bluetooth_connection_callback(callback)

    mock_bluetooth_client.register_connection_callback.assert_called_once_with(callback)
    assert unregister is mock_bluetooth_client.register_connection_callback.return_value

    # without a Bluetooth client, registering is a no-op
    mock_machine._bluetooth_client = None  # pylint: disable=protected-access
    mock_machine.register_bluetooth_connection_callback(callback)()


async def test_shot_counter_overrides_machine_status(
    mock_machine: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
) -> None:
    """Test BLE brewing states override the machine status widget."""
    cloud_start = datetime(2026, 1, 1, 11, 0, 0, tzinfo=timezone.utc)
    status = _machine_status(MachineState.POWERED_ON, cloud_start)
    mock_machine.dashboard.config[WidgetType.CM_MACHINE_STATUS] = status
    callback = MagicMock()

    await mock_machine.connect_bluetooth_shot_counter(callback)
    on_update = mock_bluetooth_client.start_shot_counter.call_args.args[0]
    on_connection = mock_bluetooth_client.start_shot_counter.call_args.kwargs[
        "connection_callback"
    ]

    brewing = _brewing_update(BluetoothBrewingState.BREWING, timer_value=12.5)
    on_update(brewing)
    callback.assert_called_once_with(brewing)
    assert status.status == MachineState.BREWING
    assert status.brewing_start_time == brewing.received_at - timedelta(seconds=12.5)

    on_update(_brewing_update(BluetoothBrewingState.BREWING_STOPPED, None, 27.4))
    assert status.status == MachineState.POWERED_ON
    assert status.brewing_start_time == cloud_start
    assert mock_machine.last_shot_time == 27.4

    # a late cloud "Brewing" message after the BLE stop is overridden
    late = _machine_status(MachineState.BREWING, cloud_start)
    mock_machine._websocket_dashboard_update_received(  # pylint: disable=protected-access
        _websocket_config(late)
    )
    assert mock_machine.dashboard.config[WidgetType.CM_MACHINE_STATUS] is late
    assert late.status == MachineState.POWERED_ON

    # flushes keep non-brewing cloud states
    mock_machine._websocket_dashboard_update_received(  # pylint: disable=protected-access
        _websocket_config(standby := _machine_status(MachineState.STANDBY))
    )
    on_update(_brewing_update(BluetoothBrewingState.FLUSHED))
    assert standby.status == MachineState.STANDBY
    assert mock_machine.last_shot_time == 27.4

    # losing the connection restores the cloud state
    on_update(_brewing_update(BluetoothBrewingState.BREWING, timer_value=1))
    assert standby.status == MachineState.BREWING
    callback.reset_mock()
    on_connection(False)
    callback.assert_called_once_with(None)
    assert standby.status == MachineState.STANDBY
    assert standby.brewing_start_time is None
    assert mock_machine.ble_brewing_update is None


async def test_shot_counter_falls_back_to_websocket_callback(
    mock_machine: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
) -> None:
    """Test the dashboard update callback is used without a dedicated callback."""
    mock_machine.dashboard.config[WidgetType.CM_MACHINE_STATUS] = _machine_status(
        MachineState.POWERED_ON
    )
    update_callback = MagicMock()
    mock_machine._update_callback = update_callback  # pylint: disable=protected-access

    await mock_machine.connect_bluetooth_shot_counter()
    on_update = mock_bluetooth_client.start_shot_counter.call_args.args[0]
    on_update(_brewing_update(BluetoothBrewingState.BREWING, timer_value=3))

    update_callback.assert_called_once()
    config: ThingDashboardWebsocketConfig = update_callback.call_args.args[0]
    assert config.config[WidgetType.CM_MACHINE_STATUS].status == MachineState.BREWING


async def test_disconnect_bluetooth_shot_counter(
    mock_machine: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
) -> None:
    """Test stopping the shot counter restores the cloud state."""
    status = _machine_status(MachineState.POWERED_ON)
    mock_machine.dashboard.config[WidgetType.CM_MACHINE_STATUS] = status
    await mock_machine.connect_bluetooth_shot_counter()
    on_update = mock_bluetooth_client.start_shot_counter.call_args.args[0]
    on_update(_brewing_update(BluetoothBrewingState.BREWING, timer_value=3))
    assert status.status == MachineState.BREWING

    await mock_machine.disconnect_bluetooth_shot_counter()

    mock_bluetooth_client.stop_shot_counter.assert_awaited_once()
    assert status.status == MachineState.POWERED_ON
    assert mock_machine.ble_brewing_update is None


async def test_shot_counter_state_expires(
    mock_machine: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
) -> None:
    """Test a stale Bluetooth state falls back to the cloud state."""
    status = _machine_status(MachineState.POWERED_ON)
    mock_machine.dashboard.config[WidgetType.CM_MACHINE_STATUS] = status
    callback = MagicMock()
    with patch("pylamarzocco.devices._machine.BLE_BREWING_STATE_TIMEOUT", 0.02):
        await mock_machine.connect_bluetooth_shot_counter(callback)
        on_update = mock_bluetooth_client.start_shot_counter.call_args.args[0]
        on_update(_brewing_update(BluetoothBrewingState.BREWING, timer_value=3))
        await asyncio.sleep(0.01)
        # a new notification extends the lifetime
        on_update(_brewing_update(BluetoothBrewingState.BREWING, timer_value=4))
        await asyncio.sleep(0.015)
        assert status.status == MachineState.BREWING

        await asyncio.sleep(0.02)

    assert status.status == MachineState.POWERED_ON
    assert mock_machine.ble_brewing_update is None
    callback.assert_called_with(None)


def _mock_bluetooth_dashboard(client: MagicMock, mode: MachineMode) -> None:
    client.get_machine_mode.return_value = mode
    client.get_plumbed_in.return_value = False
    client.get_tank_status.return_value = True
    client.get_boilers.return_value = []


async def test_bluetooth_refresh_after_shot_replaces_cloud_status(
    mock_machine: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
) -> None:
    """Test a Bluetooth refresh during the override is kept after it expires."""
    status = _machine_status(MachineState.POWERED_ON)
    mock_machine.dashboard.config[WidgetType.CM_MACHINE_STATUS] = status
    _mock_bluetooth_dashboard(mock_bluetooth_client, MachineMode.STANDBY)
    with patch("pylamarzocco.devices._machine.BLE_BREWING_STATE_TIMEOUT", 0.02):
        await mock_machine.connect_bluetooth_shot_counter()
        on_update = mock_bluetooth_client.start_shot_counter.call_args.args[0]
        on_update(_brewing_update(BluetoothBrewingState.BREWING, timer_value=3))
        on_update(_brewing_update(BluetoothBrewingState.BREWING_STOPPED, None, 27.4))

        # the machine is put in standby and the widget is refreshed in place
        await mock_machine.get_dashboard_from_bluetooth()
        assert status.status == MachineState.STANDBY

        await asyncio.sleep(0.04)

    assert mock_machine.ble_brewing_update is None
    assert status.status == MachineState.STANDBY


async def test_bluetooth_refresh_while_brewing_keeps_cloud_start_time(
    mock_machine: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
) -> None:
    """Test a Bluetooth refresh during a shot doesn't keep its start time."""
    cloud_start = datetime(2026, 1, 1, 11, 0, 0, tzinfo=timezone.utc)
    status = _machine_status(MachineState.POWERED_ON, cloud_start)
    mock_machine.dashboard.config[WidgetType.CM_MACHINE_STATUS] = status
    _mock_bluetooth_dashboard(mock_bluetooth_client, MachineMode.BREWING_MODE)
    await mock_machine.connect_bluetooth_shot_counter()
    on_update = mock_bluetooth_client.start_shot_counter.call_args.args[0]
    on_update(_brewing_update(BluetoothBrewingState.BREWING, timer_value=3))

    await mock_machine.get_dashboard_from_bluetooth()
    assert status.status == MachineState.BREWING

    on_update(_brewing_update(BluetoothBrewingState.BREWING_STOPPED, None, 27.4))
    assert status.status == MachineState.POWERED_ON
    assert status.brewing_start_time == cloud_start
    await mock_machine.disconnect_bluetooth_shot_counter()
