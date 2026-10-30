"""Test the grinder module."""

from unittest.mock import MagicMock

import pytest

from pylamarzocco import LaMarzoccoGrinder
from pylamarzocco.const import (
    DoseIndex,
    DoseMode,
    GrinderDoseMode,
    GrinderGrindWithMode,
    GrinderMode,
    GrinderSpeedLevelType,
    GrinderStatus,
    ModelCode,
    WidgetType,
)
from pylamarzocco.exceptions import UnsupportedModel
from pylamarzocco.models import (
    AutoStandBy,
    GrinderBaristaLight,
    GrinderDoses,
    GrinderDoseSettings,
    GrinderDosesSettings,
    GrinderGrindWith,
    GrinderMachineStatus,
    GrinderMirrorDoses,
    GrinderMoreDose,
    GrinderSingleDoseMode,
    GrinderSpeed,
    GrinderSpeedAuto,
    GrinderSpeedLevel,
    GrinderSpeedLevelSetting,
)


@pytest.fixture(name="grinder_serial")
def mock_grinder_serial() -> str:
    """Return the serial number of the mocked grinder."""
    return "GR123456"


@pytest.fixture(name="mock_grinder")
def mock_lm_grinder(
    grinder_serial: str,
    mock_cloud_client: MagicMock,
) -> LaMarzoccoGrinder:
    """Mock the LaMarzoccoGrinder."""
    return LaMarzoccoGrinder(
        serial_number=grinder_serial,
        cloud_client=mock_cloud_client,
    )


def _speed_widget(speed_auto: GrinderSpeedAuto | None = None) -> GrinderSpeed:
    return GrinderSpeed(
        doses={
            "DoseA": GrinderSpeedLevel(
                level=GrinderSpeedLevelType.LOW, auto_enabled=False, group_index=None
            ),
        },
        groups_number=2,
        speed_auto_supported=True,
        speed_auto=speed_auto,
    )


async def test_set_power_updates_mode(
    mock_grinder: LaMarzoccoGrinder,
    mock_cloud_client: MagicMock,
    grinder_serial: str,
) -> None:
    """Test the set_power method (wake / standby)."""
    mock_grinder.dashboard.config[WidgetType.G_MACHINE_STATUS] = GrinderMachineStatus(
        status=GrinderStatus.STANDBY,
        available_modes=[GrinderMode.GRINDING, GrinderMode.STANDBY],
        mode=GrinderMode.STANDBY,
    )

    assert await mock_grinder.set_power(True)
    mock_cloud_client.set_grinder_mode.assert_called_once_with(
        grinder_serial, GrinderMode.GRINDING
    )

    status = mock_grinder.dashboard.config[WidgetType.G_MACHINE_STATUS]
    assert isinstance(status, GrinderMachineStatus)
    assert status.mode is GrinderMode.GRINDING


async def test_set_grind_with(
    mock_grinder: LaMarzoccoGrinder,
    mock_cloud_client: MagicMock,
    grinder_serial: str,
) -> None:
    """Test the set_grind_with method."""
    mock_grinder.dashboard.model_code = ModelCode.SWAN_GRINDER
    mock_grinder.dashboard.config[WidgetType.G_GRIND_WITH] = GrinderGrindWith(
        mode=GrinderGrindWithMode.PORTAFILTER
    )

    assert await mock_grinder.set_grind_with(GrinderGrindWithMode.BY_BUTTON)
    mock_cloud_client.set_grinder_grind_with.assert_called_once_with(
        grinder_serial, GrinderGrindWithMode.BY_BUTTON
    )

    grind_with = mock_grinder.dashboard.config[WidgetType.G_GRIND_WITH]
    assert isinstance(grind_with, GrinderGrindWith)
    assert grind_with.mode is GrinderGrindWithMode.BY_BUTTON


