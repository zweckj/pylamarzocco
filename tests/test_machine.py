"""Test the machine module."""

import asyncio
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import partial
from typing import Any
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
from pylamarzocco.devices._machine import BLE_BREWING_STATE_TIMEOUT
from pylamarzocco.exceptions import (
    BluetoothConnectionFailed,
    OperationNotAvailable,
    UnsupportedModel,
)
from pylamarzocco.models import (
    BluetoothBrewingData,
    BluetoothMachineTelemetry,
    BluetoothShotCounterUpdate,
    BrewByWeightDoses,
    DosePulsesType,
    DoseSettings,
    GroupDosesSettings,
    HotWaterDose,
    MachineGroupStatus,
    PrebrewSettingTimes,
    SecondsInOut,
    ThingDashboardConfig,
    ThingDashboardWebsocketConfig,
    WakeUpScheduleSettings,
)

from .conftest import load_fixture, machine_status, websocket_config

# recorded dashboards to take real widgets from
DASHBOARD_FIXTURES = {
    ModelCode.STRADA_X: "dashboard_stradax.json",
    ModelCode.LINEA_MINI: "dashboard_mini.json",
}

WAKEUP_SCHEDULE = WakeUpScheduleSettings(
    on_time_minutes=420, off_time_minutes=480, steam_boiler=True
)


def _fixture_widget(model_code: ModelCode, widget_type: WidgetType) -> Any:
    """Return a real widget from the recorded dashboard of the given model."""
    fixture = load_fixture("machine", DASHBOARD_FIXTURES[model_code])
    return ThingDashboardConfig.from_dict(fixture).config[widget_type]


@pytest.fixture(name="mock_machine")
def mock_lm_machine(
    serial: str,
    mock_bluetooth_client: MagicMock,
    mock_cloud_client: MagicMock,
) -> LaMarzoccoMachine:
    """Mock the LaMarzoccoMachine."""
    return LaMarzoccoMachine(
        serial_number=serial,
        bluetooth_client=mock_bluetooth_client,
        cloud_client=mock_cloud_client,
    )


@pytest.fixture(name="dashboard_callback")
async def fixture_dashboard_callback(mock_machine: LaMarzoccoMachine) -> MagicMock:
    """Connect the dashboard websocket and return its update callback."""
    callback = MagicMock()
    await mock_machine.connect_dashboard_websocket(update_callback=callback)
    return callback


def _push_dashboard_update(
    cloud_client: MagicMock, config: ThingDashboardWebsocketConfig
) -> None:
    """Deliver a dashboard update like the cloud websocket does."""
    cloud_client.websocket_connect.call_args.kwargs["notification_callback"](config)


@dataclass
class FakeTimer:
    """Stand-in for the event loop timer of the Bluetooth brewing state expiry."""

    callback: Callable[[], object]
    cancelled: bool = False

    def cancel(self) -> None:
        """Cancel the timer."""
        self.cancelled = True

    def fire(self) -> None:
        """Run the callback, like the event loop does once the delay passed."""
        self.callback()


@pytest.fixture(name="expiry_timers")
async def fixture_expiry_timers() -> AsyncGenerator[list[FakeTimer]]:
    """Capture the Bluetooth brewing expiry timers instead of scheduling them."""
    loop = asyncio.get_running_loop()
    call_later = loop.call_later
    timers: list[FakeTimer] = []

    def capture(
        delay: float, callback: Callable[..., object], *args: Any, **kwargs: Any
    ) -> asyncio.TimerHandle | FakeTimer:
        if delay != BLE_BREWING_STATE_TIMEOUT:
            return call_later(delay, callback, *args, **kwargs)
        timers.append(timer := FakeTimer(partial(callback, *args)))
        return timer

    with patch.object(loop, "call_later", capture):
        yield timers


