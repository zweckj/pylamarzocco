"""Test the machine module."""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from bleak.exc import BleakError

from pylamarzocco import LaMarzoccoMachine
from pylamarzocco.const import (
    BluetoothBrewingState,
    BoilerType,
    DoseIndex,
    DoseMode,
    MachineMode,
    MachineState,
    ModelCode,
    PreExtractionMode,
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
    BluetoothMachineTelemetry,
    BluetoothShotCounterUpdate,
    BrewByWeightDoses,
    BrewByWeightDoseSettings,
    DosePulsesType,
    DoseSettings,
    GroupDosesSettings,
    PrebrewSettingTimes,
    SecondsInOut,
    ThingDashboardWebsocketConfig,
)

from .conftest import machine_status, websocket_config


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


async def test_shot_counter_overridesmachine_status(
    mock_machine: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
) -> None:
    """Test BLE brewing states override the machine status widget."""
    cloud_start = datetime(2026, 1, 1, 11, 0, 0, tzinfo=timezone.utc)
    status = machine_status(MachineState.POWERED_ON, cloud_start)
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
    late = machine_status(MachineState.BREWING, cloud_start)
    mock_machine._websocket_dashboard_update_received(  # pylint: disable=protected-access
        websocket_config(late)
    )
    assert mock_machine.dashboard.config[WidgetType.CM_MACHINE_STATUS] is late
    assert late.status == MachineState.POWERED_ON

    # flushes keep non-brewing cloud states
    mock_machine._websocket_dashboard_update_received(  # pylint: disable=protected-access
        websocket_config(standby := machine_status(MachineState.STANDBY))
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
    mock_machine.dashboard.config[WidgetType.CM_MACHINE_STATUS] = machine_status(
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
    """Test stopping the shot counter restores the cloud state without callbacks."""
    status = machine_status(MachineState.POWERED_ON)
    mock_machine.dashboard.config[WidgetType.CM_MACHINE_STATUS] = status
    callback = MagicMock()
    await mock_machine.connect_bluetooth_shot_counter(callback)
    on_update = mock_bluetooth_client.start_shot_counter.call_args.args[0]
    on_connection = mock_bluetooth_client.start_shot_counter.call_args.kwargs[
        "connection_callback"
    ]
    on_telemetry = mock_bluetooth_client.start_shot_counter.call_args.kwargs[
        "telemetry_callback"
    ]
    # like the client, stopping reports the shot counter as disconnected
    mock_bluetooth_client.stop_shot_counter.side_effect = lambda: on_connection(False)
    on_update(_brewing_update(BluetoothBrewingState.BREWING, timer_value=3))
    on_telemetry(BluetoothMachineTelemetry(coffee_boiler_temperature=93))
    assert status.status == MachineState.BREWING
    callback.reset_mock()

    await mock_machine.disconnect_bluetooth_shot_counter()

    mock_bluetooth_client.stop_shot_counter.assert_awaited_once()
    callback.assert_not_called()
    assert status.status == MachineState.POWERED_ON
    assert mock_machine.ble_brewing_update is None
    assert mock_machine.bluetooth_telemetry == BluetoothMachineTelemetry()


async def test_shot_counter_state_expires(
    mock_machine: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
) -> None:
    """Test a stale Bluetooth state falls back to the cloud state."""
    status = machine_status(MachineState.POWERED_ON)
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
    status = machine_status(MachineState.POWERED_ON)
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
    status = machine_status(MachineState.POWERED_ON, cloud_start)
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


async def test_bluetooth_telemetry(
    mock_machine: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
) -> None:
    """Test live values are kept and the machine mode is applied right away."""
    status = machine_status(MachineState.POWERED_ON)
    mock_machine.dashboard.config[WidgetType.CM_MACHINE_STATUS] = status
    callback = MagicMock()
    telemetry_callback = MagicMock()
    await mock_machine.connect_bluetooth_shot_counter(callback, telemetry_callback)
    on_telemetry = mock_bluetooth_client.start_shot_counter.call_args.kwargs[
        "telemetry_callback"
    ]
    on_connection = mock_bluetooth_client.start_shot_counter.call_args.kwargs[
        "connection_callback"
    ]

    steam = BluetoothMachineTelemetry(steam_boiler_temperature=130)
    on_telemetry(steam)
    telemetry_callback.assert_called_once_with(steam)
    assert status.mode == MachineMode.BREWING_MODE

    standby = BluetoothMachineTelemetry(
        machine_mode=MachineMode.STANDBY, sleep="command"
    )
    on_telemetry(standby)
    telemetry_callback.assert_called_with(standby)
    callback.assert_not_called()
    assert (status.mode, status.status) == (MachineMode.STANDBY, MachineState.STANDBY)
    assert mock_machine.bluetooth_telemetry == BluetoothMachineTelemetry(
        steam_boiler_temperature=130, machine_mode=MachineMode.STANDBY, sleep="command"
    )

    # the live values are dropped with the connection
    on_connection(False)
    assert mock_machine.bluetooth_telemetry == BluetoothMachineTelemetry()


async def test_bluetooth_machine_mode_during_shot(
    mock_machine: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
) -> None:
    """Test a machine mode received while brewing is kept once the shot ends."""
    status = machine_status(MachineState.POWERED_ON)
    mock_machine.dashboard.config[WidgetType.CM_MACHINE_STATUS] = status
    await mock_machine.connect_bluetooth_shot_counter(MagicMock(), MagicMock())
    on_update = mock_bluetooth_client.start_shot_counter.call_args.args[0]
    on_telemetry = mock_bluetooth_client.start_shot_counter.call_args.kwargs[
        "telemetry_callback"
    ]

    on_update(_brewing_update(BluetoothBrewingState.BREWING, timer_value=3))
    on_telemetry(BluetoothMachineTelemetry(machine_mode=MachineMode.ECO_MODE))
    assert status.status == MachineState.BREWING

    on_update(_brewing_update(BluetoothBrewingState.FLUSHED))
    assert (status.mode, status.status) == (MachineMode.ECO_MODE, MachineState.ECO_MODE)


async def test_bluetooth_machine_mode_falls_back_to_websocket_callback(
    mock_machine: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
) -> None:
    """Test machine mode changes use the dashboard callback without a callback."""
    mock_machine.dashboard.config[WidgetType.CM_MACHINE_STATUS] = machine_status(
        MachineState.POWERED_ON
    )
    update_callback = MagicMock()
    mock_machine._update_callback = update_callback  # pylint: disable=protected-access
    await mock_machine.connect_bluetooth_shot_counter()
    on_telemetry = mock_bluetooth_client.start_shot_counter.call_args.kwargs[
        "telemetry_callback"
    ]

    on_telemetry(BluetoothMachineTelemetry(coffee_boiler_temperature=93))
    update_callback.assert_not_called()

    on_telemetry(BluetoothMachineTelemetry(machine_mode=MachineMode.STANDBY))
    update_callback.assert_called_once()
    config: ThingDashboardWebsocketConfig = update_callback.call_args.args[0]
    assert config.config[WidgetType.CM_MACHINE_STATUS].mode == MachineMode.STANDBY


async def test_bluetooth_shot_counter_active(
    mock_machine: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
) -> None:
    """Test the shot counter state is taken from the Bluetooth client."""
    mock_bluetooth_client.shot_counter_active = True
    assert mock_machine.bluetooth_shot_counter_active
    mock_bluetooth_client.shot_counter_active = False
    assert not mock_machine.bluetooth_shot_counter_active
    assert not LaMarzoccoMachine("MR123456").bluetooth_shot_counter_active


async def test_get_schedule(
    mock_machine: LaMarzoccoMachine,
    mock_cloud_client: MagicMock,
) -> None:
    """Test getting the schedule."""
    schedule = MagicMock()
    mock_cloud_client.get_thing_schedule.return_value = schedule
    await mock_machine.get_schedule()
    mock_cloud_client.get_thing_schedule.assert_called_once_with("MR123456")
    assert mock_machine.schedule is schedule


async def test_get_model_info_from_bluetooth_errors(
    mock_machine: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
) -> None:
    """Test errors while fetching the model info from Bluetooth."""
    with pytest.raises(BluetoothConnectionFailed):
        await LaMarzoccoMachine("MR123456").get_model_info_from_bluetooth()

    mock_bluetooth_client.get_machine_capabilities.side_effect = BleakError("boom")
    with pytest.raises(BleakError):
        await mock_machine.get_model_info_from_bluetooth()


async def test_get_model_info_from_bluetooth_unknown_model(
    mock_machine: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
) -> None:
    """Test an unknown model family keeps the model code."""
    family = MagicMock()
    family.name = "UNKNOWN"
    mock_bluetooth_client.get_machine_capabilities.return_value = MagicMock(
        family=family
    )
    model_code = mock_machine.dashboard.model_code
    await mock_machine.get_model_info_from_bluetooth()
    assert mock_machine.dashboard.model_name is family
    assert mock_machine.dashboard.model_code == model_code


async def test_get_dashboard_from_bluetooth_error(
    mock_machine: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
) -> None:
    """Test a Bluetooth error while fetching the dashboard is raised."""
    mock_bluetooth_client.get_machine_mode.side_effect = BleakError("boom")
    with pytest.raises(BleakError):
        await mock_machine.get_dashboard_from_bluetooth()


async def test_set_power_updates_group_status(
    mock_machine: LaMarzoccoMachine,
) -> None:
    """Test setting the power updates the group status widget."""
    group_status = MagicMock()
    mock_machine.dashboard.config[WidgetType.CM_MACHINE_GROUP_STATUS] = group_status
    assert await mock_machine.set_power(False)
    assert group_status.mode is MachineMode.STANDBY


async def test_set_mode_failed_keeps_widgets(
    mock_machine: LaMarzoccoMachine,
    mock_cloud_client: MagicMock,
) -> None:
    """Test a failed set_mode does not touch the dashboard."""
    mock_machine.dashboard.model_code = ModelCode.STRADA_X
    machine_status = MagicMock()
    machine_status.mode = MachineMode.STANDBY
    mock_machine.dashboard.config[WidgetType.CM_MACHINE_STATUS] = machine_status
    mock_cloud_client.set_mode.return_value = False
    assert not await mock_machine.set_mode(MachineMode.ECO_MODE)
    assert machine_status.mode is MachineMode.STANDBY


@pytest.mark.parametrize(
    ("method", "args", "widget_type", "attribute", "value"),
    [
        ("set_auto_flush", (True,), WidgetType.CM_AUTO_FLUSH, "enabled", True),
        ("set_steam_flush", (True,), WidgetType.CM_STEAM_FLUSH, "enabled", True),
        ("set_rinse_flush", (True,), WidgetType.CM_RINSE_FLUSH, "enabled", True),
        (
            "set_hot_water_dose_enabled",
            (True,),
            WidgetType.CM_HOT_WATER_DOSE,
            "enabled",
            True,
        ),
        (
            "set_group_mode",
            (MachineMode.ECO_MODE,),
            WidgetType.CM_MACHINE_GROUP_STATUS,
            "mode",
            MachineMode.ECO_MODE,
        ),
        ("set_coffee_boiler", (True,), WidgetType.CM_COFFEE_BOILER, "enabled", True),
        (
            "set_rinse_flush_time",
            (4.5,),
            WidgetType.CM_RINSE_FLUSH,
            "time_seconds",
            4.5,
        ),
    ],
)
async def test_strada_x_commands_update_dashboard(
    mock_machine: LaMarzoccoMachine,
    method: str,
    args: tuple,
    widget_type: WidgetType,
    attribute: str,
    value: object,
) -> None:
    """Test Strada X commands update the dashboard widget."""
    mock_machine.dashboard.model_code = ModelCode.STRADA_X
    widget = MagicMock()
    mock_machine.dashboard.config[widget_type] = widget
    assert await getattr(mock_machine, method)(*args)
    assert getattr(widget, attribute) == value


async def test_set_hot_water_dose_updates_dashboard(
    mock_machine: LaMarzoccoMachine,
) -> None:
    """Test setting the hot water dose updates the matching dose."""
    mock_machine.dashboard.model_code = ModelCode.STRADA_X
    dose_a = MagicMock(dose_index=DoseIndex.DOSE_A, dose=10)
    dose_b = MagicMock(dose_index=DoseIndex.DOSE_B, dose=20)
    mock_machine.dashboard.config[WidgetType.CM_HOT_WATER_DOSE] = MagicMock(
        doses=[dose_a, dose_b]
    )
    assert await mock_machine.set_hot_water_dose(15, DoseIndex.DOSE_B)
    assert dose_a.dose == 10
    assert dose_b.dose == 15


async def test_start_backflush(
    mock_machine: LaMarzoccoMachine,
    mock_cloud_client: MagicMock,
) -> None:
    """Test starting the backflush."""
    assert await mock_machine.start_backflush()
    mock_cloud_client.start_backflush_cleaning.assert_called_once_with("MR123456")


async def test_set_pre_extraction_mode(
    mock_machine: LaMarzoccoMachine,
    mock_cloud_client: MagicMock,
) -> None:
    """Test setting the pre-extraction mode."""
    assert await mock_machine.set_pre_extraction_mode(PreExtractionMode.PREBREWING)
    mock_cloud_client.change_pre_extraction_mode.assert_called_once_with(
        "MR123456", PreExtractionMode.PREBREWING
    )


async def test_set_pre_extraction_times(
    mock_machine: LaMarzoccoMachine,
    mock_cloud_client: MagicMock,
) -> None:
    """Test setting the pre-extraction times."""
    assert await mock_machine.set_pre_extraction_times(2.0, 3.5)
    mock_cloud_client.change_pre_extraction_times.assert_called_once_with(
        "MR123456",
        PrebrewSettingTimes(times=SecondsInOut(seconds_in=2.0, seconds_out=3.5)),
    )


@pytest.mark.parametrize(
    ("enabled", "minutes", "expected"),
    [(True, 90, "01:30"), (False, 90, "Off")],
)
async def test_set_smart_standby_auto_standby(
    mock_machine: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
    mock_cloud_client: MagicMock,
    enabled: bool,
    minutes: int,
    expected: str,
) -> None:
    """Test smart standby uses auto standby when the schedule supports it."""
    mock_machine.schedule.auto_stand_by_supported = True
    assert await mock_machine.set_smart_standby(
        enabled, minutes, SmartStandByType.POWER_ON
    )
    mock_cloud_client.set_auto_standby.assert_called_once_with("MR123456", expected)
    mock_bluetooth_client.set_smart_standby.assert_not_called()


async def test_set_auto_on_off(
    mock_machine: LaMarzoccoMachine,
    mock_cloud_client: MagicMock,
) -> None:
    """Test setting auto on off."""
    assert await mock_machine.set_auto_on_off("schedule")
    mock_cloud_client.set_auto_on_off.assert_called_once_with("MR123456", "schedule")


async def test_wakeup_schedule(
    mock_machine: LaMarzoccoMachine,
    mock_cloud_client: MagicMock,
) -> None:
    """Test setting and deleting a wake up schedule."""
    schedule = MagicMock()
    assert await mock_machine.set_wakeup_schedule(schedule)
    mock_cloud_client.set_wakeup_schedule.assert_called_once_with(
        "MR123456", schedule
    )
    assert await mock_machine.delete_wakeup_schedule("schedule-id")
    mock_cloud_client.delete_wakeup_schedule.assert_called_once_with(
        "MR123456", "schedule-id"
    )


async def test_set_brew_by_weight_dose_mode_updates_dashboard(
    mock_machine: LaMarzoccoMachine,
) -> None:
    """Test setting the brew by weight dose mode updates the dashboard."""
    mock_machine.dashboard.model_code = ModelCode.LINEA_MINI_R
    widget = MagicMock()
    mock_machine.dashboard.config[WidgetType.CM_BREW_BY_WEIGHT_DOSES] = widget
    assert await mock_machine.set_brew_by_weight_dose_mode(DoseMode.DOSE_2)
    assert widget.mode is DoseMode.DOSE_2


async def test_set_brew_by_weight_dose_unavailable(
    mock_machine: LaMarzoccoMachine,
    mock_cloud_client: MagicMock,
) -> None:
    """Test setting a brew by weight dose without widget or for continuous."""
    mock_machine.dashboard.model_code = ModelCode.LINEA_MINI_R
    assert not await mock_machine.set_brew_by_weight_dose(DoseMode.DOSE_1, 36.5)

    mock_machine.dashboard.config[WidgetType.CM_BREW_BY_WEIGHT_DOSES] = MagicMock()
    assert not await mock_machine.set_brew_by_weight_dose(DoseMode.CONTINUOUS, 36.5)
    mock_cloud_client.set_brew_by_weight_dose.assert_not_called()


async def test_set_brew_by_weight_dose_2(
    mock_machine: LaMarzoccoMachine,
    mock_cloud_client: MagicMock,
) -> None:
    """Test setting the second brew by weight dose."""
    mock_machine.dashboard.model_code = ModelCode.LINEA_MINI_R
    widget = MagicMock()
    widget.doses.dose_1.dose = 32.0
    mock_machine.dashboard.config[WidgetType.CM_BREW_BY_WEIGHT_DOSES] = widget
    mock_cloud_client.set_brew_by_weight_dose.return_value = False
    assert not await mock_machine.set_brew_by_weight_dose(DoseMode.DOSE_2, 40.0)
    mock_cloud_client.set_brew_by_weight_dose.assert_called_once_with(
        "MR123456", 32.0, 40.0
    )


async def test_bluetooth_failure_without_cloud(
    mock_bluetooth_client: MagicMock,
) -> None:
    """Test a failing Bluetooth command without cloud fallback."""
    machine = LaMarzoccoMachine("MR123456", bluetooth_client=mock_bluetooth_client)
    mock_bluetooth_client.set_power.side_effect = BluetoothConnectionFailed("boom")
    assert not await machine.set_power(True)


async def test_get_statistics_widgets(
    mock_machine: LaMarzoccoMachine,
    mock_cloud_client: MagicMock,
) -> None:
    """Test the extended statistics are stored on the machine."""
    trend = MagicMock()
    last_coffee = MagicMock()
    counter = MagicMock()
    mock_cloud_client.get_thing_coffee_and_flush_trend.return_value = trend
    mock_cloud_client.get_thing_last_coffee.return_value = last_coffee
    mock_cloud_client.get_thing_coffee_and_flush_counter.return_value = counter

    assert await mock_machine.get_coffee_and_flush_trend(7, "Europe/Berlin") is trend
    mock_cloud_client.get_thing_coffee_and_flush_trend.assert_called_once_with(
        serial_number="MR123456", days=7, timezone="Europe/Berlin"
    )
    assert await mock_machine.get_last_coffee(7) is last_coffee
    mock_cloud_client.get_thing_last_coffee.assert_called_once_with(
        serial_number="MR123456", days=7
    )
    assert await mock_machine.get_coffee_and_flush_counter() is counter
    mock_cloud_client.get_thing_coffee_and_flush_counter.assert_called_once_with(
        serial_number="MR123456"
    )

    assert mock_machine.statistics.widgets == {
        WidgetType.COFFEE_AND_FLUSH_TREND: trend,
        WidgetType.LAST_COFFEE: last_coffee,
        WidgetType.COFFEE_AND_FLUSH_COUNTER: counter,
    }