async def test_set_dose_defaults_to_current_mode(
    mock_grinder: LaMarzoccoGrinder,
    mock_cloud_client: MagicMock,
    grinder_serial: str,
) -> None:
    """Test set_dose uses the grinder's current dose mode when none is given."""
    mock_grinder.dashboard.config[WidgetType.G_DOSES] = GrinderDoses(
        mode=GrinderDoseMode.TIME,
        doses=GrinderDosesSettings(
            time_type=[
                GrinderDoseSettings(
                    dose_index=DoseIndex.DOSE_A,
                    dose=1.5,
                    dose_min=0,
                    dose_max=20,
                    dose_step=0.05,
                ),
            ],
        ),
    )

    assert await mock_grinder.set_dose(DoseIndex.DOSE_A, 2.0)
    mock_cloud_client.set_grinder_dose.assert_called_once_with(
        grinder_serial, DoseIndex.DOSE_A, 2.0, GrinderDoseMode.TIME
    )
    mock_cloud_client.set_grinder_speed.assert_not_called()

    doses = mock_grinder.dashboard.config[WidgetType.G_DOSES]
    assert isinstance(doses, GrinderDoses)
    assert doses.doses.time_type[0].dose == 2.0


async def test_set_more_dose(
    mock_grinder: LaMarzoccoGrinder,
    mock_cloud_client: MagicMock,
    grinder_serial: str,
) -> None:
    """Test the set_more_dose method."""
    mock_grinder.dashboard.model_code = ModelCode.SWAN_GRINDER
    mock_grinder.dashboard.config[WidgetType.G_MORE_DOSE] = GrinderMoreDose(
        revolutions=1.0,
        revolutions_min=0,
        revolutions_max=5,
        revolutions_step=0.1,
    )

    assert await mock_grinder.set_more_dose(2.5)
    mock_cloud_client.set_grinder_more_dose.assert_called_once_with(
        grinder_serial, 2.5
    )

    more_dose = mock_grinder.dashboard.config[WidgetType.G_MORE_DOSE]
    assert isinstance(more_dose, GrinderMoreDose)
    assert more_dose.revolutions == 2.5


async def test_set_speed(
    mock_grinder: LaMarzoccoGrinder,
    mock_cloud_client: MagicMock,
    grinder_serial: str,
) -> None:
    """Test setting the speed level of a dose updates both widgets."""
    mock_grinder.dashboard.model_code = ModelCode.SWAN_GRINDER
    mock_grinder.dashboard.config[WidgetType.G_SPEED] = _speed_widget()
    mock_grinder.dashboard.config[WidgetType.G_DOSES] = GrinderDoses(
        mode=GrinderDoseMode.REV,
        doses=GrinderDosesSettings(),
        speed_levels_supported=True,
        speed_levels=[
            GrinderSpeedLevelSetting(
                dose_index=DoseIndex.DOSE_A, level=GrinderSpeedLevelType.LOW
            ),
        ],
    )
    mock_cloud_client.set_grinder_speed.return_value = True

    assert await mock_grinder.set_speed(DoseIndex.DOSE_A, GrinderSpeedLevelType.HIGH)
    mock_cloud_client.set_grinder_speed.assert_called_once_with(
        grinder_serial, DoseIndex.DOSE_A, GrinderSpeedLevelType.HIGH
    )

    speed = mock_grinder.dashboard.config[WidgetType.G_SPEED]
    assert isinstance(speed, GrinderSpeed)
    assert speed.doses["DoseA"].level is GrinderSpeedLevelType.HIGH
    doses = mock_grinder.dashboard.config[WidgetType.G_DOSES]
    assert isinstance(doses, GrinderDoses)
    assert doses.speed_levels is not None
    assert doses.speed_levels[0].level is GrinderSpeedLevelType.HIGH


async def test_set_speed_failed_keeps_dashboard(
    mock_grinder: LaMarzoccoGrinder,
    mock_cloud_client: MagicMock,
) -> None:
    """Test a failed speed command does not touch the dashboard."""
    mock_grinder.dashboard.model_code = ModelCode.SWAN_GRINDER
    mock_grinder.dashboard.config[WidgetType.G_SPEED] = speed = _speed_widget()
    mock_cloud_client.set_grinder_speed.return_value = False

    assert not await mock_grinder.set_speed(
        DoseIndex.DOSE_A, GrinderSpeedLevelType.HIGH
    )
    assert speed.doses["DoseA"].level is GrinderSpeedLevelType.LOW