BLUETOOTH_COMMANDS = [
    (
        "set_power",
        (True,),
        None,
        "set_power",
        {"enabled": True},
        "set_power",
        {"enabled": True},
    ),
    (
        "set_steam",
        (False,),
        None,
        "set_steam",
        {"enabled": False},
        "set_steam",
        {"enabled": False},
    ),
    (
        "set_steam_level",
        (SteamTargetLevel.LEVEL_2,),
        None,
        "set_temp",
        {"boiler": BoilerType.STEAM, "temperature": 128},
        "set_steam_target_level",
        {"target_level": SteamTargetLevel.LEVEL_2},
    ),
    (
        "set_coffee_target_temperature",
        (93,),
        None,
        "set_temp",
        {"boiler": BoilerType.COFFEE, "temperature": 93},
        "set_coffee_target_temperature",
        {"target_temperature": 93},
    ),
    (
        "set_steam_target_temperature",
        (124,),
        ModelCode.GS3,
        "set_temp",
        {"boiler": BoilerType.STEAM, "temperature": 124},
        "set_steam_target_temperature",
        {"target_temperature": 124},
    ),
    (
        "set_smart_standby",
        (True, 30, SmartStandByType.POWER_ON),
        None,
        "set_smart_standby",
        {"enabled": True, "minutes": 30, "mode": SmartStandByType.POWER_ON},
        "set_smart_standby",
        {"enabled": True, "minutes": 30, "after": SmartStandByType.POWER_ON},
    ),
]


@pytest.mark.parametrize("ble_fails", [False, True], ids=["bluetooth", "cloud"])
@pytest.mark.parametrize(
    (
        "method",
        "args",
        "model_code",
        "ble_method",
        "ble_kwargs",
        "cloud_method",
        "cloud_kwargs",
    ),
    BLUETOOTH_COMMANDS,
    ids=[command[0] for command in BLUETOOTH_COMMANDS],
)
async def test_bluetooth_command_with_cloud_fallback(
    mock_machine: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
    mock_cloud_client: MagicMock,
    serial: str,
    method: str,
    args: tuple,
    model_code: ModelCode | None,
    ble_method: str,
    ble_kwargs: dict[str, Any],
    cloud_method: str,
    cloud_kwargs: dict[str, Any],
    ble_fails: bool,
) -> None:
    """Test commands are sent over Bluetooth, falling back to the cloud."""
    if model_code is not None:
        mock_machine.dashboard.model_code = model_code
    if ble_fails:
        getattr(mock_bluetooth_client, ble_method).side_effect = (
            BluetoothConnectionFailed("Bluetooth error")
        )
    getattr(mock_cloud_client, cloud_method).return_value = True

    assert await getattr(mock_machine, method)(*args)

    getattr(mock_bluetooth_client, ble_method).assert_called_once_with(**ble_kwargs)
    if ble_fails:
        getattr(mock_cloud_client, cloud_method).assert_called_once_with(
            serial_number=serial, **cloud_kwargs
        )
    else:
        getattr(mock_cloud_client, cloud_method).assert_not_called()


CLOUD_COMMANDS = [
    (
        "set_mode",
        (MachineMode.ECO_MODE,),
        ModelCode.STRADA_X,
        "set_mode",
        (MachineMode.ECO_MODE,),
        WidgetType.CM_MACHINE_GROUP_STATUS,
        "mode",
        MachineMode.ECO_MODE,
    ),
    (
        "set_auto_flush",
        (False,),
        ModelCode.STRADA_X,
        "set_auto_flush",
        (False,),
        WidgetType.CM_AUTO_FLUSH,
        "enabled",
        False,
    ),
    (
        "set_steam_flush",
        (False,),
        ModelCode.STRADA_X,
        "set_steam_flush",
        (False,),
        WidgetType.CM_STEAM_FLUSH,
        "enabled",
        False,
    ),
    (
        "set_rinse_flush",
        (False,),
        ModelCode.STRADA_X,
        "set_rinse_flush",
        (False,),
        WidgetType.CM_RINSE_FLUSH,
        "enabled",
        False,
    ),
    (
        "set_rinse_flush_time",
        (4.5,),
        ModelCode.STRADA_X,
        "set_rinse_flush_time",
        (4.5,),
        WidgetType.CM_RINSE_FLUSH,
        "time_seconds",
        4.5,
    ),
    (
        "set_hot_water_dose_enabled",
        (False,),
        ModelCode.STRADA_X,
        "set_hot_water_dose_enabled",
        (False,),
        WidgetType.CM_HOT_WATER_DOSE,
        "enabled",
        False,
    ),
    (
        "set_group_mode",
        (MachineMode.ECO_MODE,),
        ModelCode.STRADA_X,
        "set_group_mode",
        (MachineMode.ECO_MODE, 1),
        WidgetType.CM_MACHINE_GROUP_STATUS,
        "mode",
        MachineMode.ECO_MODE,
    ),
    (
        "set_coffee_boiler",
        (False,),
        ModelCode.STRADA_X,
        "set_coffee_boiler",
        (False, 1),
        WidgetType.CM_COFFEE_BOILER,
        "enabled",
        False,
    ),
    (
        "set_brew_by_weight_dose_mode",
        (DoseMode.DOSE_1,),
        ModelCode.LINEA_MINI,
        "change_brew_by_weight_dose_mode",
        (DoseMode.DOSE_1,),
        WidgetType.CM_BREW_BY_WEIGHT_DOSES,
        "mode",
        DoseMode.DOSE_1,
    ),
    # commands of the Strada X and GS3 AV, sent under the same name to the cloud
    *(
        (method, args, model_code, method, cloud_args, None, None, None)
        for model_code in (ModelCode.STRADA_X, ModelCode.GS3_AV)
        for method, args, cloud_args in (
            ("set_hot_water_dose", (8.0, DoseIndex.DOSE_A), (8.0, DoseIndex.DOSE_A)),
            ("set_group_dose_mode", (DoseMode.PULSES_TYPE,), (DoseMode.PULSES_TYPE, 1)),
            (
                "set_group_dose",
                (DoseMode.PULSES_TYPE, DoseIndex.DOSE_A, 36.0),
                (DoseMode.PULSES_TYPE, DoseIndex.DOSE_A, 36.0, 1),
            ),
            ("set_continuous_dose_enabled", (True,), (True, 1)),
            ("set_continuous_dose", (3.0,), (3.0, 1)),
        )
    ),
    # commands sent under the same name to the cloud, without a widget update
    *(
        (method, args, model_code, method, cloud_args, None, None, None)
        for method, args, model_code, cloud_args in (
            ("set_brewing_pressure", (9.0,), ModelCode.STRADA_X, (9.0, 1)),
            ("set_mirror_group1", (True,), ModelCode.STRADA_X, (True, 2)),
            ("set_mirror_group1", (True, 3), ModelCode.STRADA_X, (True, 3)),
            ("set_cup_warmer", (True,), None, (True,)),
            ("set_plumb_in", (True,), None, (True,)),
            ("set_auto_on_off", ("schedule",), None, ("schedule",)),
            ("set_wakeup_schedule", (WAKEUP_SCHEDULE,), None, (WAKEUP_SCHEDULE,)),
            ("delete_wakeup_schedule", ("schedule-id",), None, ("schedule-id",)),
        )
    ),
    ("start_backflush", (), None, "start_backflush_cleaning", (), None, None, None),
    (
        "set_pre_extraction_mode",
        (PreExtractionMode.PREBREWING,),
        None,
        "change_pre_extraction_mode",
        (PreExtractionMode.PREBREWING,),
        None,
        None,
        None,
    ),
    (
        "set_pre_extraction_times",
        (2.0, 3.5),
        None,
        "change_pre_extraction_times",
        (PrebrewSettingTimes(times=SecondsInOut(seconds_in=2.0, seconds_out=3.5)),),
        None,
        None,
        None,
    ),
]


@pytest.mark.parametrize(
    (
        "method",
        "args",
        "model_code",
        "cloud_method",
        "cloud_args",
        "widget_type",
        "attribute",
        "value",
    ),
    CLOUD_COMMANDS,
    ids=[
        f"{method}-{model_code}" if model_code else method
        for method, _, model_code, *_ in CLOUD_COMMANDS
    ],
)
async def test_cloud_command(
    mock_machine: LaMarzoccoMachine,
    mock_cloud_client: MagicMock,
    serial: str,
    method: str,
    args: tuple,
    model_code: ModelCode | None,
    cloud_method: str,
    cloud_args: tuple,
    widget_type: WidgetType | None,
    attribute: str | None,
    value: object,
) -> None:
    """Test cloud commands are delegated and update the dashboard widget."""
    if model_code is not None:
        mock_machine.dashboard.model_code = model_code
    widget = None
    if widget_type is not None:
        assert model_code is not None and attribute is not None
        widget = _fixture_widget(model_code, widget_type)
        assert getattr(widget, attribute) != value
        mock_machine.dashboard.config[widget_type] = widget
    getattr(mock_cloud_client, cloud_method).return_value = True

    assert await getattr(mock_machine, method)(*args) is True

    getattr(mock_cloud_client, cloud_method).assert_called_once_with(
        serial, *cloud_args
    )
    if widget is not None:
        assert attribute is not None
        assert getattr(widget, attribute) == value