async def test_set_auto_speed(
    mock_grinder: LaMarzoccoGrinder,
    mock_cloud_client: MagicMock,
    grinder_serial: str,
) -> None:
    """Test enabling the automatic speed of a dose."""
    mock_grinder.dashboard.model_code = ModelCode.SWAN_GRINDER
    mock_grinder.dashboard.config[WidgetType.G_SPEED] = speed = _speed_widget()
    mock_cloud_client.set_grinder_auto_speed_enabled.return_value = True

    assert await mock_grinder.set_auto_speed(DoseIndex.DOSE_A, True, group_index=2)
    mock_cloud_client.set_grinder_auto_speed_enabled.assert_called_once_with(
        grinder_serial, DoseIndex.DOSE_A, True, 2
    )
    assert speed.doses["DoseA"].auto_enabled is True
    assert speed.doses["DoseA"].group_index == 2


@pytest.mark.parametrize(
    ("method", "cloud_method", "widget"),
    [
        (
            "set_barista_light",
            "set_grinder_barista_light",
            GrinderBaristaLight(enabled=False),
        ),
        (
            "set_single_dose_mode",
            "set_grinder_single_dose_mode",
            GrinderSingleDoseMode(enabled=False),
        ),
        (
            "set_mirror_doses",
            "set_grinder_mirror_doses",
            GrinderMirrorDoses(enabled=False),
        ),
    ],
)
async def test_enable_commands_update_dashboard(
    mock_grinder: LaMarzoccoGrinder,
    mock_cloud_client: MagicMock,
    grinder_serial: str,
    method: str,
    cloud_method: str,
    widget: GrinderBaristaLight | GrinderSingleDoseMode | GrinderMirrorDoses,
) -> None:
    """Test the commands that enable a feature update the dashboard."""
    mock_grinder.dashboard.config[widget.widget_type] = widget
    getattr(mock_cloud_client, cloud_method).return_value = True

    assert await getattr(mock_grinder, method)(True) is True
    getattr(mock_cloud_client, cloud_method).assert_called_once_with(
        grinder_serial, True
    )
    assert widget.enabled is True


async def test_set_dose(
    mock_grinder: LaMarzoccoGrinder,
    mock_cloud_client: MagicMock,
    grinder_serial: str,
) -> None:
    """Test set_dose sets the speed level with its own command first."""
    mock_grinder.dashboard.model_code = ModelCode.SWAN_GRINDER
    mock_grinder.dashboard.config[WidgetType.G_SPEED] = speed = _speed_widget()
    mock_grinder.dashboard.config[WidgetType.G_DOSES] = doses = GrinderDoses(
        mode=GrinderDoseMode.REV,
        doses=GrinderDosesSettings(
            rev_type=[
                GrinderDoseSettings(
                    dose_index=DoseIndex.DOSE_A,
                    dose=9.5,
                    dose_min=0,
                    dose_max=50,
                    dose_step=0.1,
                ),
            ],
        ),
    )
    mock_cloud_client.set_grinder_dose.return_value = True
    mock_cloud_client.set_grinder_speed.return_value = True

    assert await mock_grinder.set_dose(
        DoseIndex.DOSE_A, 12.0, speed_level=GrinderSpeedLevelType.HIGH
    )
    mock_cloud_client.set_grinder_speed.assert_called_once_with(
        grinder_serial, DoseIndex.DOSE_A, GrinderSpeedLevelType.HIGH
    )
    mock_cloud_client.set_grinder_dose.assert_called_once_with(
        grinder_serial, DoseIndex.DOSE_A, 12.0, GrinderDoseMode.REV
    )
    assert doses.doses.rev_type[0].dose == 12.0
    assert speed.doses["DoseA"].level is GrinderSpeedLevelType.HIGH


async def test_set_dose_speed_failure(
    mock_grinder: LaMarzoccoGrinder,
    mock_cloud_client: MagicMock,
) -> None:
    """Test set_dose doesn't set the dose when the speed level failed."""
    mock_grinder.dashboard.model_code = ModelCode.SWAN_GRINDER
    mock_cloud_client.set_grinder_speed.return_value = False

    assert not await mock_grinder.set_dose(
        DoseIndex.DOSE_A, 9.0, speed_level=GrinderSpeedLevelType.HIGH
    )
    mock_cloud_client.set_grinder_dose.assert_not_called()