WIDGET_COMMANDS = [command for command in CLOUD_COMMANDS if command[5] is not None]


@pytest.mark.parametrize(
    ("method", "args", "model_code", "cloud_method"),
    [command[:4] for command in WIDGET_COMMANDS],
    ids=[command[0] for command in WIDGET_COMMANDS],
)
async def test_cloud_command_without_widget(
    mock_machine: LaMarzoccoMachine,
    mock_cloud_client: MagicMock,
    method: str,
    args: tuple,
    model_code: ModelCode,
    cloud_method: str,
) -> None:
    """Test commands succeed when the dashboard lacks the widget to update."""
    mock_machine.dashboard.model_code = model_code
    getattr(mock_cloud_client, cloud_method).return_value = True

    assert await getattr(mock_machine, method)(*args) is True
    assert mock_machine.dashboard.config == {}


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


@pytest.mark.parametrize(
    ("dose", "value", "cloud_args", "result"),
    [
        (DoseMode.DOSE_1, 36.5, (36.5, 34.0), True),
        (DoseMode.DOSE_2, 40.0, (32.0, 40.0), False),
    ],
)
async def test_set_brew_by_weight_dose(
    mock_machine: LaMarzoccoMachine,
    mock_cloud_client: MagicMock,
    serial: str,
    dose: DoseMode,
    value: float,
    cloud_args: tuple[float, float],
    result: bool,
) -> None:
    """Test setting a brew by weight dose keeps the other dose unchanged."""
    mock_machine.dashboard.model_code = ModelCode.LINEA_MINI
    widget: BrewByWeightDoses = _fixture_widget(
        ModelCode.LINEA_MINI, WidgetType.CM_BREW_BY_WEIGHT_DOSES
    )
    mock_machine.dashboard.config[WidgetType.CM_BREW_BY_WEIGHT_DOSES] = widget
    mock_cloud_client.set_brew_by_weight_dose.return_value = result

    assert await mock_machine.set_brew_by_weight_dose(dose, value) is result
    mock_cloud_client.set_brew_by_weight_dose.assert_called_once_with(
        serial, *cloud_args
    )
    doses = (widget.doses.dose_1.dose, widget.doses.dose_2.dose)
    assert doses == (cloud_args if result else (32.0, 34.0))


async def test_set_brew_by_weight_dose_unavailable(
    mock_machine: LaMarzoccoMachine,
    mock_cloud_client: MagicMock,
) -> None:
    """Test setting a brew by weight dose without widget or for continuous."""
    mock_machine.dashboard.model_code = ModelCode.LINEA_MINI_R
    assert not await mock_machine.set_brew_by_weight_dose(DoseMode.DOSE_1, 36.5)

    mock_machine.dashboard.config[WidgetType.CM_BREW_BY_WEIGHT_DOSES] = (
        _fixture_widget(ModelCode.LINEA_MINI, WidgetType.CM_BREW_BY_WEIGHT_DOSES)
    )
    assert not await mock_machine.set_brew_by_weight_dose(DoseMode.CONTINUOUS, 36.5)
    mock_cloud_client.set_brew_by_weight_dose.assert_not_called()


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
    serial: str,
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
        serial, DoseMode.PULSES_TYPE, 1
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
    serial: str,
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
    mock_cloud_client.set_brewing_pressure.assert_called_once_with(serial, 9.0, 1)


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
    serial: str,
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
        serial, DoseMode.MASS_TYPE, DoseIndex.DOSE_A, 18.0, 1
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


async def _connect_shot_counter(
    machine: LaMarzoccoMachine,
    bluetooth_client: MagicMock,
    *callbacks: Callable[..., Any] | None,
) -> tuple[
    Callable[[BluetoothShotCounterUpdate], None],
    Callable[[bool], None],
    Callable[[BluetoothMachineTelemetry], None],
]:
    """Start the shot counter and return the callbacks given to the client.

    Returns the brewing update, connection and telemetry callbacks.
    """
    await machine.connect_bluetooth_shot_counter(*callbacks)
    call = bluetooth_client.start_shot_counter.call_args
    return (
        call.args[0],
        call.kwargs["connection_callback"],
        call.kwargs["telemetry_callback"],
    )


async def test_connect_bluetooth_shot_counter(
    mock_machine: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
    mock_cloud_client: MagicMock,
    serial: str,
) -> None:
    """Test starting the shot counter doesn't depend on cloud data."""
    mock_bluetooth_client.start_shot_counter.return_value = True

    assert not mock_machine.dashboard.shot_counter_supported
    assert await mock_machine.connect_bluetooth_shot_counter() is True
    mock_bluetooth_client.start_shot_counter.assert_awaited_once()

    mock_bluetooth_client.start_shot_counter.return_value = False
    assert await mock_machine.connect_bluetooth_shot_counter() is False

    machine = LaMarzoccoMachine(serial, cloud_client=mock_cloud_client)
    assert await machine.connect_bluetooth_shot_counter() is False


async def test_register_bluetooth_connection_callback(
    mock_machine: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
    mock_cloud_client: MagicMock,
    serial: str,
) -> None:
    """Test connection callbacks are registered on the Bluetooth client."""
    callback = MagicMock()

    unregister = mock_machine.register_bluetooth_connection_callback(callback)

    mock_bluetooth_client.register_connection_callback.assert_called_once_with(callback)
    assert unregister is mock_bluetooth_client.register_connection_callback.return_value

    # without a Bluetooth client, registering is a no-op
    machine = LaMarzoccoMachine(serial, cloud_client=mock_cloud_client)
    machine.register_bluetooth_connection_callback(callback)()


async def test_shot_counter_overrides_machine_status(
    mock_machine: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
    mock_cloud_client: MagicMock,
) -> None:
    """Test BLE brewing states override the machine status widget."""
    cloud_start = datetime(2026, 1, 1, 11, 0, 0, tzinfo=timezone.utc)
    status = machine_status(MachineState.POWERED_ON, cloud_start)
    mock_machine.dashboard.config[WidgetType.CM_MACHINE_STATUS] = status
    callback = MagicMock()
    await mock_machine.connect_dashboard_websocket()

    on_update, on_connection, _ = await _connect_shot_counter(
        mock_machine, mock_bluetooth_client, callback
    )

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
    _push_dashboard_update(mock_cloud_client, websocket_config(late))
    assert mock_machine.dashboard.config[WidgetType.CM_MACHINE_STATUS] is late
    assert late.status == MachineState.POWERED_ON

    # flushes keep non-brewing cloud states
    standby = machine_status(MachineState.STANDBY)
    _push_dashboard_update(mock_cloud_client, websocket_config(standby))
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
    dashboard_callback: MagicMock,
) -> None:
    """Test the dashboard update callback is used without a dedicated callback."""
    mock_machine.dashboard.config[WidgetType.CM_MACHINE_STATUS] = machine_status(
        MachineState.POWERED_ON
    )

    on_update, _, _ = await _connect_shot_counter(mock_machine, mock_bluetooth_client)
    on_update(_brewing_update(BluetoothBrewingState.BREWING, timer_value=3))

    dashboard_callback.assert_called_once()
    config: ThingDashboardWebsocketConfig = dashboard_callback.call_args.args[0]
    assert config.config[WidgetType.CM_MACHINE_STATUS].status == MachineState.BREWING


async def test_disconnect_bluetooth_shot_counter(
    mock_machine: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
    expiry_timers: list[FakeTimer],
) -> None:
    """Test stopping the shot counter restores the cloud state without callbacks."""
    status = machine_status(MachineState.POWERED_ON)
    mock_machine.dashboard.config[WidgetType.CM_MACHINE_STATUS] = status
    callback = MagicMock()
    on_update, on_connection, on_telemetry = await _connect_shot_counter(
        mock_machine, mock_bluetooth_client, callback
    )
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
    assert [timer.cancelled for timer in expiry_timers] == [True]