async def test_set_auto_speed_reference(
    mock_grinder: LaMarzoccoGrinder,
    mock_cloud_client: MagicMock,
    grinder_serial: str,
) -> None:
    """Test setting the reference extraction of the automatic speed."""
    mock_grinder.dashboard.model_code = ModelCode.SWAN_GRINDER
    speed_auto = GrinderSpeedAuto(dose_mode=DoseMode.PULSES_TYPE, dose_pulses=120)
    mock_grinder.dashboard.config[WidgetType.G_SPEED] = _speed_widget(speed_auto)
    mock_cloud_client.set_grinder_auto_speed_reference.return_value = True

    assert await mock_grinder.set_auto_speed_reference(
        DoseMode.MASS_TYPE, extraction_seconds=28, dose_mass=36.5, rate_lock=True
    )
    mock_cloud_client.set_grinder_auto_speed_reference.assert_called_once_with(
        grinder_serial, DoseMode.MASS_TYPE, 28, 36.5, None, True
    )
    assert speed_auto.dose_mode is DoseMode.MASS_TYPE
    assert speed_auto.extraction_seconds == 28
    assert speed_auto.dose_mass == 36.5
    assert speed_auto.dose_pulses is None
    assert speed_auto.rate_lock is True


@pytest.mark.parametrize(
    ("method", "args"),
    [
        ("set_grind_with", (GrinderGrindWithMode.BY_BUTTON,)),
        ("set_more_dose", (2.0,)),
        ("set_speed", (DoseIndex.DOSE_A, GrinderSpeedLevelType.HIGH)),
        ("set_auto_speed", (DoseIndex.DOSE_A, True)),
        ("set_auto_speed_reference", (DoseMode.MASS_TYPE,)),
    ],
)
async def test_unsupported_model(
    mock_grinder: LaMarzoccoGrinder,
    mock_cloud_client: MagicMock,
    method: str,
    args: tuple,
) -> None:
    """Test the Swan only commands raise on a Pico."""
    mock_grinder.dashboard.model_code = ModelCode.PICO_GRINDER

    with pytest.raises(UnsupportedModel):
        await getattr(mock_grinder, method)(*args)
    assert not mock_cloud_client.method_calls


async def test_set_auto_standby(
    mock_grinder: LaMarzoccoGrinder,
    mock_cloud_client: MagicMock,
    grinder_serial: str,
) -> None:
    """Test setting the auto standby updates the schedule."""
    mock_grinder.schedule.auto_stand_by = auto_stand_by = AutoStandBy(
        enabled=True, stand_by_minutes=10
    )
    mock_cloud_client.set_grinder_auto_standby.return_value = True

    assert await mock_grinder.set_auto_standby(30)
    mock_cloud_client.set_grinder_auto_standby.assert_called_once_with(
        grinder_serial, 30
    )
    assert auto_stand_by.stand_by_minutes == 30


@pytest.mark.parametrize(
    ("method", "cloud_method", "args"),
    [
        ("set_power", "set_grinder_mode", (False,)),
        ("set_barista_light", "set_grinder_barista_light", (True,)),
        ("set_grind_with", "set_grinder_grind_with", (GrinderGrindWithMode.BY_BUTTON,)),
        ("set_dose", "set_grinder_dose", (DoseIndex.DOSE_A, 9.0)),
        ("set_more_dose", "set_grinder_more_dose", (2.0,)),
        ("set_single_dose_mode", "set_grinder_single_dose_mode", (True,)),
        ("set_mirror_doses", "set_grinder_mirror_doses", (True,)),
        (
            "set_speed",
            "set_grinder_speed",
            (DoseIndex.DOSE_A, GrinderSpeedLevelType.HIGH),
        ),
        ("set_auto_speed", "set_grinder_auto_speed_enabled", (DoseIndex.DOSE_B, True)),
        (
            "set_auto_speed_reference",
            "set_grinder_auto_speed_reference",
            (DoseMode.PULSES_TYPE,),
        ),
        ("set_auto_standby", "set_grinder_auto_standby", (20,)),
    ],
)
async def test_commands_without_widgets(
    mock_grinder: LaMarzoccoGrinder,
    mock_cloud_client: MagicMock,
    method: str,
    cloud_method: str,
    args: tuple,
) -> None:
    """Test commands succeed when the dashboard has no widgets."""
    mock_grinder.dashboard.model_code = ModelCode.SWAN_GRINDER
    getattr(mock_cloud_client, cloud_method).return_value = True

    assert await getattr(mock_grinder, method)(*args) is True
    getattr(mock_cloud_client, cloud_method).assert_called_once()