async def test_shot_counter_state_expires(
    mock_machine: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
    expiry_timers: list[FakeTimer],
) -> None:
    """Test a stale Bluetooth state falls back to the cloud state."""
    status = machine_status(MachineState.POWERED_ON)
    mock_machine.dashboard.config[WidgetType.CM_MACHINE_STATUS] = status
    callback = MagicMock()
    on_update, _, _ = await _connect_shot_counter(
        mock_machine, mock_bluetooth_client, callback
    )

    on_update(_brewing_update(BluetoothBrewingState.BREWING, timer_value=3))
    assert [timer.cancelled for timer in expiry_timers] == [False]

    # a new notification extends the lifetime
    on_update(_brewing_update(BluetoothBrewingState.BREWING, timer_value=4))
    assert [timer.cancelled for timer in expiry_timers] == [True, False]
    assert status.status == MachineState.BREWING

    expiry_timers[-1].fire()

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
    expiry_timers: list[FakeTimer],
) -> None:
    """Test a Bluetooth refresh during the override is kept after it expires."""
    status = machine_status(MachineState.POWERED_ON)
    mock_machine.dashboard.config[WidgetType.CM_MACHINE_STATUS] = status
    _mock_bluetooth_dashboard(mock_bluetooth_client, MachineMode.STANDBY)
    on_update, _, _ = await _connect_shot_counter(mock_machine, mock_bluetooth_client)
    on_update(_brewing_update(BluetoothBrewingState.BREWING, timer_value=3))
    on_update(_brewing_update(BluetoothBrewingState.BREWING_STOPPED, None, 27.4))

    # the machine is put in standby and the widget is refreshed in place
    await mock_machine.get_dashboard_from_bluetooth()
    assert status.status == MachineState.STANDBY

    expiry_timers[-1].fire()

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
    on_update, _, _ = await _connect_shot_counter(mock_machine, mock_bluetooth_client)
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
    _, on_connection, on_telemetry = await _connect_shot_counter(
        mock_machine, mock_bluetooth_client, callback, telemetry_callback
    )

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
    on_update, _, on_telemetry = await _connect_shot_counter(
        mock_machine, mock_bluetooth_client, MagicMock(), MagicMock()
    )

    on_update(_brewing_update(BluetoothBrewingState.BREWING, timer_value=3))
    on_telemetry(BluetoothMachineTelemetry(machine_mode=MachineMode.ECO_MODE))
    assert status.status == MachineState.BREWING

    on_update(_brewing_update(BluetoothBrewingState.FLUSHED))
    assert (status.mode, status.status) == (MachineMode.ECO_MODE, MachineState.ECO_MODE)


async def test_bluetooth_machine_mode_falls_back_to_websocket_callback(
    mock_machine: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
    dashboard_callback: MagicMock,
) -> None:
    """Test machine mode changes use the dashboard callback without a callback."""
    mock_machine.dashboard.config[WidgetType.CM_MACHINE_STATUS] = machine_status(
        MachineState.POWERED_ON
    )
    _, _, on_telemetry = await _connect_shot_counter(
        mock_machine, mock_bluetooth_client
    )

    on_telemetry(BluetoothMachineTelemetry(coffee_boiler_temperature=93))
    dashboard_callback.assert_not_called()

    on_telemetry(BluetoothMachineTelemetry(machine_mode=MachineMode.STANDBY))
    dashboard_callback.assert_called_once()
    config: ThingDashboardWebsocketConfig = dashboard_callback.call_args.args[0]
    assert config.config[WidgetType.CM_MACHINE_STATUS].mode == MachineMode.STANDBY


async def test_bluetooth_shot_counter_active(
    mock_machine: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
    serial: str,
) -> None:
    """Test the shot counter state is taken from the Bluetooth client."""
    mock_bluetooth_client.shot_counter_active = True
    assert mock_machine.bluetooth_shot_counter_active
    mock_bluetooth_client.shot_counter_active = False
    assert not mock_machine.bluetooth_shot_counter_active
    assert not LaMarzoccoMachine(serial).bluetooth_shot_counter_active


async def test_get_model_info_from_bluetooth_errors(
    mock_machine: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
    serial: str,
) -> None:
    """Test errors while fetching the model info from Bluetooth."""
    with pytest.raises(BluetoothConnectionFailed):
        await LaMarzoccoMachine(serial).get_model_info_from_bluetooth()

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
    group_status: MachineGroupStatus = _fixture_widget(
        ModelCode.STRADA_X, WidgetType.CM_MACHINE_GROUP_STATUS
    )
    assert group_status.mode is MachineMode.STANDBY
    mock_machine.dashboard.config[WidgetType.CM_MACHINE_GROUP_STATUS] = group_status
    assert await mock_machine.set_power(True)
    assert group_status.mode is MachineMode.BREWING_MODE


async def test_set_mode_failed_keeps_widgets(
    mock_machine: LaMarzoccoMachine,
    mock_cloud_client: MagicMock,
) -> None:
    """Test a failed set_mode does not touch the dashboard."""
    mock_machine.dashboard.model_code = ModelCode.STRADA_X
    status = machine_status(MachineState.STANDBY, mode=MachineMode.STANDBY)
    mock_machine.dashboard.config[WidgetType.CM_MACHINE_STATUS] = status
    mock_cloud_client.set_mode.return_value = False
    assert not await mock_machine.set_mode(MachineMode.ECO_MODE)
    assert status.mode is MachineMode.STANDBY


async def test_set_hot_water_dose_updates_dashboard(
    mock_machine: LaMarzoccoMachine,
    mock_cloud_client: MagicMock,
) -> None:
    """Test setting the hot water dose updates the matching dose."""
    mock_machine.dashboard.model_code = ModelCode.STRADA_X
    hot_water_dose: HotWaterDose = _fixture_widget(
        ModelCode.STRADA_X, WidgetType.CM_HOT_WATER_DOSE
    )
    mock_machine.dashboard.config[WidgetType.CM_HOT_WATER_DOSE] = hot_water_dose
    mock_cloud_client.set_hot_water_dose.return_value = True
    assert await mock_machine.set_hot_water_dose(15, DoseIndex.DOSE_B)
    assert [(dose.dose_index, dose.dose) for dose in hot_water_dose.doses] == [
        (DoseIndex.DOSE_A, 7.83),
        (DoseIndex.DOSE_B, 15),
    ]


@pytest.mark.parametrize(
    ("enabled", "minutes", "expected"),
    [(True, 90, "01:30"), (False, 90, "Off")],
)
async def test_set_smart_standby_auto_standby(
    mock_machine: LaMarzoccoMachine,
    mock_bluetooth_client: MagicMock,
    mock_cloud_client: MagicMock,
    serial: str,
    enabled: bool,
    minutes: int,
    expected: str,
) -> None:
    """Test smart standby uses auto standby when the schedule supports it."""
    mock_machine.schedule.auto_stand_by_supported = True
    assert await mock_machine.set_smart_standby(
        enabled, minutes, SmartStandByType.POWER_ON
    )
    mock_cloud_client.set_auto_standby.assert_called_once_with(serial, expected)
    mock_bluetooth_client.set_smart_standby.assert_not_called()


async def test_bluetooth_failure_without_cloud(
    mock_bluetooth_client: MagicMock,
    serial: str,
) -> None:
    """Test a failing Bluetooth command without cloud fallback."""
    machine = LaMarzoccoMachine(serial, bluetooth_client=mock_bluetooth_client)
    mock_bluetooth_client.set_power.side_effect = BluetoothConnectionFailed("boom")
    assert not await machine.set_power(True)


async def test_get_statistics_widgets(
    mock_machine: LaMarzoccoMachine,
    mock_cloud_client: MagicMock,
    serial: str,
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
        serial_number=serial, days=7, timezone="Europe/Berlin"
    )
    assert await mock_machine.get_last_coffee(7) is last_coffee
    mock_cloud_client.get_thing_last_coffee.assert_called_once_with(
        serial_number=serial, days=7
    )
    assert await mock_machine.get_coffee_and_flush_counter() is counter
    mock_cloud_client.get_thing_coffee_and_flush_counter.assert_called_once_with(
        serial_number=serial
    )

    assert mock_machine.statistics.widgets == {
        WidgetType.COFFEE_AND_FLUSH_TREND: trend,
        WidgetType.LAST_COFFEE: last_coffee,
        WidgetType.COFFEE_AND_FLUSH_COUNTER: counter,
    }
